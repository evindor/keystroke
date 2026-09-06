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

Omarchy loads `Service.qml` into `omarchy-shell`, injects `shell` and `manifest`, and destroys it on disable or removal. Keystroke enumerates `pluginRegistry.installedPlugins`, keeps plugins that carry `x-keystroke` and are enabled, and calls `shell.serviceFor(id)`. Re-enumeration happens on every registry change. A plugin whose service is missing, exposes no `provider`, or declares another `apiVersion` is listed under "Plugins needing attention" in Settings instead of loading. Community providers start disabled in Keystroke; the user enables them in Settings → <provider>. Complete example: [examples/keystroke-hello](../examples/keystroke-hello/).

## Provider object

```js
readonly property var provider: ({
  apiVersion: 1,
  name: "Thing", icon: "✳", iconFont: "", color: "#hex", description: "",
  prefix: "th",                 // optional, documentation only for now
  settings: [ { key, type: "boolean"|"enum"|"number"|"string", label, "default", options, min, max, integer, description } ],
  query: function(ctx) { ... return rows },       // required
  activate: function(row, ctx) { ... return effect }, // optional; defaults to row.action (row.altAction when ctx.alternate)
  opened: function() { }                          // optional; called on every summon
})
```

Bundled providers also carry `id`; community providers are keyed by their plugin id.

### ctx

`query` (string), `scope` (`""` at root, or `<key>` / `<key>/<sub>`), `sub`, `generation`, `settings` (validated values for your schema), `pending()` (call when more rows will arrive later), `host` (`host.requery()` re-runs the current query; `host.appLibrary`, `host.omarchyPath`, `host.shell`), `shell`, `appLibrary`, `omarchyPath`.

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

`catalog(ctx)` is optional. When present it returns every row the provider could ever activate (no query), in the same shape as `query()` rows plus an optional `detail` string (a breadcrumb or a category, kept short). The host feeds these rows, numbered, to the voice assistant so a spoken command can be mapped to one of them; a provider without `catalog()` is simply not on the assistant's list. `ctx` carries `host`, `settings`, `shell`, `appLibrary` and `omarchyPath`, like `query()` without the query fields.

`altAction` is optional and runs on `Ctrl+↵` (a row without one runs `action` again). Say what it does in `hint` ("ctrl ↵ terminal"). A provider's `activate(row, ctx)` receives `ctx.alternate === true` for that key so it can compute the effect itself.

`id` must be stable for a logical result: it drives in-place delegate updates and frecency. `score` orders only within the tier; omit it to use the default matcher, `Match.match(query, title, keywords, path, description)`, which is fuzzy over `title`, over `path` (the breadcrumb ending in the title, for rows that live in submenus; matched slightly below the title) and over `keywords` (identifiers a user may abbreviate: aliases, ids, config keys; matched below the path), and word-prefix only over `description` (prose). Put synonyms and sentences in `description`, not `keywords`: scattered letters would match any sentence. Rows with a zero score are dropped when the query is non-empty. A provider that owns a tree should return every descendant when the query is non-empty, with `path` relative to the current scope, so abbreviations reach deep items from the root. `remember: true` opts into frecency (never use query text as the id).

### Effects

`{type:"navigate", scope, title}` · `{type:"exec", argv}` (literal argv, login-shell env) · `{type:"shell", command}` (trusted strings only) · `{type:"copy", text}` · `{type:"url", url}` · `{type:"app", id, name}` (launch via AppLibrary) · `{type:"notify", glyph, headline, body}` · `{type:"setting", path, key, value, schema}` · `{type:"compound", actions}` · `{type:"noop"}`. The host closes the palette before anything that launches.

## Scopes and settings

Navigating into a provider gives it scope `<key>`; deeper scopes are `<key>/<sub>`. Settings are stored under `providers.<key>` in `~/.config/omarchy/keystroke.json`; the `enabled` key is reserved. Screens are generated from `settings`; no UI code is needed. Every screen, setting and enum choice is also searchable from the palette root through its breadcrumb (Keystroke Settings › <name> › <label> › <choice>); the setting `key` and enum option values count as identifiers, so a key like `provider` makes `prefp` reach a setting labelled "Preferred assistant".

## Stability

API 1 is frozen once a second community provider ships against it. Changes that add optional fields keep the version; anything else bumps `apiVersion`, and Keystroke keeps loading the previous version for one Omarchy release.
