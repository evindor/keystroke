# Working on Keystroke

This file is for anyone who wants to build a Keystroke extension or change Keystroke itself. It says where things are, what the conventions are, and how to prove a change works. The provider contract proper is in [docs/providers.md](docs/providers.md); the design in [docs/architecture.md](docs/architecture.md).

## What Keystroke is

Keystroke is one Omarchy shell plugin (`manifest.json`, kinds `menu` and `bar-widget`) written in QML and JavaScript. It runs inside the existing `omarchy-shell` process and replaces the stock menu through `omarchy.clonedFrom: "omarchy.menu"`. Everything the palette can do is a **provider**: an object with `query(ctx)` that returns rows and, optionally, `activate(row, ctx)` that returns an effect. Bundled providers live in `providers/`; community providers are separate Omarchy plugins ("extensions") that Keystroke discovers at runtime.

There is no build step. The shell loads the QML files as they are.

## Repository map

| Path | What |
| --- | --- |
| `Keystroke.qml` | The palette: window, keys, navigation stack, dmenu protocol, effects, config, frecency, voice glue. `host` as providers see it. |
| `providers/*.qml` | Bundled providers. `Registry.qml` instantiates them and discovers community ones. |
| `providers/Extensions.qml` | The in-palette extension manager (install, update, remove, on/off). |
| `core/*.js` | Pure JavaScript: matcher, settings, settings tree, calculator, units, colors, emoji, files, extensions, intent. Everything testable lives here. |
| `omarchy/MenuModel.js` | Vendored stock menu model (MIT, Omarchy). Keep in sync with Omarchy, do not restyle. |
| `voice/`, `codex/` | Voice session (voxtype) and the Codex app-server integration. |
| `ui/` | Result row, preview pane, key caps, waveform. |
| `tests/` | `tst_*.qml` unit tests (qmltestrunner), `*_check.py` integration checks that drive real Quickshell components offscreen, `lint.sh`. |
| `docs/` | Contract, architecture, verification log. |
| `examples/keystroke-hello/` | The smallest possible extension. |
| `extensions/index.json` | The curated index of known extensions the Extensions screen fetches. |
| `bin/keystroke` | Developer commands: `install`, `uninstall`, `validate`, `test`, `open <query>`, `voice-setup`. |

## Conventions

- **Pure logic in `core/*.js`, side effects in QML.** A provider's QML file owns processes, files and timers; the decisions (what rows to show, what argv to run, how to parse output) go in a `.pragma library` module with unit tests. See `providers/Files.qml` + `core/Files.js`, `providers/Extensions.qml` + `core/Extensions.js`.
- **Return quickly from `query`.** It runs on the UI thread for every keystroke. Cache, or start a `Process` and call `ctx.pending()` now and `host.requery()` when the result is in.
- **Stable row ids.** `id` drives in-place delegate updates and frecency. Never put query text in an id.
- **Literal argv, never shell strings**, unless the string is entirely yours (`{type:"shell"}` is for trusted constants). Pass user input as separate argv elements, after `--` where the tool supports it.
- **Confirm anything destructive or trust-expanding** with the row's `confirm` field: removals, installs, config resets, shutdown.
- **Theme tokens only.** Colors, fonts, radii and spacing come from Omarchy's `Color`, `Style`, `Border` (`import qs.Commons`). No hard-coded colors in UI; a provider's `color`/`tint` is an accent, applied through `Util.alpha`.
- **Match the house style**: two-space indent, `var`, `function` expressions, no semicolons at line ends, short comments that explain why. Keep files ASCII except glyphs from the Omarchy icon font.
- **Settings are schemas**, not UI. Declare `settings: [{ key, type, label, default, … }]` on the provider; screens, search and persistence are generated.
- **Never start a second Quickshell process, never `sudo`, never write outside `~/.config/omarchy/keystroke.json`, `~/.local/state/keystroke/` and `~/.cache/keystroke/`** without a clear, documented reason. Plugins run unsandboxed in the user's shell.

## Verify before you claim it works

```sh
bin/keystroke validate      # omarchy plugin validate on the checkout
bin/keystroke test          # qmltestrunner (tests/), integration checks, qmllint
```

`tests/lint.sh` prints known noise from Quickshell metadata (`PanelWindow is not creatable`, `member not found on QObject` for `Style.font.*`/`Color.menu.*`); anything else is yours. Run the unit tests offscreen: `cd tests && QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software /usr/lib/qt6/bin/qmltestrunner -input .`.

To see a change in the running shell: `bin/keystroke install` copies the checkout into `~/.config/omarchy/plugins/evindor.keystroke` (no symlinks) and enables it; because the plugin is `keepLoaded`, a code change usually needs `omarchy-restart-shell` afterwards. Drive it headlessly with `bin/keystroke open "<query>"` and `omarchy-shell shell call omarchy.menu inspect '{}'`, which prints the current rows, selection and state as JSON. Do not simulate key presses on the user's desktop as a test.

