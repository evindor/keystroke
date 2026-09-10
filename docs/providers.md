# Keystroke provider contract (API 1)

A provider supplies rows for a query and effects for activation. Bundled providers ([providers/](../providers/)) and extensions implement the same interface.

## Packaging an extension

Bundled providers live in [providers/](../providers/) and are instantiated by `providers/Registry.qml`. Third-party providers are **extensions**: one folder each under [extensions/](../extensions/) in this repository (merged through pull requests, so they ship with Keystroke), or under `~/.local/share/keystroke/extensions/` on the user's machine (work in progress, or private). A folder holds an `extension.json` and the QML it names:

```json
{
  "name": "Thing", "version": "1.0.0", "author": "You", "description": "One line for the Extensions screen",
  "apiVersion": 1, "icon": "󰀻", "color": "#8bceb4",
  "entry": "Service.qml",
  "setup": { "run": "bin/setup", "summary": "Downloads a 40 MB model, verified by SHA-256" }
}
```

`commands` (optional) declares the typed triggers, see *Commands* below; it lives in `extension.json` so the usage is known, and shown, before the extension is turned on. `name`, `version`, `author`, `description` and `apiVersion` (exactly `1`) are required; `icon` (a glyph from Omarchy's icon font) and `color` decorate the extension's rows before its code is loaded; `entry` defaults to `Service.qml` and must be a `.qml` file inside the folder; `homepage` (https) replaces the GitHub link on the extension's screen; `license` is informational; `setup` is only for an extension that needs a one-off step before it can work (see below). The **folder name is the extension's id**: lowercase letters, digits and dashes, distinct from every bundled provider id. It is the registry key, the settings section (`providers.<id>` in `keystroke.json`) and the scope (`<id>`, `<id>/<sub>`).

`providers/Registry.qml` scans both folders (`core/Extensions.js`, `scanArgv`/`parseScan`) when the palette is created and on every open; a local folder with the same id replaces the shipped one. **An extension is off until the user turns it on** (`providers.<id>.enabled: true`), and one that is off is never compiled or instantiated: the registry lists it from `extension.json` alone, with an empty settings schema. Turning it on creates `entry` in its own object tree at once, injecting `shell`, `extension` (the parsed `extension.json` plus `id`, `dir` and `source`, `"builtin"` or `"local"`) and `omarchyPath`, and reads `provider`. Turning it off destroys the object. A folder whose `extension.json` is unusable, and an extension that is on but whose entry fails to compile, exposes no `provider`, or declares another `apiVersion`, is listed under "Extensions needing attention" in Settings and shows **Needs attention** on the Extensions screen. The QML engine caches components by file and Quickshell 0.3.1 cannot clear that cache, so after editing a loaded extension's code run `omarchy-restart-shell`; a first load has nothing cached.

The reference extension is [extensions/timer](../extensions/timer/); the step-by-step guide is [CONTRIBUTING.md](../CONTRIBUTING.md#build-an-extension).

## Extensions screen

`providers/Extensions.qml` (logic in `core/Extensions.js`) lists every extension found by the registry with Keystroke's switch. Turning one on goes through a confirmation that says the extension was checked and reviewed before it shipped (or that a local folder was not), that it nonetheless runs at the user's own risk, and that checking its code first is recommended. The same confirmation guards the **Enabled** row under Keystroke Settings. `Ctrl+↵` on a list row that is on turns it off. An extension's own screen starts with a **Usage** section built from its declared commands: the usage line (`tr [to] <text>`), what each argument means, examples that type themselves into the palette when activated, and a **Prefix** row that leads to the reserved `prefix` setting. An extension that declares `setup` gets a **Run setup** row: after a confirmation, the palette closes and `omarchy-launch-floating-terminal-with-presentation` runs the script in a visible terminal from the extension's folder (`setupArgv`); the script's exit status is shown there. Keystroke does not track whether setup has happened; the provider checks for what it needs and says so in its rows. The screen never touches the network: extensions arrive with Keystroke's own updates. `tests/palette_extensions_check.py` drives the real palette offscreen through the whole lifecycle.

## Provider object

```js
readonly property var provider: ({
  apiVersion: 1,
  name: "Thing", icon: "✳", iconFont: "", iconSource: "", color: "#hex", description: "",
  commands: [ { id, prefix, title, summary, args: [{ name, hint, optional, rest }], examples } ],   // optional, see Commands
  patterns: [ { id, regex, flags, boost, example, description } ],   // optional, see Patterns
  settings: [ { key, type: "boolean"|"enum"|"number"|"string", label, "default", options, min, max, integer, description } ],
  view: Component { ... },                        // optional, see Provider views
  query: function(ctx) { ... return rows },       // required
  activate: function(row, ctx) { ... return effect }, // optional; defaults to row.action (row.altAction when ctx.alternate)
  opened: function() { },                         // optional; called on every summon
  dismiss: function() { }                         // optional; called when the palette closes while your view is showing
})
```

Bundled providers also carry `id`; extensions are keyed by their folder name.

`icon` is a glyph (Omarchy's icon font unless `iconFont` names another); `iconSource` is an optional image URL that replaces the glyph wherever the provider itself is shown: its row on the Extensions screen, its screen's About row, and its entry under Keystroke Settings. Resolve it next to your QML file with `String(Qt.resolvedUrl("assets/icon.svg"))`, and put the same value in your rows' `iconSource` so the result rows carry it too. SVG and PNG both render; keep the glyph as the fallback for the moment before the image loads.

### ctx

`query` (string), `rawQuery` (full original text before spoken-command normalization), `scope` (`""` at root, or `<key>` / `<key>/<sub>`), `sub`, `generation`, `settings` (validated values for your schema, plus `prefix` when you declare commands), `patterns` (`{ matched: [ids], boost }` for your declared patterns against this query; `{ matched: [], boost: 0 }` when none matched or none are declared), `command` (`{ id, prefix, rest, args }` when the query starts with one of your declared commands, with `rest` the text after the prefix; `null` otherwise, and absent on older hosts), `pending()` (call when more rows will arrive later), `host` (`host.requery()` re-runs the current query; `host.appLibrary`, `host.omarchyPath`, `host.shell`), `shell`, `appLibrary`, `omarchyPath`.

`host.requery(options)` accepts `{ catalog: false }` when only your `query` rows changed (the Smart Match catalog is kept) and `provider: "<your id>"` so only your rows are queried again; the other providers' rows for the current query are reused. Calls landing in one event-loop turn run a single query, and none interrupts the typing pause.

### Patterns

A provider that answers a recognisable shape of text (a unit conversion, a variable assignment, a currency amount, a date expression) declares it, so the host can rank its offer without the provider computing scores against every other provider's:

```js
patterns: [
  { id: "assignment", regex: "^\\s*[a-z_]\\w*\\s*=\\s*\\S", flags: "i", boost: 14, example: "price = 10", description: "Assigns a variable" },
  { id: "currency", regex: "[$€£]\\s*\\d", boost: 12, example: "$100 in EUR" }
]
```

`regex` is a string (or a `RegExp`; flags limited to `i`, `m`, `s`, `u`), `boost` a number from 0 to 100 (default 10), `example` and `description` short prose. The host compiles the list once when the registry is built, tests every pattern against the query before calling `query(ctx)`, and:

- adds the largest `boost` among the matched patterns to the score of every row the provider returns for that query, inside the row's tier, after the default matcher or the provider's explicit `score` has produced a positive score (a matched pattern never revives a row the matcher dropped);
- passes the matched ids in `ctx.patterns.matched`, so the provider can return its offer only when something matched, pick a subtitle per shape, or skip work it knows is pointless;
- lists the `example`s on the extension's screen ("Answers queries like price = 10 · $100 in EUR").

Fallback rows (`tier: "fallback"`, the *Continue with* section) are where this matters most: the assistant hand-offs sit at scores 2 to 5 there, so an extension whose shape matched lands above them with a base score of 1 and a boost of 5 or more, and below them otherwise. An invalid pattern is reported under "Plugins needing attention" and skipped; the provider still loads. Patterns run on the UI thread for every keystroke: keep them linear (no nested quantifiers over the same text) and under 400 characters; the host keeps the first 64.

Return quickly. `query` runs on the UI thread for every keystroke; anything that forks or reads large files must be cached or asynchronous (`Process`/`FileView` in your service, then `host.requery()`).

### Commands

A provider that is triggered by a typed word or sign declares it, so the host can explain it instead of every provider parsing its own prefix:

```js
commands: [{
  id: "translate", prefix: "tr", title: "Translate", summary: "Translate text into your target languages",
  args: [{ name: "to", hint: "a language code or name", optional: true }, { name: "text", hint: "what to translate", rest: true }],
  examples: ["tr bonjour", "tr fr good morning"]
}]
```

An extension declares its commands in `extension.json` (the registry reads them while the extension is off, so the Extensions screen can show its usage before any code loads); a bundled provider declares them on the provider object. `prefix` is one word (letters, digits, dashes, at most 16 characters, matched without regard to case) or a **sigil**: one or two punctuation characters such as `~`, `:` or `/`, which attach to the text with no space. `title` is the action as a verb phrase ("Set a timer"); `summary` one line; `args` are positional, each with a `name` shown as the placeholder and a `hint` shown while the caret is on it and on the Usage rows (one row per argument), `optional: true` for one that may be left out, `rest: true` for the last one when it takes the rest of the line; `examples` are up to four complete queries. At most eight commands per provider; the first one is the one a user can rename.

From that declaration the host does, for every provider alike:

- **Routing.** A query that starts with the prefix goes to the provider alone, with `ctx.command = { id, prefix, rest, args }`, the prefix already removed: the user named the provider, so no other provider is asked and Smart Match stays out. Every row it returns gets a boost of 20, like a matched pattern, and the default matcher scores rows against `rest`, not the prefix. **Read `ctx.command.rest`, never re-parse the prefix**: the user may have renamed it. Keep your old check as a fallback for hosts that do not send `ctx.command`.
- **The user's prefix.** A provider with commands gets the reserved `prefix` setting (a string, listed first on its settings screen and returned in `ctx.settings.prefix`); the host applies it to the first command. Two enabled providers with the same prefix: the earlier one in registry order answers, the other is skipped for that prefix.
- **The hint line.** While the query starts with a command, the line under the search field shows the command's `title`, then the name and `hint` of the argument the caret is on ("Translate · to: a language code or name (optional)"); with every argument typed, the `summary`.
- **Ghost placeholders.** The arguments still to type are drawn after the caret in the field's own font (`[to] <text>`, `<name>` required, `[name]` optional), and disappear one by one as words are typed. A word prefix on its own gets a soft highlight sweeping across it once when it is recognised, timed by the animation tier.
- **Tab.** A row whose action is `{type: "query"}` types its text; the host offers such a row for a query that matches a command's title ("trans" → *Translate · tr [to] <text>*, hint "tab types tr"). Tab after a bare word prefix adds the space so the placeholders show.
- **The `/` screen.** `/` is a sigil command of the bundled Commands provider: it lists every command of every enabled provider with its usage line, `/tr` filters the list, Enter types the prefix. The same list is the *Commands* scope, reachable from the root row **What can I type?**, and the empty root's hint line says so.
- **Usage on the Extensions screen** (above), and a status line when the user turns an extension on: "Translate is on · type tr [to] <text>, or find it by name".

Commands and patterns coexist: a command is the explicit trigger, a pattern the shape of text with no prefix (`bonjour to english`). Declare both when both apply. A command that does not compile is reported under "Extensions needing attention" and skipped; the provider still loads.

### Rows

```js
{ id: "stable-id", title: "…", subtitle: "", icon: "󰀻", iconFont: "", iconSource: "file:///…",
  tint: "#hex", section: "Thing", verb: "Open", tier: "item",  // "answer" | "item" | "fallback"
  score: 100, order: 0, keywords: "ids aliases", path: "Parent › Child › …", description: "prose", accessory: "✓", hint: "↵ copies",
  disabled: false, remember: false, confirm: "Really?", confirmDetail: "one muted line under the question",
  preview: "text", previewLabel: "RESULT", previewDetail: "…", previewImage: "/path.png", swatch: "#hex",
  action: effect, altAction: effect }
```

Legacy `catalog(ctx)` fields are ignored; the local model command classifier has been removed.

`confirm` asks before the effect runs; the optional `confirmDetail` is a muted line under the question. Turning an extension on uses it to say what was checked and that the code runs at the user's own risk. A confirmation never carries a link: opening anything would move focus away from the palette.

`altAction` is optional and runs on `Ctrl+↵` (a row without one runs `action` again). Say what it does in `hint` ("ctrl ↵ terminal"). A provider's `activate(row, ctx)` receives `ctx.alternate === true` for that key so it can compute the effect itself.

`id` must be stable for a logical result: it drives in-place delegate updates and frecency. `score` orders only within the tier; omit it to use the default matcher, `Match.match(query, title, keywords, path, description)`, which is fuzzy over `title`, over `path` (the breadcrumb ending in the title, for rows that live in submenus; matched slightly below the title) and over `keywords` (identifiers a user may abbreviate: aliases, ids, config keys; matched below the path), and word-prefix only over `description` (prose). Put synonyms and sentences in `description`, not `keywords`: scattered letters would match any sentence. Rows with a zero score are dropped when the query is non-empty. A provider that owns a tree should return every descendant when the query is non-empty, with `path` relative to the current scope, so abbreviations reach deep items from the root. `remember: true` opts into frecency (never use query text as the id).

### Effects

`{type:"navigate", scope, title}` · `{type:"query", text}` (put `text` in the search field at the palette root and stay open: what a command's usage rows and the `/` screen do) · `{type:"exec", argv}` (literal argv, login-shell env) · `{type:"shell", command}` (trusted strings only) · `{type:"copy", text}` · `{type:"url", url}` · `{type:"app", id, name}` (launch via AppLibrary) · `{type:"notify", glyph, headline, body}` · `{type:"setting", path, key, value, schema}` · `{type:"compound", actions}` · `{type:"close"}` (dismiss the palette, nothing else) · `{type:"noop"}` (stay open; pair it with `host.requery()` when your rows changed). The host closes the palette before anything that launches.

A provider's own `activate(row, ctx)` may perform work itself (start a process, mutate its state) and return one of the effects above; private action types are fine as long as `activate` translates them (see `providers/Extensions.qml`). `ctx.host` is the palette: `host.requery()`, `host.statusMessage = "…"`, `host.errorMessage = "…"`, `host.opened`, `host.scope`, `host.config`, `host.registry` (the provider registry: `entries`, `manifests`, `problems`, `scan()`), `host.providerSettings(id)` (the validated values of one provider's settings, for a service that keeps state between queries; `host.configChanged` fires on every save), `host.setBarItem(id, item)` (below).

### Bar items

A provider with something to show next to the menu button in the bar calls `host.setBarItem(id, { text, tooltip, payload })` with its own key as `id`, and `host.setBarItem(id, null)` to clear it. `text` (up to 40 characters, glyphs from the bar's font are fine) is drawn as a bar button after the menu button by Keystroke's own `BarWidget.qml`; `tooltip` shows on hover; `payload` is what the palette is opened with when the item is pressed (`{ scope: extension.id, title: "Timers" }` opens your screen; `{ query: "…" }` types a query; without one the press toggles the menu). One item per provider: a second call replaces the first, an equal one is ignored. The palette keeps items only for loaded, enabled providers, so an extension's item disappears when it is turned off; clear yours in `Component.onDestruction` all the same. Update the text from your own clock (the Timer extension's once-a-second tick), never per query, and bear in mind the space is shared with every other widget the user put in the bar. Old hosts have no `setBarItem`: guard the call with `typeof host.setBarItem === "function"`.

## Scopes and settings

Navigating into a provider gives it scope `<key>`; deeper scopes are `<key>/<sub>`. Settings are stored under `providers.<key>` in `~/.config/omarchy/keystroke.json`; the `enabled` and `prefix` keys are reserved (`prefix` exists only for a provider that declares commands). Screens are generated from `settings`; no UI code is needed. Every screen, setting and enum choice is also searchable from the palette root through its breadcrumb (Keystroke Settings › <name> › <label> › <choice>); the setting `key` and enum option values count as identifiers, so a key like `provider` makes `prefp` reach a setting labelled "Preferred assistant".

## Stability

API 1 is frozen once a second extension ships against it. Changes that add optional fields keep the version; anything else bumps `apiVersion`, and Keystroke keeps loading the previous version for one Omarchy release. Added as optional fields in September 2026, with [keystroke-calpad](https://github.com/evindor/keystroke-calpad) as the second extension: `patterns`, `iconSource` and `ctx.patterns`, and the documented host surface for provider views; later that month `host.setBarItem` and `host.providerSettings`, for the Timer extension's countdown in the bar, then `commands` (in `extension.json` and on the provider object), `ctx.command`, the reserved `prefix` setting and the `query` effect. A provider that uses `ctx.patterns` should treat it as absent on older hosts (`ctx.patterns && ctx.patterns.matched.length`).

## Optional provider views (API 1)

A provider may expose `view: Component { ... }` and return `{type: "provider-view", provider: "<registry key>"}` from activation (an extension's key is its folder name, `extension.id`). The host loads the component over the palette card, injects `host`, and calls optional `focusInput()`. A missing/disabled view produces a visible error. Ordinary row-only providers need no changes. Anything the view needs to know about the activation (the typed text, a saved item) goes through the provider: `activate(row, ctx)` stores it on the provider object before returning the effect, and the view reads it from there (`Component { MyView { service: root } }`, where `root` is your `Service.qml`).

The provider owns view data and asynchronous work; keep durable state outside the loaded component. The view may implement `dismiss()`, `beginVoice()` and `transcript(text, final)`. The host calls dismissal before unloading or navigating and supplies voice snapshots to these optional methods. Dismiss must cancel or detach work without blocking close. The provider must stop its owned resources when disabled; the host also drops a view whose provider is removed, unloaded or turned off while it is showing. See `providers/Codex.qml` and `codex/ConversationView.qml` for the bundled reference, [extensions/translate](../extensions/translate/) for a shipped extension with a view, and [keystroke-calpad](https://github.com/evindor/keystroke-calpad) for a third-party one.

### What a view may use on `host`

The palette is the view's theme and its keyboard context. These members are part of API 1; anything else on the host object is internal and may change.

| Member | Meaning |
| --- | --- |
| `background`, `foreground`, `accent`, `muted`, `hairline` (colors), `fontFamily` (string), `compact` (bool) | The palette's theme, already resolved against the active Omarchy theme and Keystroke's appearance settings. Use them instead of `Color.menu.*` so the accent choice applies to you too. |
| `fontInput`, `fontTitle`, `fontBody`, `fontLabel`, `fontCaption` (ints) | The palette's own type scale, density bump included. Use these instead of `Style.font.*` so a view reads at the size of the results it replaced -- see below. |
| `paintsViewBackdrop` (bool) | True on a host that paints the backdrop behind your view. Undefined on older builds, which is the only case where a view should paint its own. |
| `cancel()` | Close the palette (what `Esc` does). |
| `goBack()` | Leave the view and return to the results, restoring the query. What `←` and `Backspace` on an empty composer do in the bundled views. |
| `requery()` | Re-run the palette's query; relevant when your rows changed while the view was shown. |
| `statusMessage`, `errorMessage` (strings, writable) | The footer text once the user is back on the results. |
| `voice` (`active`, `phase`: `idle`/`starting`/`listening`/`transcribing`, `level` 0..1, `history` array), `voiceTrigger` (`tap`/`hold`), `voiceBegin("tap")`, `voiceStop()`, `voiceCancel()` | The dictation state, for a waveform and for forwarding keys while listening: while `voice.active`, `↵` should call `voiceStop()` and any other non-modifier key `voiceCancel()`. |
| `isModifierKey(key)`, `isSuperKey(key)` | Key classification for the hold-to-talk release. |
| `home`, `omarchyPath`, `shell`, `appLibrary`, `config` (read-only) | The same values `ctx` carries. |

The view runs inside `omarchy-shell`, so `import qs.Commons` and `import qs.Ui` work: `Style.space`, `Style.font.*`, `Style.cornerRadius`, `Util.alpha`, `Ui.Button`, `Ui.BorderSurface` and `Ui.TextField` are the kit the bundled views are made of.

### Styling a view

The host loads the view *inside* the card's border and paints the themed backdrop behind it, so a view must not fill its whole area with an opaque rectangle: that covers the border the active theme draws, and the submenu stops looking like the menu it came from. A view that also has to run against older Keystroke builds can keep its own backdrop behind `visible: !(host && host.paintsViewBackdrop)`.

Sizes are the other half of that. The palette sets its rows in `title` and its search field in `heading`, and shifts both up a step in the comfortable density; a view that reaches for `Style.font.body` directly reads smaller than the results it replaced and ignores the density setting. Take sizes from the host instead:

| token | palette role | size |
| --- | --- | --- |
| `host.fontInput` | the search field; a view's own editor | `heading`, +2 when comfortable |
| `host.fontTitle` | a result row's title; a view's primary content | `title`, +1 when comfortable |
| `host.fontBody` | a preview body; long secondary text | `body` |
| `host.fontLabel` | a row subtitle, the status line, the footer | `bodySmall` |
| `host.fontCaption` | keycaps, the breadcrumb brand | `caption` |

## Developing an extension locally

Put the folder (or a symlink to it, from a checkout of this repository) under `~/.local/share/keystroke/extensions/<id>`. The registry picks it up the next time the palette opens, lists it with a **local** badge, and, once turned on, runs it exactly as a shipped one; a local folder with the same id as a shipped extension replaces it, which is how you iterate on one that already ships. `bin/keystroke check-extensions <folder>` runs the same checks as the pull request review.

## Optional Smart Match catalog

API 1 providers may add `catalog: function(ctx) { return rows }`. It enumerates
current available command/navigation rows for the requested scope, independently
of query wording. Use the normal stable IDs, actions, confirmations, and display
metadata, plus `path`, `keywords`, `description`, and optionally a single-sentence
`intentDescription` stating the outcome. Return quickly from cached state and call
`ctx.pending()` / `host.requery()` when asynchronous catalog state changes: the host
enumerates catalogs once per summon, scope or configuration change and after such
a call, never per keystroke. Filter
unavailable actions and other scopes before returning them. Do not enumerate
clipboard contents, file contents, recent conversations, or unbounded data.

The host uses at most 6,000 catalog rows in a query. It sends IDs and descriptive
text to a local embedding helper; executable actions stay in QML and are resolved
against the latest catalog. Disabled rows are never semantic suggestions. Providers
without this optional method keep their existing lexical behavior; bundled providers
also contribute their root navigation entries. Extensions are never enumerated by
calling their query method with invented empty input.

`intentFamily`, when supplied, can identify `launch`, `navigate`, `install`, `remove`,
`default`, `restart`, `record-start`, `record-stop`, `toggle`, `enable`, or `disable`.
This constrains suggestions for explicit command families and directions; it does
not authorize execution. Do not describe a toggle as an idempotent on/off action
unless the action actually implements that behavior. Existing confirmations and
provider `activate()` are preserved.

Enum setting schemas can optionally provide `optionLabels: { value: "Visible label" }`.
The stored option values and validation remain unchanged; both choice rows and the
current-value accessory use the label when provided.
