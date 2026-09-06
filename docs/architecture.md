# Architecture

Keystroke is one Omarchy `menu` plugin. Everything runs in `omarchy-shell`'s QML engine; there is no second process while hidden and no IPC on the query path.

```text
omarchy-shell
  └─ Keystroke.qml (menu entry point, keepLoaded)
       ├─ window, keys, navigation stack, dmenu protocol, effects, config, frecency
       ├─ providers/Registry.qml
       │    ├─ bundled: OmarchyMenu, Applications, Calculator, Converter, Colors,
       │    │           Emoji, Clipboard, AiWeb, SettingsProvider
       │    └─ community: shell.serviceFor(<plugin id>) for every enabled plugin
       │                  whose manifest carries "x-keystroke"
       ├─ core/*.js   Match (fuzzy matcher + tiers), SettingsTree, Frecency, Settings, Calculator, Units, Colors, Emoji, AiTargets
       ├─ omarchy/MenuModel.js   vendored stock menu model (parse, merge, routes, guards)
       └─ ui/         ResultRow, PreviewPane, Keycap
```

## Query flow

Keystrokes debounce 16 ms, then the host calls `query(ctx)` on every enabled provider (root) or the owning provider (scoped). Providers return rows synchronously. Anything slow (guards, dynamic menu providers, the time-zone helper) returns what it has, calls `ctx.pending()`, and later calls `host.requery()`; the host re-runs the query and keeps the selection. Rows are normalized, ranked by host-owned tiers (`answer > item > fallback`), scored within a tier, and reconciled into a fixed-role `ListModel` by uid so delegates update in place while typing. Previews are read from the selected row's JS object, never copied into the model.

## Omarchy menu parity

`providers/OmarchyMenu.qml` is a port of the stock `Menu.qml` logic over the vendored `MenuModel.js`: default plus user JSONC (watched, merged per key), aliases and links through `resolveRoute`, leaf routes executed on summon, `when`/`checked` guards evaluated as one batch on load and on every open (never per query), the `fonts` (volatile) and `power-profiles` providers loaded on submenu entry or search and cached for the session, actions run through `Util.execDetached` (`bash -lc`). The `apps` submenu is the Applications provider, which uses `shell.appLibrary` for entries, hidden filters, icons, launch feedback and uninstall.

## Integration points used

All from Omarchy 4.0.2 source: property injection of `shell`, `manifest`, `pluginRegistry` (`shell.qml`), `open/close/opened` and `shell call` methods, `PluginRegistry.resolveEnabledId` and `restoreCloneSource` keyed by `omarchy.clonedFrom`, `shell.serviceFor` for service plugins, `Color.menu.*`, `Style.font.menuFamily`, `Style.space`, `Style.cornerRadius`, `Style.gapsOut`, `Border.surfaceSpec`, `BorderSurface`, `ConfirmDialog`, `PointerMoveGate`, `Util.execDetached/execArgv/alpha/fileUrl/shellQuote`. The layer namespace is `omarchy-menu` so the stock no-animation layer rule applies.

## Helpers

`helpers/timezone.py` is the only out-of-process helper. QML's JavaScript has no IANA zone data; the converter spawns the helper once per distinct time query after a regex gate matches, with a 1 s timeout, and caches the answer.

## Settings and state

`~/.config/omarchy/keystroke.json` (FileView, watched, atomic writes; `core/Settings.js` validates against provider schemas, preserves unknown fields, refuses to overwrite a file that does not parse). `~/.local/state/keystroke/usage.json` holds frecency (`core/Frecency.js`: md5 of provider/row id, decaying weights, 2000-entry cap). Enable/disable of the plugin itself stays in Omarchy's `shell.json`.

## Matching

`core/Match.js` is fzf's FuzzyMatchV2 (Smith-Waterman with affine gaps and bonuses for word starts, camelCase and digits) tuned for a palette: the per-letter score is smaller than fzf's so letters on word starts dominate, a gap never costs more than a few letters so skipping a whole breadcrumb segment is cheap, and matches below 40 % of a perfect prefix are dropped. A row is scored on up to four haystacks: its title, its breadcrumb path below the current scope (× 0.97), its identifiers such as aliases, ids and config keys (× 0.92), and its description, which is prose and only matches when every query word is a prefix of a word in it (flat 50). Query words are AND-ed in any order. Normalised scores put a whole-word prefix at 100 and an exact title at 120; providers add small constant lifts on top (actions +3, confident app matches +45) and frecency reorders within the item tier only.

Every provider that owns a tree searches all of it when a query is present: the Omarchy menu scores descendants of the active submenu against their relative breadcrumb, and `core/SettingsTree.js` flattens every settings screen, setting and enum choice into nodes with breadcrumbs so `keysepro` reaches Keystroke Settings › AI & Web Search › Preferred assistant from the root and `prefcla` selects its Claude choice directly. Prepared haystacks and joined strings are cached per distinct string, and providers cache their breadcrumbs, so a keystroke costs one DP pass per candidate; the test suite times a 700-row worst case (every row matching) at about 10 ms in the QML engine.

## Deferred

Match highlighting in rows, arbitrary provider views and a permanent publishing id.
