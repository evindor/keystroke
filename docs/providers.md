# Keystroke provider contract (API 1)

A provider supplies rows for a query and effects for activation. Bundled providers ([providers/](../providers/)) and community providers implement the same interface.

## Community packaging

An Omarchy plugin of kind `service` whose root object exposes `provider`, with a manifest marker:

```json
{
  "schemaVersion": 1, "id": "you.thing", "name": "Thing", "version": "1.0.0",
  "kinds": ["service"], "keepLoaded": true,
  "entryPoints": { "service": "Service.qml" },
  "x-keystroke": { "apiVersion": 1 }
}
```

Omarchy loads `Service.qml` into `omarchy-shell`, injects `shell`, `manifest` and `omarchyPath`, and destroys it on disable or removal. Keystroke enumerates `pluginRegistry.installedPlugins`, keeps plugins that carry `x-keystroke` and are enabled, and calls `shell.serviceFor(id)`. Re-enumeration happens on every registry change. A plugin whose service is missing, exposes no `provider`, or declares another `apiVersion` is listed under "Plugins needing attention" in Settings instead of loading. Community providers installed out of band (`omarchy plugin add`) start disabled in Keystroke; the user enables them under Extensions → <name> or Settings → <name>. Extensions installed from the palette's own Extensions screen are enabled immediately. Minimal example: [examples/keystroke-hello](../examples/keystroke-hello/); complete, published example: [keystroke-timer](https://github.com/evindor/keystroke-timer). The step-by-step guide is [CONTRIBUTING.md](../CONTRIBUTING.md).

## Extensions screen

`providers/Extensions.qml` (logic in `core/Extensions.js`) is the in-palette manager for community providers. It lists every installed plugin carrying `x-keystroke`, loaded or not, with Keystroke's own on/off switch (`providers.<id>.enabled` in keystroke.json) and Omarchy's (`PluginRegistry.setEnabled`, the same call `omarchy plugin enable/disable` makes). Install, update and remove run Omarchy's scripts as one background job at a time: `omarchy-plugin-add <url> --yes --enable`, `omarchy-plugin-update <id> --yes`, `omarchy-plugin-remove <id> --yes`. Update checks are a `git fetch` per extension without merging. Discovery merges two sources, cached for an hour under `~/.cache/keystroke`: the Keystroke index ([extensions/index.json](../extensions/index.json), raw from GitHub; the URL is a setting) and the Omarchy marketplace catalog (`plugins.omarchy.org/catalog.json`), where an extension is recognised by the word *keystroke* in its id, name, description or tags. Any git URL or `owner/repo` shorthand typed on the Extensions screen offers an install row. Every install and removal asks for confirmation first. `tests/extensions_check.py` drives all of it through the real scripts against a local bare repository.

## Provider object

```js
readonly property var provider: ({
  apiVersion: 1,
  name: "Thing", icon: "✳", iconFont: "", iconSource: "", color: "#hex", description: "",
  prefix: "th",                 // optional, documentation only for now
  patterns: [ { id, regex, flags, boost, example, description } ],   // optional, see Patterns
  settings: [ { key, type: "boolean"|"enum"|"number"|"string", label, "default", options, min, max, integer, description } ],
  view: Component { ... },                        // optional, see Provider views
  query: function(ctx) { ... return rows },       // required
  activate: function(row, ctx) { ... return effect }, // optional; defaults to row.action (row.altAction when ctx.alternate)
  opened: function() { },                         // optional; called on every summon
  dismiss: function() { }                         // optional; called when the palette closes while your view is showing
})
```

Bundled providers also carry `id`; community providers are keyed by their plugin id.

