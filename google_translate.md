# Keystroke Google Translate extension — build spec

Status: draft spec, no code written yet.
Target: a community Keystroke extension (Omarchy plugin, `x-keystroke.apiVersion: 1`) that
reproduces the Raycast [`google-translate`](https://github.com/raycast/extensions/tree/a5090e97075f2e65e331127456797d9561b5e2b0/extensions/google-translate)
extension's behaviour inside the palette.

## 1. Decision: keyless, same as Raycast

The Raycast extension uses **no authentication at all**. It does not touch the Google Cloud
Translation API, has no API-key preference and no Google Cloud dependency. It calls the
undocumented endpoint that the translate.google.com web page uses, via a vendored copy of
`@iamtraction/google-translate`.

We do the same, for the same reason: Keystroke is free, the extension is free, and a
BYO-key flow (GCP project, billing account, key pasted into a config file) is
disproportionate for translating a phrase from a launcher.

Accepted costs, stated once so they are not rediscovered later:

- The endpoint is undocumented and outside Google's Terms of Service.
- It is rate-limited per source IP; heavy use returns HTTP 429.
- It can break whenever Google changes the request contract. Mitigation is the same one
  Raycast chose: **vendor the transport** into our own repo so we can patch it, rather than
  depending on an upstream package.

If we later want a supported path, the backend is swappable — see §10.

## 2. What the reference extension ships

Feature inventory taken from the pinned commit.

| Raycast surface | Behaviour |
| --- | --- |
| `translate` (view) | Type text, see translation live as you type |
| `translate-form` (view) | Form with explicit source/target pickers |
| `quick-translate` (view) | One input, translated into *several* target languages at once |
| `instant-translate-copy` (no-view) | Translate current selection, copy result, no UI |
| `instant-translate-paste` (no-view) | Translate current selection, paste into the focused app |
| `instant-translate-view` (no-view) | Translate current selection, show result as a HUD |

Result actions: **Copy**, **Paste**, **Toggle Full Text**, **Open in Google Translate**,
plus text-to-speech playback of the translation.

Preferences: `langFrom` (250 options, default `auto`), `lang1` (250, default `en`),
`lang2` (249, default `en`), `autoInput` (bool, default true), `defaultAction`
(`copy` | `paste`), `prioritizeCrossLanguage` (bool, default false), `proxy` (free text).

Two behaviours worth copying because they are what make it feel smart:

1. **Same-language fallback.** With `langFrom: auto`, if the detected source language equals
   the first target, it re-translates into the second target instead. Typing English with
   `en` as target does something useful rather than echoing the input.
2. **Double-way translate.** Translate A→B, then feed the result back B→A, so you can sanity
   check the translation without leaving the palette.

## 3. Transport (verified against the live endpoint)

All of the following was probed directly, not read off documentation.

### 3.1 Request

```
GET https://translate.google.com/translate_a/single
  ?client=dict-chrome-ex
  &sl=<source or "auto">
  &tl=<target>
  &hl=<target>
  &dt=at&dt=bd&dt=ex&dt=ld&dt=md&dt=qca&dt=rw&dt=rm&dt=ss&dt=t
  &ie=UTF-8&oe=UTF-8&otf=1&ssel=0&tsel=0&kc=7
  &q=<percent-encoded text>
```

The `dt` parameters select which payload sections come back: `t` translation,
`rm` romanisation, `bd` dictionary, `at` alternatives, `ex` examples, `ld` language
detection. Request only what a given call renders — the single-word dictionary payload is
large.

### 3.2 The `tk` token is dead weight — do not port it

The vendored library computes a `tk` query parameter with deliberately obfuscated,
reverse-engineered Google code (`zr`/`wr`/`xr` in `tokenGenerator.ts`), seeded by a `TKK`
value scraped from the translate.google.com HTML with the regex `tkk:'\d+.\d+'`.

Two verified findings:

- **That scrape no longer matches.** `curl https://translate.google.com | grep -c "tkk:'"`
  returns `0`. `window.TKK` therefore stays at its `"0"` default and `zr()` produces a
  meaningless token on every call.
- **`tk` is not validated for `client=dict-chrome-ex`.** Identical byte-for-byte responses
  (HTTP 200, 124 bytes) with a bogus `tk=0.0` and with the parameter omitted entirely.

So the token generator is entirely vestigial in the reference implementation. **Our port
omits it.** This removes the single ugliest, most fragile, most obviously-reverse-engineered
piece of the whole thing. If Google ever starts enforcing `tk` for this client, the symptom
will be a sudden uniform HTTP 4xx, and *that* is the moment to reconsider — not before.

### 3.3 POST fallback for long input

The reference switches to POST when the assembled URL exceeds 2048 characters: drop `q`
from the query string, send it as `q=<text>` in an
`application/x-www-form-urlencoded;charset=UTF-8` body. Verified working (HTTP 200 on a
~2600-character input). Keep this — it is what stops long clipboard text from failing.

### 3.4 Response shape

A JSON array. Indices used:

| Path | Meaning |
| --- | --- |
| `body[0][*][0]` | translated segments — concatenate in order for the full text |
| `body[0][1][2]` | romanisation of the **translation** (e.g. `Ohayō`) |
| `body[0][1][3]` | phonetic of the **source** (e.g. `ˌɡo͝od ˈmôrniNG`) |
| `body[2]` | detected source language |
| `body[8][0][0]` | confirmed source language; differs from `body[2]` ⇒ "did you mean" |
| `body[1]` | dictionary: part of speech, synonyms, reverse translations with frequencies |
| `body[7][0]` | spelling correction, with `<b><i>…</i></b>` marking the changed span |
| `body[7][5]` | `true` ⇒ auto-corrected, otherwise ⇒ "did you mean" |

Sample (`hello world`, auto→fr):

```json
[[["Bonjour le monde","hello world",null,null,10]],null,"en",null,null,null,0.763,[],[["en"],null,[0.763],["en"]]]
```

Note the reference's `extractPronounceTextFromRaw` reads `raw[0][1][2]` — the *target*
romanisation, which is the useful one for en→ja and similar. Match that.

## 4. Keystroke mapping

### 4.1 Plugin layout

```
keystroke-translate/
  manifest.json
  Service.qml            # the provider object; owns all state and async work
  TranslateView.qml      # multi-target / double-way view (§4.6)
  transport/Translate.js # vendored request building + response parsing
  data/languages.js      # the 250-language table
  assets/icon.svg
```

`manifest.json`:

```json
{
  "schemaVersion": 1,
  "id": "io.github.evindor.keystroke-translate",
  "name": "Translate",
  "version": "1.0.0",
  "kinds": ["service"],
  "keepLoaded": true,
  "entryPoints": { "service": "Service.qml" },
  "x-keystroke": { "apiVersion": 1 }
}
```

The folder name must equal the id or the host skips the manifest
(`core/Extensions.js`, `parseScan`).

### 4.2 Query grammar

Three shapes, all resolving to `(text, from, to)`:

| Typed | Meaning |
| --- | --- |
| `tr bonjour` | detect source, translate to primary target |
| `tr fr bonjour` | explicit target by ISO code or name |
| `bonjour to french` / `bonjour in french` | natural trailing form |

Declare these as `patterns` so the host boosts our rows without us scoring against every
other provider:

```js
patterns: [
  { id: "prefix", regex: "^\\s*(tr|translate)\\s+\\S", flags: "i", boost: 20,
    example: "tr bonjour", description: "Translates the rest of the line" },
  { id: "target",  regex: "\\s(?:to|in)\\s+[a-z]{2,}\\s*$", flags: "i", boost: 14,
    example: "bonjour to english", description: "Translates into a named language" }
]
```

Keep them linear and short — the host runs every pattern on the UI thread on every
keystroke and truncates at 400 characters.

**Do not offer a bare-text fallback row on every query.** A translate provider that answers
*any* input would put a row under everything the user types. Answer only when a pattern
matched (`ctx.patterns.matched.length`) or the palette is scoped to us. Guard for older
hosts: `ctx.patterns && ctx.patterns.matched.length`.

### 4.3 Rows

Primary result, `tier: "answer"`:

```js
{
  id: "translate/" + from + "/" + to,        // stable; never the query text
  title: translatedText,
  subtitle: pronunciation || (fromName + " → " + toName),
  section: "Translate",
  verb: "Copy",
  preview: translatedText,                    // full text when it wraps
  previewLabel: toName.toUpperCase(),
  previewDetail: dictionarySummary,           // from body[1], when present
  hint: "↵ copies · ctrl ↵ pastes",
  action: { type: "copy", text: translatedText },
  altAction: pasteEffect
}
```

Secondary rows, `tier: "item"`: the reverse translation (double-way), each additional
target language, "Open in Google Translate", "Speak". A spelling correction from `body[7]`
becomes a row whose activation re-runs the query with the corrected text.

`id` must be stable per logical result — it drives in-place delegate updates and frecency.
Never set `remember: true` on a row keyed by query text.

### 4.4 Effects

| Action | Effect |
| --- | --- |
| Copy | `{type: "copy", text}` |
| Paste | `{type: "exec", argv: ["wtype", "--", text]}` — the palette closes before it runs |
| Open in Google Translate | `{type: "url", url: "https://translate.google.com/?sl=…&tl=…&text=…&op=translate"}` |
| Speak | `{type: "exec", argv: ["mpv", "--no-video", "--really-quiet", "--", ttsUrl]}` |
| Change target | `{type: "navigate", scope: "…"}` into the language picker |

Raycast plays TTS with `afplay`, which is macOS-only. On Omarchy use `mpv`; fall back to
`paplay` if `mpv` is absent, and degrade by hiding the Speak row rather than failing.

`defaultAction` (`copy` | `paste`) decides which of copy/paste is `action` and which is
`altAction`, matching the reference preference.

### 4.5 Settings — and a hazard specific to Keystroke

Raycast can afford 250-entry dropdowns because preferences live in a modal panel. **We
cannot.** In Keystroke every enum option becomes a searchable palette row reachable from
the root by breadcrumb (`core/SettingsTree.js`, `schemaNodes`). Three 250-option enums would
inject ~750 rows into the global settings tree and measurably degrade palette search for
someone who never translates anything.

So:

```js
settings: [
  { key: "targets", type: "string", default: "en,fr",
    label: "Target languages",
    description: "Comma-separated ISO codes, tried in order" },
  { key: "source", type: "enum", options: ["auto", "en", "fr", "de", "es", "uk", "ru"],
    default: "auto", label: "Translate from" },
  { key: "defaultAction", type: "enum", options: ["copy", "paste"], default: "copy",
    label: "Default action" },
  { key: "prioritizeCrossLanguage", type: "boolean", default: false,
    label: "Prioritise cross-language results" },
  { key: "speak", type: "boolean", default: false, label: "Offer pronunciation playback" },
  { key: "proxy", type: "string", default: "", label: "HTTP proxy" }
]
```

The full 250-language set stays reachable — but through an **in-palette picker scope**
(`navigate` into `…/targets`) that we render from `data/languages.js`, not through the
settings enum. Same reach, no pollution of the global tree.

`enabled` is reserved by the host; do not declare it.

### 4.6 Provider view

Expose `view: Component { TranslateView { service: root } }` and return
`{type: "provider-view", provider: manifest.id}` to open it. The view covers the
`quick-translate` and `translate-form` equivalents: an editor plus one block per target
language, and the double-way pair.

View rules from the provider contract:

- **Do not fill the view with an opaque rectangle** — the host paints the backdrop behind it
  and an opaque fill covers the card border the active theme draws. Guard any own backdrop
  behind `visible: !(host && host.paintsViewBackdrop)`.
- **Take the type scale from the host**, not `Style.font.*`: `host.fontInput` for the editor,
  `host.fontTitle` for each translation, `host.fontLabel` for language captions. Otherwise
  the view reads smaller than the rows it replaced and ignores the density setting.
- Implement `dismiss()` to abort in-flight requests without blocking close.
- While `host.voice.active`, `↵` calls `host.voiceStop()` and any other non-modifier key
  calls `host.voiceCancel()` — this makes dictate-then-translate work.

### 4.7 Selection-based entry points

The three `instant-translate-*` commands operate on the current selection. Keystroke has no
no-view command kind, so they become rows that read the selection themselves:

- Read with `wl-paste --primary --no-newline` (fall back to the clipboard).
- Offer them only when the selection is non-empty and differs from the typed query.
- `instant-translate-view` maps to opening the provider view pre-filled;
  `-copy` and `-paste` map to the corresponding effects directly.

This is also the `autoInput` preference: when the palette opens with an empty query and a
selection exists, seed from the selection.

## 5. Networking implementation

The repo's established pattern is `curl` through a `Process`, argv-literal — see
`core/Extensions.js:239` (`fetchArgv`) and `providers/Extensions.qml`. Reuse it; there is no
credential here, so the argv-exposure concern that applies to keyed backends does not arise.

Rules that follow from `query(ctx)` running on the UI thread for every keystroke:

1. **Never block.** `query` returns cached rows synchronously, calls `ctx.pending()` when a
   request is in flight, and calls `host.requery({catalog: false, provider: manifest.id})`
   when the response lands.
2. **Debounce ~350 ms** after the last keystroke before issuing a request. Typing a sentence
   must not fire twenty requests — that is the fastest route to HTTP 429.
3. **Cache** on `(text, from, to)` in an LRU of a few hundred entries for the session.
   Repeat queries and backspacing must not re-hit the network.
4. **One in-flight request per target**; supersede rather than queue. Tag each with the
   `ctx.generation` it was issued for and drop responses whose generation is stale.
5. **Timeout** `--max-time 20`, matching the existing fetcher.
6. **Minimum length**: skip queries under 2 characters.

Proxy support: when `settings.proxy` is set, add `--proxy <value>` to the curl argv. This is
the escape hatch for rate-limiting and geo-blocking, which is why the reference exposes it.

## 6. Errors

| Condition | Behaviour |
| --- | --- |
| HTTP 429 | Row: "Too many requests — try again later". Back off 60 s before the next attempt. Do not retry in a loop. |
| curl non-zero exit | `host.errorMessage` naming the exit code, as `providers/Extensions.qml:115` does |
| Unparseable body | Treat as a transport break, surface "Translation unavailable", log the first 200 bytes |
| Unsupported language code | Reject at parse time with the offending code named |

A sustained parse failure is the signal that Google changed the contract. Make it loud in
the status line rather than silently returning nothing.

## 7. Testing

Follow `tests/extensions_check.py`, which drives the real Omarchy plugin scripts against a
local bare repository.

- **Transport unit tests, offline.** Fixture JSON bodies captured from the live endpoint
  (short text, long text, single word with dictionary, non-Latin target, spelling
  correction, 429) parsed by `transport/Translate.js`. These must not hit the network.
- **One opt-in live test**, skipped by default, that asserts the endpoint still answers and
  the indices in §3.4 still hold. This is the canary for Google changing the contract.
- **Install/enable/disable/remove** through the real scripts against a bare clone.
- **Palette behaviour** via the offscreen capture harness — per project practice, verify by
  offscreen capture rather than synthetic keystrokes into the live palette.
- **Per-keystroke cost** via `tools/profile_palette.py`, to confirm the patterns and cache
  lookup stay off the UI-thread budget.

## 8. Language data

Lift the 250-language table from the reference's `package.json` preference `data` array
(`{title, value}` pairs) into `data/languages.js` as `{code, name}`. Needed for: validating
codes before a request, resolving `to french` → `fr`, the picker scope, and display names on
rows. Match on code, English name, and a small alias set (`ua`→`uk`, `cn`→`zh-CN`).

## 9. Milestones

1. `transport/Translate.js` + fixtures + unit tests — no QML, no palette.
2. Minimal provider: `tr <text>` → one answer row, copy. Installable from a local bare repo.
3. Debounce, cache, generations, error rows.
4. Language parsing (`tr fr …`, `… to french`), picker scope, settings.
5. Reverse translation, dictionary detail, spelling correction.
6. Provider view: multi-target, double-way, voice.
7. Selection entry points, TTS, proxy.
8. Icon, README, `extensions/index.json` entry.

## 10. Non-goals and exit

Not in scope: document translation, offline models, a supported cloud backend, any
credential storage.

Keep the backend behind the `transport/` boundary so a keyed provider (DeepL API Free is the
best-fitting one: static `Authorization: DeepL-Auth-Key` header, 500k chars/month, no card,
hard-stops instead of billing) can be added later as a second implementation selected by a
setting. If that happens, two Keystroke-specific hazards apply that do not apply today:

- A key stored as a `string` setting is rendered in cleartext as the row accessory
  (`core/SettingsTree.js:37-40`, `current = String(value)`) and is searchable from the root.
  Store a reference, or read the key via `secret-tool`.
- An argv-literal curl leaks a key to `ps` via `/proc/<pid>/cmdline`. Pass headers through
  `curl -K -` on stdin or a `0600` config file.

Neither matters for the keyless transport specified here. Both matter the moment a key exists.
