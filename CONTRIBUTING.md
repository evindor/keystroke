# Working on Keystroke

This file is for anyone, person or coding agent, who wants to build a Keystroke extension or change Keystroke itself. It says where things are, what the conventions are, and how to prove a change works. The provider contract proper is in [docs/providers.md](docs/providers.md); the design in [docs/architecture.md](docs/architecture.md). **To write an extension, jump to [Build an extension](#build-an-extension).**

## What Keystroke is

Keystroke is one Omarchy shell plugin (`manifest.json`, kinds `menu` and `bar-widget`) written in QML and JavaScript. It runs inside the existing `omarchy-shell` process and replaces the stock menu through `omarchy.clonedFrom: "omarchy.menu"`. Everything the palette can do is a **provider**: an object with `query(ctx)` that returns rows and, optionally, `activate(row, ctx)` that returns an effect. Bundled providers live in `providers/`, vetted and maintained as part of Keystroke; third-party providers are **extensions**, one folder each under `extensions/`, contributed through pull requests and shipped with Keystroke but off until the user turns them on.

There is no build step. The shell loads the QML files as they are.

## Repository map

| Path | What |
| --- | --- |
| `Keystroke.qml` | The palette: window, keys, navigation stack, dmenu protocol, effects, config, frecency, voice glue. `host` as providers see it. |
| `providers/*.qml` | Bundled providers. `Registry.qml` instantiates them, scans the extension folders, and creates an extension's service when it is turned on. |
| `providers/Extensions.qml` | The Extensions screen (on/off, setup, source). |
| `extensions/<id>/` | Third-party extensions, one folder each. `extensions/timer` is the reference. |
| `core/*.js` | Pure JavaScript: matcher, settings, settings tree, calculator, units, colors, emoji, files, extensions, intent. Everything testable lives here. |
| `omarchy/MenuModel.js` | Vendored stock menu model (MIT, Omarchy). Keep in sync with Omarchy, do not restyle. |
| `voice/`, `codex/` | Voice session (voxtype) and the Codex app-server integration. |
| `ui/` | Result row, preview pane, key caps, waveform. |
| `tests/` | `tst_*.qml` unit tests (qmltestrunner), `*_check.py` integration checks that drive real Quickshell components offscreen, `lint.sh`. |
| `docs/` | Contract, architecture, verification log. |
| `tools/check_extensions.py` | The checks a pull request with an extension must pass (`bin/keystroke check-extensions`). |
| `bin/keystroke` | Developer commands: `install`, `uninstall`, `validate`, `test`, `check-extensions`, `open <query>`. |

## Conventions

- **Pure logic in `core/*.js`, side effects in QML.** A provider's QML file owns processes, files and timers; the decisions (what rows to show, what argv to run, how to parse output) go in a `.pragma library` module with unit tests. See `providers/Files.qml` + `core/Files.js`, `providers/Extensions.qml` + `core/Extensions.js`.
- **Return quickly from `query`.** It runs on the UI thread for every keystroke. Cache, or start a `Process` and call `ctx.pending()` now and `host.requery()` when the result is in.
- **Stable row ids.** `id` drives in-place delegate updates and frecency. Never put query text in an id.
- **Literal argv, never shell strings**, unless the string is entirely yours (`{type:"shell"}` is for trusted constants). Pass user input as separate argv elements, after `--` where the tool supports it.
- **Confirm anything destructive or trust-expanding** with the row's `confirm` field: removals, installs, config resets, shutdown.
- **Theme tokens only.** Colors, fonts, radii and spacing come from Omarchy's `Color`, `Style`, `Border` (`import qs.Commons`). No hard-coded colors in UI; a provider's `color`/`tint` is an accent, applied through `Util.alpha`.
- **Match the house style**: two-space indent, `var`, `function` expressions, no semicolons at line ends, short comments that explain why. Keep files ASCII except glyphs from the Omarchy icon font.
- **Settings are schemas**, not UI. Declare `settings: [{ key, type, label, default, … }]` on the provider; screens, search and persistence are generated.
- **Never start a second Quickshell process, never `sudo`, never write outside `~/.config/omarchy/keystroke.json`, `~/.local/state/keystroke/` and `~/.cache/keystroke/`** without a clear, documented reason. Keystroke and its extensions run unsandboxed in the user's shell.

## Verify before you claim it works

```sh
bin/keystroke validate      # omarchy plugin validate on the checkout
bin/keystroke test          # qmltestrunner (tests/), integration checks, qmllint
```

`tests/lint.sh` prints known noise from Quickshell metadata (`PanelWindow is not creatable`, `member not found on QObject` for `Style.font.*`/`Color.menu.*`); anything else is yours. Run the unit tests offscreen: `cd tests && QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software /usr/lib/qt6/bin/qmltestrunner -input .`.

To see a change in the running shell: `bin/keystroke install` copies the checkout into `~/.config/omarchy/plugins/evindor.keystroke` (no symlinks) and enables it; because the plugin is `keepLoaded`, a code change usually needs `omarchy-restart-shell` afterwards. Drive it headlessly with `bin/keystroke open "<query>"` and `omarchy-shell shell call omarchy.menu inspect '{}'`, which prints the current rows, selection and state as JSON. Do not simulate key presses on the user's desktop as a test.

Record what you ran in `docs/verification.md` when you change behaviour, including what was *not* exercised.

## Build an extension

An extension is one folder under `extensions/` with an `extension.json` and a `Service.qml` whose root object exposes `readonly property var provider`. It ships with Keystroke once its pull request is merged, and every user sees it on the Extensions screen, **off**, until they turn it on; Keystroke creates `Service.qml` at that moment, injects `shell`, `extension` and `omarchyPath`, and reads `provider`. The reference is [extensions/timer](extensions/timer/): copy it and change what you need. The workflow, end to end:

1. Fork and clone this repository. Pick an id: lowercase letters, digits and dashes, not the name of a bundled provider (`calculator`, `files`, …). `extensions/<id>/` is the folder; the id is also the settings section and the scope key.
2. Write the extension (below). Put it where the palette can see it without reinstalling Keystroke: `ln -s "$PWD/extensions/<id>" ~/.local/share/keystroke/extensions/<id>` (a copy works too). Open the palette: the extension is listed under Extensions with a **local** badge. Turn it on there, confirm, and use it. After you edit code that was already loaded, `omarchy-restart-shell` (the shell's QML cache cannot be cleared on Quickshell 0.3.1).
3. `bin/keystroke check-extensions extensions/<id>` must pass. Open a pull request against `main` with the checklist from the template filled in. It is reviewed (by a coding agent first, then by the maintainer), merged, and ships with the next Keystroke release; your local copy keeps working in the meantime, and the shipped folder takes over when you delete the local one.

### 1. Files

```
extensions/<id>/
├── extension.json    name, version, author, description, apiVersion 1, icon, color; optional entry, homepage, license, setup
├── Service.qml       QtObject { property var shell; property var extension; readonly property var provider: ({ … }) }
├── core/Model.js     pure functions: parse the query, build rows, build argv
├── tests/tst_*.qml   qmltestrunner tests for core/ (run by check-extensions)
├── assets/           optional icon.svg and anything else the QML resolves next to itself
├── bin/setup         optional, only if the extension needs a one-off step (see Setup)
└── README.md         what it does, example queries, settings, limits and dependencies
```

```json
{
  "name": "Thing", "version": "1.0.0", "author": "Your Name",
  "description": "One line for the Extensions screen: thing 42",
  "apiVersion": 1, "icon": "󰀻", "color": "#8bceb4", "license": "MIT"
}
```

Rules, all enforced by `bin/keystroke check-extensions`: the five required fields are non-empty strings and `apiVersion` is the number 1; `entry` (default `Service.qml`) is a `.qml` file inside the folder; nothing in the folder is a symlink; no file is named `manifest.json` (an extension is not an Omarchy plugin); no `import` reaches outside the folder; `README.md` exists; a declared `setup.run` exists and is executable; qmllint reports no error; `tests/tst_*.qml` pass. Keep the folder self-contained: everything it needs is in it, or fetched by its setup script.

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

`ctx` carries `query`, `rawQuery`, `scope` (`""` at the root, your id inside your own screen, `<id>/<sub>` deeper), `settings` (validated against your schema), `patterns` (`{ matched: [ids], boost }` for the patterns you declared), `pending()`, `host`, `shell`, `appLibrary`, `omarchyPath`. Your scope key is your id (`root.extension.id`): return `{type:"navigate", scope: extension.id, title: "Thing"}` to open your screen, and answer only when `ctx.scope` is empty or yours.

**Patterns** are how an extension gets ranked for the shapes of text it understands without knowing about every other provider: declare each shape as a regular expression with a `boost`, and when one matches the query the host adds the largest boost to the score of every row you return and tells you which ids matched (`ctx.patterns.matched`). Use them to offer a `fallback` row (the *Continue with* section, where the assistant hand-offs sit at scores 2 to 5) only when a shape matched, with a base score of 1: matched, your row lands above the hand-offs; unmatched, return nothing. Give each pattern an `example`; the Extensions screen shows them. Never answer every query: a provider that puts a row under everything the user types is the first thing a reviewer will send back.

**Icon.** `icon` is a glyph from Omarchy's icon font and is always needed (put the same one in `extension.json`, which is what the Extensions screen shows before your code is loaded); `iconSource` is an optional image (SVG or PNG next to your QML, resolved with `Qt.resolvedUrl`) that replaces the glyph on your rows in Extensions and Settings. Put the same `iconSource` on the rows you return so your results carry your icon too.

Rows: `{ id, title, subtitle, icon, iconSource, tint, section, verb, tier: "answer"|"item"|"fallback", score, order, keywords, description, accessory, hint, confirm, preview, previewLabel, previewDetail, action, altAction }`. Omit `score` for non-empty queries to use the fuzzy matcher over `title`, `keywords` (identifiers) and `description` (prose, word-prefix only); give an explicit `score` for listings with an empty query. Answers (`tier: "answer"`) sort above items; use them only for computed results of an explicit request.

Effects: `navigate`, `exec` (argv), `shell` (trusted string), `copy`, `url`, `app`, `notify`, `setting`, `compound`, `close`, `noop`, and `provider-view` for an extension that ships its own screen (see below). Anything that launches closes the palette first. `noop` keeps it open; call `host.requery()` when your rows changed. Private action types are fine if `activate` translates them into one of these.

**A view of your own.** An extension that needs more than rows (a conversation, a multi-line editor) exposes `view: Component { MyView { service: root } }` on the provider and returns `{type: "provider-view", provider: extension.id}` from `activate`. The host loads the component over the palette card and injects `host`; the view draws with `host.background`, `host.foreground`, `host.accent`, `host.muted`, `host.hairline` and `host.fontFamily`, closes with `host.cancel()`, returns to the results with `host.goBack()`, and forwards voice through `host.voice`. The contract, with the full list of host members a view may rely on, is in [docs/providers.md](docs/providers.md) under *Optional provider views*; [keystroke-calpad](https://github.com/evindor/keystroke-calpad) is a complete example (patterns, image icon, a session view and an offscreen check of all three).

A service outlives the palette window: timers, sockets and caches you keep on the root object survive the window closing. The object is destroyed when the user turns the extension off, when the shell reloads its plugins and when it restarts; stop what you own in `Component.onDestruction`. Nothing of yours runs while the extension is off.

### 3. Setup, only when there is no other way

Most extensions need no setup. One that needs a local model, a compiled helper or a large download declares it in `extension.json`:

```json
"setup": { "run": "bin/setup", "summary": "Downloads the 40 MB model into ~/.local/share/keystroke/thing, verified by SHA-256" }
```

The Extensions screen then shows **Run setup**: after a confirmation that quotes the summary, it opens a visible terminal and runs the script from your folder in front of the user, who reads its output and its exit status. Nothing else ever runs it. The script must be idempotent and honest: pin what it downloads and verify a digest (see `helpers/matching-start.py`), never `curl | sh`, never `sudo`, write only under `~/.local/share/keystroke/<id>` or `~/.cache/keystroke/<id>`, and say what it is doing. Your provider decides for itself whether setup has happened (does the file exist?) and, if not, returns one disabled row saying so instead of failing.

### 4. Test it

- Unit-test `core/*.js` with qmltestrunner; `bin/keystroke check-extensions extensions/<id>` runs them, lints your QML and checks the folder. Cover parsing edge cases, argv construction (no injection), rows for the root and for your scope.
- Try it in the shell from `~/.local/share/keystroke/extensions/<id>` as described above. **Extensions → <name>** shows **Needs attention** with the QML error if `Service.qml` failed to load; `journalctl --user -u omarchy-shell -f` (or `qs log`) shows QML errors too.
- Check the palette's view of it: `omarchy-shell shell summon omarchy.menu '{"query":"thing"}'` then `omarchy-shell shell call omarchy.menu inspect '{}'`. Do not simulate key presses on the user's desktop.
- For the pull request, `tests/palette_extensions_check.py` shows how to drive the real palette offscreen with an extension folder if you want an integration check of your own.

### 5. Submit it

Open a pull request against `main` with `extensions/<id>` and nothing outside it (a change to Keystroke itself is a separate pull request). Fill in the template: what the extension does with example queries, and the checklist. Review looks for exactly what the checklist says: the folder is self-contained, every process, file, network call and download is listed in the README, nothing runs before the user turns the extension on, nothing runs on every keystroke that the README does not explain, and the code is yours or attributed. Bump `version` in `extension.json` for every user-visible change in later pull requests; there is no separate publishing step, the next Keystroke release carries it.

## Contribute to Keystroke itself

- **A new bundled provider**: add `providers/<Name>.qml` with `id`, `name`, `icon`, `color`, `description`, `settings`, `query`; register it in `providers/Registry.qml` (`bundled` list, in display order); put logic in `core/<Name>.js` with `tests/tst_<name>.qml`; document it in `README.md` (Using it) and `docs/architecture.md`. Bundled providers default to enabled.
- **A change to the contract** (`docs/providers.md`): adding an optional field keeps `apiVersion: 1`; anything that changes the meaning of an existing field bumps it, and `Registry.qml` must keep loading the previous version for one Omarchy release.
- **The host** (`Keystroke.qml`): new effects go in `perform()`, new keys in the search field's `Keys.onPressed`, new IPC methods next to `ping()`/`inspect()`. Keep the dmenu protocol byte-compatible with Omarchy's `omarchy-menu-select`/`omarchy-menu-input`.
- **Omarchy vendored code** (`omarchy/MenuModel.js`): only sync with upstream, never fork behaviour.
- Commit messages: one line in the imperative, then why. Update `docs/verification.md` with what you ran.

## Security and trust

Keystroke and its extensions run unsandboxed with the user's permissions. The line that keeps that acceptable is drawn at the switch: an extension that is off is never compiled, never instantiated and never asked anything, so installing or updating Keystroke runs no third-party code, and turning one on is an explicit, confirmed action that names the folder. A setup script runs only in a terminal the user opened for it. Reviewing pull requests is the other half: `tools/check_extensions.py` catches the mechanical problems, the checklist in the template names the behavioural ones, and a maintainer reads every extension before it ships. Keep it that way: no auto-enabling, no code fetched at runtime, no work before the switch.