`icon` is a glyph (Omarchy's icon font unless `iconFont` names another); `iconSource` is an optional image URL that replaces the glyph wherever the provider itself is shown: its row on the Extensions screen, its screen's About row, and its entry under Keystroke Settings. Resolve it next to your QML file with `String(Qt.resolvedUrl("assets/icon.svg"))`, and put the same value in your rows' `iconSource` so the result rows carry it too. SVG and PNG both render; keep the glyph as the fallback for the moment before the image loads.

### ctx

`query` (string), `rawQuery` (full original text before spoken-command normalization), `scope` (`""` at root, or `<key>` / `<key>/<sub>`), `sub`, `generation`, `settings` (validated values for your schema), `patterns` (`{ matched: [ids], boost }` for your declared patterns against this query; `{ matched: [], boost: 0 }` when none matched or none are declared), `pending()` (call when more rows will arrive later), `host` (`host.requery()` re-runs the current query; `host.appLibrary`, `host.omarchyPath`, `host.shell`), `shell`, `appLibrary`, `omarchyPath`.

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

### Rows

```js
{ id: "stable-id", title: "…", subtitle: "", icon: "󰀻", iconFont: "", iconSource: "file:///…",
  tint: "#hex", section: "Thing", verb: "Open", tier: "item",  // "answer" | "item" | "fallback"
  score: 100, order: 0, keywords: "ids aliases", path: "Parent › Child › …", description: "prose", accessory: "✓", hint: "↵ copies",
  disabled: false, remember: false, confirm: "Really?", 
  preview: "text", previewLabel: "RESULT", previewDetail: "…", previewImage: "/path.png", swatch: "#hex",
  action: effect, altAction: effect }
```

Legacy `catalog(ctx)` fields are ignored; the local model command classifier has been removed.

`altAction` is optional and runs on `Ctrl+↵` (a row without one runs `action` again). Say what it does in `hint` ("ctrl ↵ terminal"). A provider's `activate(row, ctx)` receives `ctx.alternate === true` for that key so it can compute the effect itself.

`id` must be stable for a logical result: it drives in-place delegate updates and frecency. `score` orders only within the tier; omit it to use the default matcher, `Match.match(query, title, keywords, path, description)`, which is fuzzy over `title`, over `path` (the breadcrumb ending in the title, for rows that live in submenus; matched slightly below the title) and over `keywords` (identifiers a user may abbreviate: aliases, ids, config keys; matched below the path), and word-prefix only over `description` (prose). Put synonyms and sentences in `description`, not `keywords`: scattered letters would match any sentence. Rows with a zero score are dropped when the query is non-empty. A provider that owns a tree should return every descendant when the query is non-empty, with `path` relative to the current scope, so abbreviations reach deep items from the root. `remember: true` opts into frecency (never use query text as the id).

### Effects

`{type:"navigate", scope, title}` · `{type:"exec", argv}` (literal argv, login-shell env) · `{type:"shell", command}` (trusted strings only) · `{type:"copy", text}` · `{type:"url", url}` · `{type:"app", id, name}` (launch via AppLibrary) · `{type:"notify", glyph, headline, body}` · `{type:"setting", path, key, value, schema}` · `{type:"compound", actions}` · `{type:"close"}` (dismiss the palette, nothing else) · `{type:"noop"}` (stay open; pair it with `host.requery()` when your rows changed). The host closes the palette before anything that launches.

A provider's own `activate(row, ctx)` may perform work itself (start a process, mutate its state) and return one of the effects above; private action types are fine as long as `activate` translates them (see `providers/Extensions.qml`). `ctx.host` is the palette: `host.requery()`, `host.statusMessage = "…"`, `host.errorMessage = "…"`, `host.opened`, `host.scope`, `host.config`, `host.pluginRegistry`.

## Scopes and settings

Navigating into a provider gives it scope `<key>`; deeper scopes are `<key>/<sub>`. Settings are stored under `providers.<key>` in `~/.config/omarchy/keystroke.json`; the `enabled` key is reserved. Screens are generated from `settings`; no UI code is needed. Every screen, setting and enum choice is also searchable from the palette root through its breadcrumb (Keystroke Settings › <name> › <label> › <choice>); the setting `key` and enum option values count as identifiers, so a key like `provider` makes `prefp` reach a setting labelled "Preferred assistant".

## Stability

API 1 is frozen once a second community provider ships against it. Changes that add optional fields keep the version; anything else bumps `apiVersion`, and Keystroke keeps loading the previous version for one Omarchy release. Added as optional fields in September 2026, with [keystroke-calpad](https://github.com/evindor/keystroke-calpad) as the second community provider: `patterns`, `iconSource` and `ctx.patterns`, and the documented host surface for provider views. A provider that uses `ctx.patterns` should treat it as absent on older hosts (`ctx.patterns && ctx.patterns.matched.length`).

## Optional provider views (API 1)

A provider may expose `view: Component { ... }` and return `{type: "provider-view", provider: "<registry key>"}` from activation (a community provider's key is its plugin id, `manifest.id`). The host loads the component over the palette card, injects `host`, and calls optional `focusInput()`. A missing/disabled view produces a visible error. Ordinary row-only providers need no changes. Anything the view needs to know about the activation (the typed text, a saved item) goes through the provider: `activate(row, ctx)` stores it on the provider object before returning the effect, and the view reads it from there (`Component { MyView { service: root } }`, where `root` is your `Service.qml`).

The provider owns view data and asynchronous work; keep durable state outside the loaded component. The view may implement `dismiss()`, `beginVoice()` and `transcript(text, final)`. The host calls dismissal before unloading or navigating and supplies voice snapshots to these optional methods. Dismiss must cancel or detach work without blocking close. The provider must stop its owned resources when disabled; the host also drops a view whose provider is removed, unloaded or turned off while it is showing. See `providers/Codex.qml` and `codex/ConversationView.qml` for the bundled reference and [keystroke-calpad](https://github.com/evindor/keystroke-calpad) for a community one.

### What a view may use on `host`

The palette is the view's theme and its keyboard context. These members are part of API 1; anything else on the host object is internal and may change.

| Member | Meaning |
| --- | --- |
| `background`, `foreground`, `accent`, `muted`, `hairline` (colors), `fontFamily` (string), `compact` (bool) | The palette's theme, already resolved against the active Omarchy theme and Keystroke's appearance settings. Use them instead of `Color.menu.*` so the accent choice applies to you too. |
| `cancel()` | Close the palette (what `Esc` does). |
| `goBack()` | Leave the view and return to the results, restoring the query. What `←` and `Backspace` on an empty composer do in the bundled views. |
| `requery()` | Re-run the palette's query; relevant when your rows changed while the view was shown. |
| `statusMessage`, `errorMessage` (strings, writable) | The footer text once the user is back on the results. |
| `voice` (`active`, `phase`: `idle`/`starting`/`listening`/`transcribing`, `level` 0..1, `history` array), `voiceTrigger` (`tap`/`hold`), `voiceBegin("tap")`, `voiceStop()`, `voiceCancel()` | The dictation state, for a waveform and for forwarding keys while listening: while `voice.active`, `↵` should call `voiceStop()` and any other non-modifier key `voiceCancel()`. |
| `isModifierKey(key)`, `isSuperKey(key)` | Key classification for the hold-to-talk release. |
| `home`, `omarchyPath`, `shell`, `appLibrary`, `config` (read-only) | The same values `ctx` carries. |

The view runs inside `omarchy-shell`, so `import qs.Commons` and `import qs.Ui` work: `Style.space`, `Style.font.*`, `Style.cornerRadius`, `Util.alpha`, `Ui.Button`, `Ui.BorderSurface` and `Ui.TextField` are the kit the bundled views are made of.

## Installing from a local checkout

The Extensions screen accepts `file:///absolute/path/to/repo.git` as well as https and `owner/repo`: Omarchy's plugin scripts clone the `file` transport, which makes a local bare repository the way to try an extension in the real palette before it is published (`git clone --bare <your checkout> /tmp/thing.git`, then type the `file://` URL). Relative paths, plain paths and anything containing `..` are refused.