Record what you ran in `docs/verification.md` when you change behaviour, including what was *not* exercised.

## Build an extension

An extension is an ordinary Omarchy plugin of kind `service` whose manifest carries `"x-keystroke": { "apiVersion": 1 }` and whose `Service.qml` root object exposes `readonly property var provider`. Omarchy installs, loads, updates and removes it; Keystroke only reads `provider`. The complete reference is [keystroke-timer](https://github.com/evindor/keystroke-timer); use it as a template.

### 1. Files

```
my-extension/
├── manifest.json     kinds ["service"], keepLoaded true, entryPoints.service "Service.qml", x-keystroke marker
├── Service.qml       QtObject { property var shell; property var manifest; readonly property var provider: ({ … }) }
├── core/Model.js     pure functions: parse the query, build rows, build argv
├── tests/tst_*.qml   qmltestrunner tests for core/
├── bin/test          runs the tests, `omarchy plugin validate .`, qmllint
├── README.md         install, use, settings, remove, limits and dependencies
├── LICENSE           MIT or compatible
└── preview.png       optional, shown by the marketplace
```

Manifest rules (enforced by `omarchy plugin validate` and the marketplace): `schemaVersion` exactly `1`; `id` lowercase, globally unique, namespaced (`io.github.<you>.<name>` is the convention), never `omarchy.*`; `name`, `version`, `author`, `description` non-empty strings; every kind has its entry point and the file exists; no symlinks anywhere in the folder. Put the word **Keystroke** in the name or description: that is how the palette's marketplace search recognises an extension, since the marketplace catalog does not carry manifests.

### 2. The provider object

```js
readonly property var provider: ({
  apiVersion: 1,
  name: "Thing", icon: "󰀻", iconSource: String(Qt.resolvedUrl("assets/thing.svg")), color: "#8bceb4",
  description: "One line for Settings and the Extensions screen",
  patterns: [ { id: "amount", regex: "^\\s*[$€]\\s*\\d", boost: 12, example: "$120 - 30%" } ],   // optional
  settings: [ { key: "limit", type: "number", label: "Results", "default": 10, min: 1, max: 50, integer: true } ],
  query: function(ctx) { return Model.rows(ctx.query, ctx.scope, ctx.settings, ctx.patterns, state) },
  activate: function(row, ctx) { /* do work, then */ return row.action },   // optional
  opened: function() { }                                                     // optional: every summon
})
```

`ctx` carries `query`, `rawQuery`, `scope` (`""` at the root, your plugin id inside your own screen, `<id>/<sub>` deeper), `settings` (validated against your schema), `patterns` (`{ matched: [ids], boost }` for the patterns you declared), `pending()`, `host`, `shell`, `appLibrary`, `omarchyPath`. Your scope key is your plugin id: return `{type:"navigate", scope: manifest.id, title: "Thing"}` to open your screen, and answer only when `ctx.scope` is empty or yours.

**Patterns** are how an extension gets ranked for the shapes of text it understands without knowing about every other provider: declare each shape as a regular expression with a `boost`, and when one matches the query the host adds the largest boost to the score of every row you return and tells you which ids matched (`ctx.patterns.matched`). Use them to offer a `fallback` row (the *Continue with* section, where the assistant hand-offs sit at scores 2 to 5) only when a shape matched, with a base score of 1: matched, your row lands above the hand-offs; unmatched, return nothing. Give each pattern an `example`; the Extensions screen shows them.

**Icon.** `icon` is a glyph from Omarchy's icon font and is always needed; `iconSource` is an optional image (SVG or PNG next to your QML, resolved with `Qt.resolvedUrl`) that replaces the glyph on your rows in Extensions and Settings. Put the same `iconSource` on the rows you return so your results carry your icon too.

Rows: `{ id, title, subtitle, icon, iconSource, tint, section, verb, tier: "answer"|"item"|"fallback", score, order, keywords, description, accessory, hint, confirm, preview, previewLabel, previewDetail, action, altAction }`. Omit `score` for non-empty queries to use the fuzzy matcher over `title`, `keywords` (identifiers) and `description` (prose, word-prefix only); give an explicit `score` for listings with an empty query. Answers (`tier: "answer"`) sort above items; use them only for computed results of an explicit request.

Effects: `navigate`, `exec` (argv), `shell` (trusted string), `copy`, `url`, `app`, `notify`, `setting`, `compound`, `close`, `noop`, and `provider-view` for an extension that ships its own screen (see below). Anything that launches closes the palette first. `noop` keeps it open; call `host.requery()` when your rows changed. Private action types are fine if `activate` translates them into one of these.

**A view of your own.** An extension that needs more than rows (a conversation, a multi-line editor) exposes `view: Component { MyView { service: root } }` on the provider and returns `{type: "provider-view", provider: manifest.id}` from `activate`. The host loads the component over the palette card and injects `host`; the view draws with `host.background`, `host.foreground`, `host.accent`, `host.muted`, `host.hairline` and `host.fontFamily`, closes with `host.cancel()`, returns to the results with `host.goBack()`, and forwards voice through `host.voice`. The contract, with the full list of host members a view may rely on, is in [docs/providers.md](docs/providers.md) under *Optional provider views*; [keystroke-calpad](https://github.com/evindor/keystroke-calpad) is a complete community example (patterns, image icon, a session view and an offscreen check of all three).

A service outlives the palette: timers, sockets and caches you keep on the root object survive the window closing and are destroyed only when the plugin is disabled, removed or the shell restarts. Stop what you own when that happens (`Component.onDestruction`).

### 3. Test it

- Unit-test `core/*.js` with qmltestrunner (`bin/test`). Cover parsing edge cases, argv construction (no injection), rows for the root and for your scope.
- Validate: `omarchy plugin validate .` must pass; lint: `qmllint -I /usr/lib/qt6/qml Service.qml`.
- Try it in the shell: copy the folder to `~/.config/omarchy/plugins/<id>` (copy, not symlink), `omarchy-shell shell rescanPlugins`, `omarchy plugin enable <id>`, then in Keystroke open **Extensions → <name>** and turn **Enabled** on. `omarchy plugin list` shows the plugin; `journalctl --user -u omarchy-shell -f` (or `qs log`) shows QML errors. To go through the palette's own installer instead, `git clone --bare <your checkout> /tmp/<id>.git` and type `file:///tmp/<id>.git` on the Extensions screen: the install, update and remove rows then behave exactly as they will for the published repository.
- Check the palette's view of it: `omarchy-shell shell summon omarchy.menu '{"query":"thing"}'` then `omarchy-shell shell call omarchy.menu inspect '{}'`.

### 4. Publish it

1. Push the repository to GitHub, public, with `manifest.json`, `README.md` and `LICENSE` at the root and, ideally, a `preview.png`.
2. Confirm `omarchy plugin add https://github.com/<you>/<repo>.git --enable` works on a clean machine and `omarchy plugin remove <id>` cleans up.
3. Submit it to the Omarchy marketplace: open the [plugin submission form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=submit-plugin.yml) (or follow the [CLI guide](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md)). Category **Productivity** and tags such as `launcher`, `quickshell` fit most extensions. The marketplace runs a static baseline on the exact commit: avoid `curl | sh`, unpinned `git` installs, `sudo`, and service units unless you document them. Approval is for listing, not a security review.
4. Add it to Keystroke's index: open a pull request against this repository adding an entry to [extensions/index.json](extensions/index.json) (`id`, `name`, `description`, `author`, `repo`, `tags`). Extensions in the index appear on the Extensions screen at once; marketplace listings appear once the catalog picks them up, as long as they mention Keystroke.

### 5. Version it

Bump `version` in `manifest.json` for every user-visible change and commit it; `omarchy plugin update` fast-forwards to the default branch, validates the manifest, and rolls back if validation fails. Keystroke's Extensions screen shows "Update available" when the remote HEAD differs from the installed commit. Keep the default branch releasable.

## Contribute to Keystroke itself

- **A new bundled provider**: add `providers/<Name>.qml` with `id`, `name`, `icon`, `color`, `description`, `settings`, `query`; register it in `providers/Registry.qml` (`bundled` list, in display order); put logic in `core/<Name>.js` with `tests/tst_<name>.qml`; document it in `README.md` (Using it) and `docs/architecture.md`. Bundled providers default to enabled.
- **A change to the contract** (`docs/providers.md`): adding an optional field keeps `apiVersion: 1`; anything that changes the meaning of an existing field bumps it, and `Registry.qml` must keep loading the previous version for one Omarchy release.
- **The host** (`Keystroke.qml`): new effects go in `perform()`, new keys in the search field's `Keys.onPressed`, new IPC methods next to `ping()`/`inspect()`. Keep the dmenu protocol byte-compatible with Omarchy's `omarchy-menu-select`/`omarchy-menu-input`.
- **Omarchy vendored code** (`omarchy/MenuModel.js`): only sync with upstream, never fork behaviour.
- Commit messages: one line in the imperative, then why. Update `docs/verification.md` with what you ran.

## Security and trust

Extensions and Keystroke itself run unsandboxed with the user's permissions. The Extensions screen makes that explicit before every install and removal, uses Omarchy's own scripts (which refuse git transport helpers, validate manifests and reject symlinks), and never runs anything from a catalog without the user's confirmation. Keep it that way: no auto-install, no auto-update without an explicit action, no code fetched at runtime.
