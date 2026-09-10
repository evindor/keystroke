> Historical checkpoints below include retired local-model and forked-Voxtype implementations. Current build: [Codex integration verification](codex-integration-verification.md).

## Release 1.4.1 (2026-09-11)

- Documentation only: `site/guide/index.html` copy pass (32 replacements:
  every heading except the four kept on purpose, the hero, two asides) after
  the user's review of 1.4.0's guide. `manifest.json` 1.4.0 → 1.4.1; no other
  file under the plugin changes. `python3 site/check.py` passes (2 pages, 199
  references, 35 screenshots); `tst_settingstree` and the full QML suite are
  unchanged from the 1.4.0 run. Not exercised: nothing new to exercise.

## Release 1.4.0 (2026-09-11)

- Release tree: 1.3.0 plus the in-repo extensions, the Translate extension,
  the Timer sound and bar countdown, the bar widget sizing fix, declared
  commands with Tab as a space, the route fallback, and this release's own
  additions: the **Learn Keystroke** row (`core/SettingsTree.js`, a `url`
  effect to the guide; `tst_settingstree.qml` covers it from the root, from
  Settings and by the words learn, guide and help), the usage guide
  (`site/guide/index.html`) and the offscreen screenshot harness.
- `tools/showcase/offscreen.py` renders the real `Keystroke.qml` under
  Quickshell's offscreen platform at `QT_SCALE_FACTOR=4` (a 640x540 card
  grabbed as the 2560x2160 PNG `site/check.py` expects) in a fake HOME
  holding demo files, a demo clipboard history, `keystroke.json` with Timer
  and Translate on, and a symlink to `~/.local/state/omarchy/current` so the
  captures wear the desktop's current theme; a fake `curl` answers Translate
  from a table, `wl-paste` finds no selection, and a fake `OMARCHY_PATH`
  whose `omarchy-menu-keybindings` prints twelve demo binds in the script's
  record format feeds the Hotkeys provider. 32 scenes drive the real palette
  (queries, scopes, `activateAt` for the confirmations and the Translate
  editor, `ctrlHeld` for the numbered rows, the Timer service's own
  `activate` for the running countdowns) and three staged states (apps,
  Codex, voice) come from the `prepare.py` fixture palette, which gained a
  `KEYSTROKE_SHOWCASE_DEST`/`HOME` override and an `approvalDetail` stub
  the conversation view now calls. The Timer countdown in the bar is the
  real `BarWidget.qml` against the fake bar from
  `palette_extensions_check.py`, saved as `bar-timer.png` (the preflight
  accepts `bar-*` strips at any wide size). All 35 PNGs were looked at on
  contact sheets; the settings screen shows the config path under `~`
  through a harness-only patch of the copied `SettingsTree.js`.
- Seen while capturing, not changed: with Translate on, `5 miles in km`
  also offers a translation into Khmer, because `km` is a language code and
  the natural `… in <language>` form matches; the Converter answer still
  ranks first. Two-letter unit symbols that are also language codes are a
  Translate follow-up. The guide uses `5 miles in kilometers`.
- `python3 site/check.py` walks both pages, resolves `guide/` and `../` to
  their index pages and checks anchors across pages: PASS, 2 pages, 199
  references, 35 screenshots. `node --check site/script.js` passes; the
  lightbox now reads the clicked image's own path so it works from
  `guide/`. Both pages were rendered headless in Chromium at 1400 px and
  looked at. `.github/workflows/pages.yml` copies `site/guide` too.
- Full offscreen `bin/keystroke test` on the release tree: 162 QML tests,
  the application, file, catalog, matching session, palette matching,
  shortcut, route, motion, dictation, extensions and commands checks, the
  matching worker and engine checks, voice, clipboard, Codex, 48 time-zone
  cases, the extension review checks for Timer and Translate, the hotkey
  check and qmllint (the existing metadata warnings only) all pass.
  `omarchy plugin validate` passes.
- Not exercised: the release plugin on the live desktop (per practice,
  offscreen only; the user checks the installed palette), the `Learn
  Keystroke` row opening a real browser, the GitHub Pages deployment (it
  runs on the push to `main`).

## Timer 1.2.1: the Bell sound is called Drop (2026-09-10)

- The `sound` option `bell` is renamed `drop` (label Drop), still the
  freedesktop `bell.oga`; a saved `bell` falls back to the default Chime
  through the schema validation. Unit tests and `check-extensions` pass.

## Declared commands: hint line, placeholders, usage (2026-09-10)

- Providers declare their typed triggers (`commands`: prefix, title, summary,
  positional args with hints, examples) in `extension.json` or on the provider
  object; `core/Commands.js` compiles them, builds the index with the user's
  prefixes (`providers.<id>.prefix`, a reserved setting listed first on the
  settings screen), matches the query (longest prefix wins, sigils attach and
  are exclusive), computes the placeholders after the caret and the hint line,
  and builds the rows for the `/` screen, the name suggestions and an
  extension's Usage section. The host routes a matched query to its owner with
  `ctx.command = { id, prefix, rest, args }` and a boost of 20, asks no other
  provider (a typed command is exclusive; this generalises the old `~` special
  case and keeps other providers' fuzzy matches on the prefix out of the
  list), scores rows against the rest, adds the `query`
  effect, Tab completion, the sheen over a recognised prefix (Motion tier
  `sheen`), and says what to type when an extension is turned on. Emoji,
  Files, Timer and Translate migrated to `ctx.command.rest` with their old
  checks kept as fallbacks; Translate's prefix pattern is gone.
- `tests/tst_commands.qml` (12 tests): compile and its rejections, prefix
  rules, usage strings, the index and conflicts, matching (case, whitespace,
  sigils, longest prefix), placeholders following the caret including the
  rest argument, the ghost with a leading space after a bare prefix, the hint
  line, help and suggestion rows, usage rows and the enable notice.
  `tests/tst_extensions.qml` covers commands in the manifest and the Usage
  rows on the detail screen. All 161 palette unit tests pass; both extension
  checks pass.
- `tests/palette_commands_check.py` (real `Keystroke.qml` offscreen, fake
  curl): the empty root's row and index; `tr` recognised live with hint and
  ghost before any query runs; Tab adding the space after the prefix and
  after the first argument, doing nothing on the last argument, with a
  trailing space or after a sigil; the ghost and hint
  following the caret through `tr fr ` and `tr fr hello`; `timer 10m tea`
  routed through `ctx.command`; `tm 10m tea` after renaming the prefix in
  keystroke.json; `:smi` answered by Emoji alone; `/` listing every command
  with the renamed prefix and `/tr` filtering; `trans` suggesting Translate
  and Tab typing `tr `; the Translate screen starting with `tr [to] <text>`,
  a runnable `tr bonjour`, the Prefix row; the Timer screen showing
  `tm <duration> [name]` while off and the enable notice naming it; the Prefix
  setting under Keystroke Settings › Timer. With `KEYSTROKE_CAPTURE_DIR` set it
  saves PNGs of the ghost, the `/` screen and a Usage screen; all three were
  looked at. `palette_extensions_check.py`, `palette_matching_check.py` (its
  fixture now declares the `~` command), route, shortcut, motion, dictation,
  catalog, files, applications, hotkeys and the Translate check all pass.
- Not exercised: the sheen on the desktop (transient; offscreen it runs
  through the same NumberAnimation), typing on a real keyboard (the check
  drives `setQuery` and `completeCommand`), calpad (external; its `=` keeps
  working through its own pattern until it declares a command).

## Translate extension (2026-09-10)

- `extensions/translate` ports the Raycast google-translate extension onto
  the in-repo extension system: keyless calls to the translate.google.com
  page endpoint through `curl` (no `tk` token: verified not validated for
  `client=dict-chrome-ex`), `tr bonjour` / `tr fr …` / `… to english`
  grammar as `patterns`, the same-language fallback and the reverse
  translation, a target picker scope instead of 250-option enums, an editor
  view with dictation, selection rows that deliver after the palette closed,
  a 350 ms debounce, a session cache, superseded requests killed, HTTP 429
  backed off for a minute. Paste goes through wl-copy plus Shift+Insert like
  the palette's own dictation.
- `tests/tst_translate.qml` (14 tests, offline): language resolution and the
  ambiguous-code rule, the grammar, the pattern examples, curl argv (GET,
  POST past 2 KB, proxy, no token, user text never in a command string), the
  parser over nine bodies captured from the live endpoint on 2026-09-10
  (`tests/Fixtures.js`: phrase, Japanese romanisation, single-word
  dictionary, spelling correction, auto-correction, same language,
  Ukrainian, multi-sentence, 2.7 KB POST), the request chain after the
  detected language lands, ordering and fallback, view blocks, rows at the
  root, in scope, with answers, with a correction, the picker, the settings
  schema. `bin/keystroke check-extensions extensions/translate` passes.
- `extensions/translate/tests/palette_check.py` drives the real
  `Keystroke.qml` offscreen with a fake `curl`, `wl-paste`, `wl-copy`,
  `wtype` and notification script on PATH: off until switched on; `tr hello
  world` yields the answer row, the reverse row and the follow-ups from
  exactly three requests in order (auto→en, auto→fr, fr→en); the editor view
  opens with the text; the root offers the selection; the scoped screen's
  "Copy the translated selection" closes the palette and wl-copy receives
  "Good day" with a notification; a 429 shows the back-off row; the picker
  adds German through a setting the service picks up; turning the extension
  off destroys the service. With `KEYSTROKE_CAPTURE_DIR` set it also saves
  PNGs of the rows, the view, the scoped screen and the picker; all four were
  looked at.
- Live endpoint probes (curl, this machine): GET and POST both HTTP 200 with
  the indices documented in the spec; `translate_tts` streams audio/mpeg. Not
  exercised live: the palette on the desktop (per practice, offscreen only),
  Shift+Insert paste into a real app, `mpv` playback, dictation into the
  editor, the `setQuery` retry of a spelling correction.
## Timer sound and a countdown in the bar (2026-09-10)

- Host API, optional under API 1: `host.setBarItem(id, { text, tooltip,
  payload })` keeps one item per loaded, enabled provider on
  `Keystroke.barItems`/`barList` (pruned on every registry and config
  change, so nothing outlives an extension that is turned off);
  `host.providerSettings(id)` returns a provider's validated settings for a
  service that needs them outside a query. `BarWidget.qml` finds the
  keepLoaded palette through `shell.panelLoaders[moduleName].item`, binds
  its `barList`, and draws each item as a `WidgetButton` after the menu
  button; a press summons `omarchy.menu` with the item's payload. Text
  items are hidden on a vertical bar, like Omarchy's own.
- `bin/keystroke install` and `enable` now run `omarchy plugin enable
  evindor.keystroke left --index 0`. Omarchy's registry replaces the stock
  menu button in place when it is in the bar and leaves Keystroke where it
  is when it already sits there; the placement only matters for a fresh
  insert, which without it landed after `omarchy.workspaces` (the
  registry's left-section anchor) instead of first. `omarchy plugin add
  --enable` asks for a section only, so the README names `omarchy bar move`
  for that path.
- Timer 1.2.0: settings `sound` (off/chime/bell/alarm, default chime, the
  freedesktop sound theme that libcanberra brings in), `soundFile` (custom
  path, `~` expanded) and `showInBar` (default on). The sound argv is
  `bash -c '<script>' keystroke-timer-sound <path>`: the file is checked and
  `pw-play`, then `mpv`, then `paplay` is used, with the path only ever in
  `$1`. `sndfile-info` confirms libsndfile decodes the `.oga` files, so
  `pw-play` plays them. The service publishes the soonest countdown on start,
  cancel, every tick and every config change (a `Connections` on
  `host.configChanged`), and clears it on destruction.
- `tests/palette_extensions_check.py` (real `Keystroke.qml` and the real
  `BarWidget.qml` against a fake bar, offscreen): the bar list is empty
  before a start; activating `timer 10m tea` through the service puts
  `󰔛 10:00` with the Timers payload and a tooltip on it at once; the widget
  shows it after the menu glyph; pressing it runs `omarchy-shell shell
  summon omarchy.menu '{"scope":"timer","title":"Timers"}'`; items from
  other enabled providers are accepted, empty text and unknown providers
  are not; the item survives another extension turning off and goes when
  the timer is turned off. The timer is started through the service's own
  `activate`, not the palette's, so no desktop notification is sent.
- `extensions/timer/tests/tst_timer.qml` (+2 tests): sound paths and argv
  (off is silent even with a custom file, a path with quotes and `$(…)`
  stays a positional parameter) and the bar item (soonest timer first,
  `+n` for the rest, tooltip, payload).
- Regression found live: the first `BarWidget.qml` anchored its Row to the
  widget's height while the widget took its implicit height from the Row,
  and the bar showed no menu button at all (the widget measured 0x0, no
  error in the shell log). The Row now sizes from the buttons' implicit
  sizes and nothing reads the widget's size back. The check hosts the
  widget in a `Window` (positioners lay out on polish, which needs one) and
  asserts 27x30 with the menu button alone and a wider widget once the
  countdown is there.
- Ran: `bin/keystroke check-extensions` (ok), `tests/lint.sh` (no new
  warnings beyond the pre-existing QObject member ones), the 148 QML tests,
  `tests/palette_extensions_check.py` (PASS). Not driven on the live
  desktop; the sound was not played.

## Extensions ship inside Keystroke (2026-09-10)

- Extensions moved from separate Omarchy plugins (git-installed into
  `~/.config/omarchy/plugins`, discovered from a hosted index and the
  marketplace catalog) to folders under `extensions/` in this repository,
  reviewed through pull requests, plus `~/.local/share/keystroke/extensions`
  for local work. `core/Extensions.js` shrank from the install/update/remove
  job protocol to the folder scan, the listing and the screen rows;
  `providers/Extensions.qml` from 292 lines to 75. `extensions/timer` is the
  ported keystroke-timer, key `timer`; `examples/` and `extensions/index.json`
  are gone.
- Security property verified offscreen (`tests/palette_extensions_check.py`,
  real `Keystroke.qml`): with no switch in keystroke.json, three extensions
  are listed but `registry.services` is empty and a broken `Service.qml` is
  not reported, because it was never compiled; after `providers.<id>.enabled:
  true` the probe is created with `extension` (id, dir, source) and
  `omarchyPath` injected and answers `probe tea`, the shipped timer answers
  `timer 10m tea`, the broken one is reported with the QML error; turning the
  switch off destroys the service and the listing stays. The Enabled row of
  an extension that is off carries a confirmation naming its folder.
- `tests/tst_extensions.qml` (12 tests): scan parsing and every rejection
  message, local-over-builtin replacement, placeholder entries, listing,
  screen and detail rows, the setup argv with single-quoted arguments, scope
  ids. `tests/tst_settingstree.qml` updated to the extension entry shape.
- `tools/check_extensions.py` (`bin/keystroke check-extensions`) passes on
  `extensions/timer`: extension.json fields, folder-local imports resolved
  by path, no symlinks, no manifest.json, README, qmllint, qmltestrunner.
  `.github/workflows/extensions.yml` runs it with `--qt auto` on pull
  requests; that job was not executed here (no CI run from a worktree).
- The confirmation for turning an extension on is Keystroke's own
  `ui/ConfirmSheet.qml` (the shell's dialog with a muted note under the
  question), rendered offscreen with the Timer text. A first version carried
  a link to the source folder; it was removed because opening it moves focus
  away from the palette, which cannot survive that, so the note now says the
  code runs at the user's own risk and recommends checking it first. The
  Enabled rows on the Extensions screen and under Settings carry
  `confirmDetail` (unit-tested; the offscreen harness checks the local probe
  names its own folder).
- Not exercised: the Run setup row against a real terminal (no shipped
  extension declares one; the argv is unit-tested), and the live palette
  (the patched plugin was not installed over the user's copy).

## Disabled provider routes (2026-09-09)

- Reproduced on Omarchy 4.0.3-1 with Keystroke 1.3.0: an `omarchy-menu
  toggle apps` binding opened the Applications scope while
  `providers.applications.enabled` was false. The route was accepted before
  provider filtering removed Applications, leaving a generic empty state;
  Backspace returned to the populated root palette.
- Direct routes now verify their target after resolving it. A disabled target
  falls back to root and reports that the provider is disabled in Keystroke
  Settings; enabled routes retain their existing scoped behaviour.
- `tests/palette_route_check.py` drives the real palette offscreen and covers
  both states. It fails against `v1.3.0` at the disabled-route assertion and
  passes on this tree. Full `bin/keystroke test` passes: 149 QML tests and all
  integration checks, including the new palette route check. `bin/keystroke
  validate` and `git diff --check` pass; qmllint reports only the existing
  metadata warnings. The patched plugin was not installed over the user's
  release copy and the fallback was not exercised in a live shell.

## Release 1.3.0 (2026-09-10)

- Root cause of "installed extension never appears": omarchy-shell gives a
  third-party plugin `PluginRegistryApi` (`shell.qml` `pluginRegistryFor`),
  whose `installedPlugins` holds only the plugin's own manifest, and a
  `serviceFor` scoped by `pluginOwnsTarget` to the plugin's own id. Confirmed
  in the journal by the `onPluginsChanged` "no signal of the target matches"
  warning from `providers/Registry.qml` and `providers/Extensions.qml`: the
  facade has no such signal, the real `PluginRegistry` does. Keystroke's
  `clonedFrom: omarchy.menu` inherits no capabilities (`omarchy.menu` declares
  none) and no capability grants cross-plugin service access.
- `providers/Registry.qml` now scans the plugin folder (`core/Extensions.js`
  `scanArgv`/`parseScan`) and creates services with `Qt.createComponent`,
  injecting `shell`, `manifest`, `omarchyPath`. `providers/Extensions.qml`
  reads `host.registry.manifests`/`problems`; install drops `--enable`; the
  shell-side switch and `op("load")` are gone; an installed extension defaults
  to on. Job protocol fixed: a job ends when its result is read (or both files
  are confirmed absent), results are finished once per instance, the next
  wrapper removes the previous result, chained checks are quiet.
- Measured on Quickshell 0.3.1: `typeof Qt.clearComponentCache` is
  `undefined`, `Qt.createComponent` returns the cached component after the
  file changed, and a `?v=` query on the URL reloads the `.qml` but not its JS
  imports. The update status therefore advises `omarchy-restart-shell`; the
  trick is not used.
- Full offscreen `bin/keystroke test` on the release tree: 149 QML tests
  (`tst_extensions` covers the scan parser, `serviceUrl` escaping,
  `publicManifest`, the problem rows and the argv without `--enable`), the
  application, file, catalog, matching session, palette matching, shortcut,
  motion and dictation checks, the matching worker and engine checks, voice,
  clipboard, Codex, 48 time-zone cases, `tests/extensions_check.py` end to end
  (its registry stub now uses the real scan and parser; it asserts the install
  writes nothing to keystroke.json, that no "loaded" row exists, and the
  restart advice after an update), the new `tests/palette_extensions_check.py`
  (real `Keystroke.qml`, fake HOME: working, broken, misnamed and unmarked
  folders) and the hotkeys check passed. `tests/lint.sh` exits 0 with 206
  warning lines, the same count as the `v1.2.1` tree. `bin/keystroke validate`,
  `git diff --check`, `site/check.py` and `node --check site/script.js` pass.
- Live on Omarchy 4.0.3-1: after `bin/keystroke install` the rescan alone kept
  running the old code (cache, above); after `omarchy-restart-shell`,
  `omarchy-shell shell call omarchy.menu inspect '{}'` lists
  `io.github.evindor.keystroke-timer` among the providers with no problems.
  The stale `shell.json` `plugins[]` entry was removed with
  `omarchy plugin disable`. See [release notes](releases/v1.3.0.md).

## Release 1.2.1 (2026-09-09)

- Hotfix release for Omarchy 4.0.3: the scoped-shell revocation recorded below
  and the `keepLoaded` restore from `1dc4e48`. Manifest bumped to 1.2.1.
- Full offscreen suite on the release tree (`QT_QPA_PLATFORM=offscreen`,
  `QT_QPA_PLATFORMTHEME=generic`, `QT_QUICK_BACKEND=software`): 148 QML tests,
  the application (now covering revocation), file, catalog, matching session,
  palette matching, shortcut and motion checks, the matching worker and engine
  checks, voice, clipboard, Codex, dictation, 48 time-zone cases and the hotkeys
  check against the live `omarchy-menu-keybindings` passed. `tests/lint.sh`
  exits 0 with 206 warning lines, the same count on the `v1.2.0` tree.
  `bin/keystroke validate`, `git diff --check`, `site/check.py` and
  `node --check site/script.js` pass.
- `tests/extensions_check.py` stops at the same "update applied" race recorded
  for 1.2.0; every other step of that check passes.
- Live desktop check on Omarchy 4.0.3-1: installed from this tree, shell
  restarted, the Applications screen rendered all 73 rows with icons.
  See [release notes](releases/v1.2.1.md).

## Release 1.2.0 (2026-09-09)

- Full offscreen `bin/keystroke test` on the release tree (`QT_QPA_PLATFORM=offscreen`,
  `QT_QPA_PLATFORMTHEME=generic`, `QT_QUICK_BACKEND=software`, `UV_OFFLINE=1`):
  148 QML tests, the application, file, catalog, matching session, palette
  matching, shortcut and motion checks, the matching worker and engine checks
  (build, protocol, tokenizer parity, shipped-binary digest), voice, clipboard,
  Codex, dictation and 48 time-zone cases passed. The suite then stopped at
  `tests/extensions_check.py`, which fails its "update applied" step
  ("Extensions are up to date" instead of "Updated Probe") on three runs here and
  identically on the exported 1.1.5 tree (`origin/main` at `4798c4a`): the
  update job schedules a check job the moment it finishes and the check's status
  overwrites the update's before the harness reads it, the race recorded under
  the time-zone entry below. Every other step of that check passes (install,
  update detection, update job, manifest at the new version, toggles, removal).
- Run separately after that stop: `tests/hotkeys_check.py` against the live
  `omarchy-menu-keybindings` on this machine passed; `tests/lint.sh` exits 0
  with 81 warnings, unchanged from the animation-tiers entry; `bin/keystroke
  validate`, `git diff --check`, `site/check.py` and `node --check site/script.js`
  pass.
- Release scope: the fourteen commits on `dev` after the 1.1.5 release merge,
  `c7cc2cb` (Smart Match) through `c2213e2` (Instant window transition), plus
  the release documentation. The installed plugin was not replaced and no live
  desktop check was run for this release; the manifest was already at 1.2.0.
  See [release notes](releases/v1.2.0.md).

## Animation tiers (2026-09-09)

Appearance gained **Animations** (Off, Snappy, Fluid; default Snappy) and
**Window transition** (Instant, Fade, Slide up; default Instant, chosen apart
from the tier so the window can stay instant while the rest animates).
`core/Motion.js` holds the one table of durations: Snappy 38 ms for the level
slide, the selection glide and the window, with a 14 + 34 ms flash (the first
cut was 32 ms and felt too short, so every Snappy figure grew by 20 %); Fluid
90 ms with a 20 + 50 ms flash; Off is all zeros and takes every path as a
plain assignment. Four transitions:

- A menu level (results, breadcrumb, or a provider view) enters from the right
  after `navigate` and from the left after `goBack`; rows are reconciled in
  place, so only the entering level moves.
- The selection is one `ListView` highlight that glides between rows (rows no
  longer paint their own background); a reset after typing or a level change
  jumps instead of gliding.
- The activated row flashes with the selected text color, and a launch waits
  for the flash to peak before the window starts leaving.
- The window fades (or slides up 20 px while fading) in and out on an
  `OutExpo` curve, so most of the change lands in the first frames; a gentler
  ramp read as the palette being late rather than as motion. The layer stays
  mapped for the fade-out without keyboard focus, so the launched app gets
  the keyboard at once.

Fixed after the first live check: the highlight vanished or sat on the wrong
row after typing. The `ListView` follows the surviving item when rows above the
selection are removed, so its own `currentIndex` drifted from `selected` while
the highlight read `currentItem`; reproduced offscreen (selected 0, list index
1 after the first row went away). The index is now re-asserted from the
selection after every reconcile instead of being bound to it.

Checked offscreen (`QT_QPA_PLATFORM=offscreen`, software backend):

- `tests/tst_motion.qml` (6 tests): tier ranges, fallback to Snappy, offsets.
- `tests/palette_motion_check.py` on the real palette with a fixture provider:
  the reveal starts below 1 and reaches 1; the highlight exists, covers the row
  and not its section header, glides after `select()` and jumps after a reset;
  `navigate`/`goBack` enter from the right/left and settle; activation flashes
  the activated row; closing keeps the window mapped until the fade ends and
  the slide-up leaves the card lower; reopening while leaving cancels the
  fade-out; with animations Off the reveal, highlight, level and window change
  at once and nothing flashes; after typing removes the first row the list
  index and the highlight follow the selection onto the new first row, and a
  kept selection is re-indexed when everything above it goes; Instant maps
  and unmaps at once while the tier stays Snappy; the row's flash overlay
  brightens then settles and a zero-length flash does nothing.
- Card renders grabbed mid-glide and mid-flash confirmed the highlight is
  painted under the row text and the flash reads as a brightening of the row.
- `qmltestrunner` (148 tests), the shortcut, matching, dictation and catalog
  checks pass; qmllint warnings unchanged (81).

Not exercised: the live layer-shell window (fade-in timing against surface
mapping, keyboard focus release during the fade-out) and the exact durations;
the numbers are the starting points to tune by feel, all in `core/Motion.js`.

## Smart Match performance and compiled engine (2026-09-09)

Profiled offscreen with `tools/profile_palette.py` on the laptop (Core Ultra X7
358H, 16 threads): the actual providers, this machine's Omarchy menu, 58 apps,
230 hotkeys and home folder, the installed small model, and 41 typed keystrokes
across four queries. Milliseconds are wall time of one `runQuery()` on the UI
thread (1 ms resolution).

| per query on the UI thread | before (`cdcfffe`) | after |
| --- | --- | --- |
| total, median / p90 / max | 35 / 148 / 287 | 10 / 16 / 21 |
| rank (frecency + sort) | 5 / 96 / 245 | 0 / 1 / 1 |
| providers + catalog enumeration | 23 / 30 / 56 | 8 / 15 / 18 |
| documents + request key | 2 / 3 / 4 | 0 / 0 / 1 |
| merge (lexical + semantic) | 4 / 7 / 9 | 1 / 3 / 6 |

- The ranking cost was `Qt.md5` (about 25 µs per call in the engine) run four
  times per comparison inside the sort; keys are now memoized and the bonus is
  computed once per row. Learned query keys changed shape to item hash, colon,
  context hash; previous learned entries decay out of `usage.json` unchanged.
- The catalog (rows, intent descriptions, fingerprint hashes, filtered documents
  and their digest) is built once per summon, scope, configuration or provider
  change and prewarmed while the palette waits for the first keystroke; the
  first-keystroke enumeration hitch (34 ms) is gone. Refreshes from one provider
  (`fd` finishing, an embedding reply) re-run only that provider; lexical scores
  are reused across the refreshes of one keystroke. Files and Hotkeys build rows
  only for the survivors; menu visibility is memoized until guards change.
- Engine: `matching/engine` (Rust, 600 KB, no ML framework) replaces the Python
  runtime when cargo is available. Tokenizer parity with `tokenizers` on 3,771
  texts (618 descriptions, catalog keys, 2,500 random and unicode strings):
  identical. Scores agree with the Python worker within 4e-7 and produce the same
  top-30 order for every checked query. Ready in 18 ms (65 ms submit-to-result
  through `Session.qml` after an idle unload, versus about 250 ms), 16 MiB
  resident versus 92 MiB for the live Python worker, 1,500 documents embedded in
  5 ms, a query in under 0.1 ms. Model files are fetched by URL with pinned
  SHA-256 digests; `huggingface_hub` is no longer needed. The Python path remains
  as the fallback without cargo and serves the same protocol.
- Shipped binary: `matching/bin/keystroke-matching` is a static-pie x86_64 build
  (1.5 MB, `ldd`: statically linked) with a manifest naming the machine and the
  engine-source fingerprint; the start script takes it only while both match. A
  fresh data directory now needs only the 8 MB model download (1.8 s here) and no
  cargo; the engine check verifies the manifest, digest and tokenizer parity of
  the shipped binary as well.
- Full `bin/keystroke test` except one pre-existing failure: 142 QML tests, all
  integration checks and the new `matching_engine_check.py` (build, protocol,
  parity) pass; `tests/extensions_check.py` fails at "update applied" on the
  untouched `cdcfffe` checkout as well. qmllint warning count is unchanged (283).
  Plugin validation and `git diff --check` pass. The installed plugin was not
  replaced; the live check is the user's.

## Fuzzy file search and tilde prefix (2026-09-09)

- Fixed candidate generation: `dwnlds` now reaches Downloads. `~` isolates Files
  and bypasses embeddings; the main palette offers Fuzzy (default), Literal,
  and Only with ~. Search remains under home and respects ignore rules.
- Five real-home fd runs per query (`downlo`, `dwnlds`, `rpt`, `zzzxqv`), two
  threads and 400 candidates: fuzzy medians 12.1–38.6 ms, maxima 12.4–40.7 ms;
  literal medians 36.2–39.5 ms. This is a warm local-disk measurement, not a
  latency guarantee. Broad fuzzy `rpt` reached the 400-candidate cap.
- QML scoring of 400 synthetic report paths measured about 6 ms per query over
  20 repetitions. No full-tree index or embedding work runs for file search.
- Full `bin/keystroke test`: 142 QML tests plus integration checks passed.
  New actual-fd integration covers all modes, bare tilde, directory matches,
  space/slash path abbreviations, hidden filters, and newline filenames.
  Palette integration verifies prefix isolation and embedding bypass. Targeted
  tests also cover bounded input, safe regex/argv, cache keys, and incomplete
  records after cancellation. Plugin validation and diff checks passed.
- Large/slow trees can reach the three-second timeout; broad queries can omit
  better results beyond the 400 candidates. Only with ~ avoids background file
  walks for ordinary root queries. The installed plugin was not replaced.

## Smart Match (2026-09-09, dev / 1.2.0)

- Full offscreen `bin/keystroke test` exits 0: **139 QML tests**, all prior
  integration checks, and new worker, session, catalog and palette matching checks.
  Used `QT_QPA_PLATFORM=offscreen`, `QT_QPA_PLATFORMTHEME=generic`,
  `QT_QUICK_BACKEND=software`; dependencies were cached and `UV_OFFLINE=1` was set.
- Pure logic covers spoken arithmetic, ambiguous prose, defaults and enum labels,
  launch-vs-install filtering, Chromium-only alias, typo distance, negation,
  recording direction, volume direction, on/off setters, and confirmation-preserving
  command deduplication. Typed provider arguments keep case and raw input.
- Real QML process checks cover one-in-flight/latest-queued requests, stale replies,
  Off unloading, changing size during loading, cancellation, idle unloading without
  immediately reloading on a status refresh, waking with a fresh index, and no
  leaked helper processes. Targeted session/palette checks were rerun after the idle
  lifecycle refinement and passed.
- Actual palette checks cover Only voice vs typed input, Voice and text, Off,
  scoped enumeration, removal from a live catalog, raw transcript preservation,
  ordinary matching fallback and stable selection during result reordering.
  The same palette harness also passed with the real installed 2M worker offline.
- Catalog checks execute no menu actions: unresolved/false guards and guarded
  ancestors are excluded from semantic enumeration; subtree scope and later changes
  are respected. Worker checks cover input limits, cache reuse/eviction, replacement
  of catalog IDs and IDs/scores-only replies.
- The pinned installer was exercised with Python 3.13 and the desktop's Python
  3.14.7. Small (2M) is installed under the current user's Keystroke data directory;
  Large (8M) was downloaded and validated only in an isolated `/tmp` directory.
  The installed small model subsequently served requests with `HF_HUB_OFFLINE=1`.
- Rendered and inspected Matching, Smart match choices and Matching model choices
  offscreen: correct labels, selected defaults, existing theme/layout and no clipped
  setting text. These were temporary screenshots, not new product artwork.
- `bin/keystroke validate` and `git diff --check` pass. Lint has no new warning
  messages compared with the untouched dev checkout; existing Quickshell/Qt metadata
  warnings remain. The 618 descriptions and source fingerprints have full coverage.
- No live desktop commands were activated, no real microphone recordings were
  tested, and the running plugin was not replaced. Installation/download performance
  was not measured on low-end laptops. This is a local suggestions system, not an
  automatic command executor or a production accuracy claim for arbitrary speech.

## Release 1.1.5 (2026-09-09)

- Full offscreen `bin/keystroke test`: 119 QML tests, application-library
  compatibility, voice lifecycle, clipboard, Codex, palette, 48 time-zone cases,
  extension lifecycle and qmllint passed. The sandbox skipped the live hotkey
  check because it cannot reach Hyprland; the host run passed with 205 bindings.
- Updated the live hotkey check to derive Close window availability from its
  current binding record. This host uses a runnable `hl.dsp.window.close()`
  action instead of the reference machine's keyboard-only closure. Fixed
  closure behavior remains covered by the QML unit tests.
- `site/check.py`, `node --check site/script.js`, plugin validation and
  `git diff --check` passed. Existing QML metadata warnings remain. The earlier
  live application check on Omarchy 4.0.3-1 returned and rendered 73 rows.
- Release scope: the five commits from the 1.1.4 marketplace snapshot
  `4e7409b` through `b1cfbb9`, plus release documentation and the host-aware
  integration-test correction. See [release notes](releases/v1.1.5.md).

## Non-intrusive Voxtype integration (2026-09-09)

- Retired the pinned Voxtype fork, build helper, bundled patch, systemd drop-in writer and TOML rewriting. Keystroke now resolves only the user's ordinary `voxtype` from `PATH`; the absent-Voxtype row still launches Omarchy's installer only when the user explicitly selects it. Keystroke passes `--file` and `--no-osd` for its own recording and otherwise leaves the user's daemon and preferences alone.
- Kept the runtime live-transcript reader as an optional, read-only capability. On Voxtype versions without the mirror, the path remains absent and the completed `record stop --wait --json` transcript fills the query. A future upstream implementation can provide partials without another Keystroke installer or configuration migration.
- `tests/voice_session_check.py` now puts both a stale Keystroke-owned binary and a normal `PATH` binary in a temporary home, verifies the `PATH` binary wins, exercises stop/cancel/auto-stop, and confirms a sentinel `~/.config/voxtype/config.toml` remains byte-identical. Focused voice check, site check, plugin validation and `git diff --check`: pass. Full offscreen `bin/keystroke test`: 119 QML tests and all integration checks pass; hotkeys skipped without a Hyprland session; qmllint emitted only the existing metadata warnings. A first full-suite attempt without the documented offscreen Qt environment aborted before loading tests because the sandbox could not connect to Wayland or X11; the core stack was entirely in Qt platform initialization and the offscreen rerun passed.
- Not exercised: a real microphone recording or a daemon that publishes live partials. No installed Voxtype config, service or binary was changed during this work.


## Provider patterns, image icons, view host surface; Calpad as the second extension (2026-09-09)

- API 1 gains three optional pieces, driven by [keystroke-calpad](https://github.com/evindor/keystroke-calpad) (source in the Calpad repository under `keystroke/`): `provider.patterns` (regular expressions with a boost, compiled once per registry rebuild in `providers/Registry.qml` by `core/Patterns.js`, evaluated in `runQuery()` before `query(ctx)`, the largest matched boost added in `normalize()` to rows that already score, the matched ids passed as `ctx.patterns`, examples shown on the extension's screen), `provider.iconSource` (an image that replaces the glyph on the Extensions and Settings rows about the provider), and a documented list of host members a provider view may rely on. `Extensions.gitUrl` accepts `file:///absolute/path` for local development installs. The host also drops a provider view whose provider is removed, unloaded or turned off while it is showing, and `inspect()` reports the matched patterns and the selected row's icon fields.
- `qmltestrunner -input tests`: **119 passed, 0 failed** (Qt 6.11.2, offscreen). New `tst_patterns.qml`: compile (invalid regex, bad flags, missing regex, non-objects, boost clamping, list and length caps, RegExp objects), evaluate (matched ids, largest boost, empty query, no patterns), examples. `tst_extensions.qml`: `file://` acceptance and refusal (relative, `..`, plain path), a loaded provider's icon and examples on the installed row, the About row and the new patterns row. `tests/extensions_check.py` PASS; `bin/keystroke test` otherwise unchanged; `tests/lint.sh` warning count unchanged from `dev` (206, all known metadata noise).
- Live, on this machine after `bin/keystroke install` and `omarchy-restart-shell`: a bare repository split from Calpad's `keystroke/` folder, typed as `file:///home/evindor/Work/keystroke-calpad.git` on the Extensions screen, produced the install row; the row's exact argv (`omarchy-plugin-add <url> --yes --enable`) installed and enabled the plugin; the palette listed the provider with no problems, its screen showed the About row with Calpad's icon and "Answers queries like price = 10 · Rent: $1,800 · …"; activating **Enabled** wrote `providers.io.github.evindor.keystroke-calpad.enabled` to keystroke.json. `summon {"query":"price = 10"}` then `inspect`: `patterns: {"io.github.evindor.keystroke-calpad": ["assignment"]}`, **Quick Calpad session** first under *Continue with* above Ask Codex (fallback tier, the image icon in `iconSource`, subtitle `price = 10  →  10`, preview `10`); `activate` opened the provider view (`view: io.github.evindor.keystroke-calpad`), which showed the note with its result aligned on the right and the footer keys. A second split pushed to the bare repository and `omarchy-plugin-update … --yes` fast-forwarded the installed copy. Screenshots taken over IPC with `grim` and reviewed; the ones in Calpad's README and the extension's `preview.png` come from this session.
- Calpad side (`calpad-gtk --note <id> --content <text>`): a first call created the note in the user's notes.json, a second call reached the running instance and updated the same note (one process); the test note was removed afterwards and notes.json restored. The extension's own `keystroke/bin/test` (unit tests, `omarchy plugin validate`, qmllint, offscreen service and view check against the real CLI: pattern gating, `=` prefix, async results, Enter copies, Shift/Ctrl+Enter, Ctrl+O argv, persistence, resume, Left, Esc) passes.
- Not exercised live: pressing keys in the session view on the desktop (covered by the offscreen check), the update row on the Extensions screen (the same script ran from the CLI), voice dictation into the view, the marketplace listing (the repository is not published yet: `keystroke/bin/publish` in the Calpad repository does that once `evindor/keystroke-calpad` exists on GitHub).

## Time-zone grammar: abbreviations, bare zones, now, dates (2026-09-09)

- `10am pt` used to fall through both the JS gate and the helper (the grammar was `<time> in|from <zone> [to <zone>] [on YYYY-MM-DD]`). `helpers/timezone.py` now owns the grammar: `<time> [in|from|at] <zone> [to|in <zone>] [on <date>]`, `<time> to <zone>` (local time shown elsewhere), `now|time|what time is it in <zone>`, `<zone> time`, and a date before or after (`tomorrow 9am est`, `10am pt on friday`, `10pm pt on tuesday to tokyo`). Times: `10am`, `10:30pm`, `10.30`, `1530`, `15:00`, `noon`, `midnight`, `10 a.m.`; a bare hour still needs `in`/`from`/`at`. Zones: an abbreviation table (`pt`, `pst`, `est`, `cet`, `eet`, `ist`, `jst`, `aest`, `nzt`, ...; ambiguous ones take the common reading and the detail line says which IANA zone was used, e.g. `pt = America/Los_Angeles`), region words (`pacific`, `eastern`), cities and countries that are not IANA names (`sf`, `nyc`, `india`, `germany`), IANA names with `/` or `_`, offsets (`utc+2`, `gmt-5`, `+05:30`), and `here`/`local`/`my time`. Names that span several zones (`australia`, `usa`) and IANA last-segment collisions come back as a hint the palette shows as a disabled row; half-typed queries stay silent.
- `core/Units.js` `isTimeQuery` is now a loose time-shaped gate (time token at the start after an optional date, `10 in <zone>`, `now in <zone>`, `<zone> time`) so the helper decides; decimals such as `128 * 1.24` and `10 amsterdam` do not pass it. `providers/Converter.qml` shows hint errors as a row, marks `live` answers and re-runs them every 30 s while on screen.
- `tests/tz_helper_check.py`: 48/48 with the clock fixed at 2026-09-09 12:00 UTC (the helper takes an optional ISO instant as its third argument). `tests/tst_units.qml` gate: 14 positive, 7 negative forms. `bin/keystroke test`: 110 QML tests, the voice, clipboard, Codex and dictation checks and the time-zone check pass; `bin/keystroke validate` passes; qmllint unchanged. `tests/extensions_check.py` fails its `update applied` step ("Extensions are up to date" instead of "Updated Probe") on this tree and identically on pristine `main` (three runs each): the update job schedules a check job the moment it finishes and the check's status overwrites the update's before the harness reads it. Pre-existing timing race in the check, not touched here.
- Not exercised live in the shell this round: the palette journey for `10am pt` and the 30 s refresh of `now in london` (same code paths as the unit-tested gate and helper; the QML changes are the hint row and the refresh timer).

## No agent-instruction files in the plugin tree (2026-09-08)

- The marketplace's security review at `a6b09bd` blocked on root `AGENTS.md`: the repository tree is what gets installed, so a file that agents read automatically ships into the plugin root and becomes an instruction channel unrelated to the runtime. `AGENTS.md` is now `CONTRIBUTING.md` (same content, addressed to contributors), `CLAUDE.md` (which only pointed at it and is the same class of file) is removed, and `.gitignore` keeps any local `CLAUDE.md`/`AGENTS.md` untracked so they cannot ship again. References in `README.md`, `docs/providers.md` and the hello example updated.
- Checked: no `AGENTS` reference left (`grep`), `bin/keystroke validate` pass, the QML test suite unchanged. Manifest 1.1.4; issue #5292 edited with the new `main` SHA for fresh validation.

## Pinned voxtype source for the marketplace baseline (2026-09-07)

- The marketplace's automated security baseline on submission omacom/omarchy-plugin-marketplace#5292 flagged `helpers/voice-setup.sh` for cloning a branch of the voxtype fork (`remote-git-execution-unpinned`). The script now carries `FORK_COMMIT` (`60082b10e61af51b63b97ce86254686aadb8af88`, the commit `helpers/voxtype-full-request.patch` is written against and where `feature/live-transcript-file` pointed), refuses anything that is not a 40-character SHA, clones with `--no-checkout`, requires the commit to exist in the checkout, and builds through one fail-closed chain: `git -C "$SRC" checkout --detach <the SHA, spelled out> && apply_revision_patch && cargo build --manifest-path "$SRC/Cargo.toml" …`, with an explicit stop when any link fails (`set -e` ignores failures inside an `&&` list). The build no longer `cd`s into the checkout: the detector carries a `cd` forward as the working directory of every later command, so the unrelated `python3` step that edits voxtype's config was reported as executing the checkout (second attempt, commit `e79591c`).
- A first attempt (commit `d0683d8`) kept the SHA in a variable and verified `HEAD` in a separate function; the bot validated the commit but the baseline still reported the finding. The marketplace's detector (`scripts/security-baseline-analysis.mjs`, public) accepts only `checkout`/`switch --detach <literal 40-hex SHA>` on the same directory token as the clone, joined by `&&` to every build or interpreter that references that directory. Running the detector locally was declined by this session's policy (downloaded code), so the chain was written to its rules by reading them; the bot's re-run on the pushed commit is the confirmation.
- Checked: `bash -n` on the script (shellcheck is not installed on this machine); `pinned_source`, `apply_revision_patch` and the pinned checkout exercised in a temporary HOME against a local repository standing in for the fork: a fresh fetch has no working tree, the chain lands detached at the pin with the patch applied, a second run on that checkout is accepted, a clean checkout at another commit is moved to the pin, a repository without the pinned commit and a short SHA are refused before anything runs; `bin/keystroke voice-status` on this machine, whose fork checkout at `~/Documents/ChatGPT/voxtype` is at the pinned commit. Not exercised: a full `voice-setup` rebuild (minutes of cargo; the cargo invocation itself did not change).
- Manifest 1.1.1, then 1.1.2 for the chained form, then 1.1.3 for the build without `cd`. Submitted for a new validation each time by editing issue #5292 with the new `main` SHA.

## Hotkeys provider (2026-09-06)

- `qmltestrunner -input tests`: **110 passed, 0 failed** (Qt 6.11.2, offscreen). New `tst_hotkeys.qml`: record parsing (arrow split, tabs inside arguments, garbage lines, duplicate binds merged into one row with two combos, same label with a different action gets its own id), key spelling (`SUPER SHIFT + RETURN` → `Super + Shift + ↵`, `XF86AudioRaiseVolume`, mouse buttons, unresolved `code:` keys), literal argv for load and dispatch (a shell-injection argument stays an argument), the screen listing in menu order with keyboard-only binds greyed, root search by abbreviation (`flcrn`), by keys (`super f` beats Full width on `Super + Alt + F`, `SUPER + ALT + F` works with the pluses), by command, and the root cap.
- `tests/hotkeys_check.py` (now part of `bin/keystroke test`) loads `providers/Hotkeys.qml` in an offscreen Quickshell against the real `omarchy-menu-keybindings` on this machine: first query pending, 219 binds after the records land, `flcrn` → Full screen with `Super + F`, `terminal` → `Super + ↵`, the screen listing all 219 in `Super+K` order with Keybindings first, Close window greyed, activate() translating to the script's `dispatch_binding` with `lua` and the fullscreen expression as separate argv elements. Nothing was dispatched: **PASS**. The check skips itself when `hyprctl binds` does not answer.
- `bin/keystroke validate`: pass. `tests/lint.sh`: only the known `QProcess::ExitStatus` noise on the new file.
- Installed with `bin/keystroke install` and `omarchy-restart-shell`; the in-shell journey (type `flcrn`, press `↵`, watch the window go full screen; open **Hotkeys**; press `Super+K` and compare) is left to the user, as is the frecency effect over days.

## Release 1.0.0: extensions from inside the palette (2026-09-06)

- `qmltestrunner -input tests`: **103 passed, 0 failed** (Qt 6.11.2, offscreen). New `tst_extensions.qml`: git URL acceptance and refusal (options, `ext::`, plain http), `owner/repo` expansion, defensive parsing of the Keystroke index and the marketplace catalog (an extension must name Keystroke the palette, not a key press: "one keystroke away" no longer matches), discovery merge by id and repository, installed listing from the Omarchy registry with both switches, literal argv for add/update/remove/check, the detached job wrapper, screen and detail rows, typed-URL install rows. `tst_settingstree.qml` follows the "Manage extension" row.
- `tests/extensions_check.py` (now part of `bin/keystroke test`) drives `providers/Extensions.qml` in an offscreen Quickshell against a fake HOME, a local bare repository as upstream, a `file://` index and a stub `omarchy-shell`; everything else is real (`omarchy-plugin-add`, `omarchy-plugin-update`, `omarchy-plugin-remove`, `omarchy-plugin-validate`, git, curl). It installs, sees the job row, finds the extension on and up to date, detects a pushed commit, updates through a fast-forward with validation, toggles Keystroke's switch and the shell's, removes, and confirms a second provider instance picks the in-flight job up from the runtime dir: **PASS**.
- Live, on this machine after `bin/keystroke install` and `omarchy-restart-shell`: `omarchy plugin add https://github.com/evindor/keystroke-timer.git --enable --yes` installed the published example; `summon omarchy.menu {"query":"timer 10m tea"}` then `inspect` listed "Start a 10 min timer: tea" first; the Extensions screen listed Keystroke Timer v1.0.0 as enabled with the update check done; the Timer's own settings screen appeared under Keystroke Settings. Found and fixed on the way: the provider registry was built before the shell injected `pluginRegistry` and never rebuilt after the shell recreated the palette on a plugin rescan, so a plugin installed after startup was invisible; it now rebuilds when the registry arrives and on every summon.
- Found and designed around: `omarchy-shell shell rescanPlugins`, which every install and removal triggers, destroys and recreates all plugin instances, Keystroke included. Extension jobs therefore run detached with their state and result in `$XDG_RUNTIME_DIR/keystroke/extensions/`, and the wrapper sends the outcome as a notification because the palette closes during the rescan.
- Marketplace: the marketplace's own `inspectSubmission` (scripts/build-catalog.mjs from omacom/omarchy-plugin-marketplace, run locally with a GitHub token) accepted both `evindor/keystroke` and `evindor/keystroke-timer` (manifest, root README, root license found). Submission itself is a maintainer-reviewed GitHub issue and was not filed.
- Screenshots in `assets/screenshots/` and `preview.png` were captured on this machine over IPC (`summon` with a query or scope, `grim`, crop to the card) and reviewed.
- Not exercised live: pressing Install/Update/Remove on the desktop (the same code paths run in `extensions_check.py`), the Timer's notification when a timer ends (the service's `Timer` fires it; the row that starts one was verified), voice.

## v1-voice checkpoint: clipboard query fallback (2026-09-06)

Normal spoken or typed queries now include **Copy to Clipboard** under **Continue with**. Enter copies the original text and closes; Ctrl+Enter additionally pastes after 100 ms. Command normalization does not strip wording, punctuation, or whitespace from the clipboard payload. AI handoffs also receive the original query. The dedicated dictation launcher remains optional.

Validation: 110 QML tests plus clipboard, palette, and recording lifecycle checks passed. The palette integration test covers a normal spoken query, selection and activation of the clipboard fallback, and replacement by a fresh typed query.

The whole-request backend change is included as `helpers/voxtype-full-request.patch`, based on voxtype commit `60082b10e61af51b63b97ce86254686aadb8af88`. `voice-setup` applies it or recognizes an already-patched checkout, and refuses incompatible source. This keeps the checkpoint reproducible without depending on uncommitted changes in the sibling checkout.

## Whole-request revision and Dictate to Clipboard (2026-09-06)

- File-output streaming in the local voxtype fork (`../voxtype`) now retains audio through the recording-duration cap and emits complete transcript snapshots. These replace accumulated text in memory, including earlier words and final punctuation; they never become virtual keyboard backspaces. Regular cursor dictation keeps its existing behavior.
- The Dictate to Clipboard provider preserves raw prose, bypasses Gemma, and starts recording on entry. Enter queues copying of the final transcript; Ctrl+Enter also pastes 100 ms after successful copy closes the palette. Escape, new navigation, and reopening cancel pending work.
- Automated checks cover whole-transcript replacement, Unicode/deletions, audio beyond the former window, clipboard payload fidelity, failure/cancellation, copy-close-paste ordering, and actual palette key handling with fake audio/clipboard processes. An offscreen render checks the dictation preview.
- Validation: 109 QML tests, 34 sliding-window tests, 13 streaming-output tests, recording lifecycle and clipboard/palette integration checks passed. Installed both the palette and rebuilt voxtype daemon; both voice services are active. Omarchy needed a shell restart to clear its old provider cache; IPC then confirmed the dictation provider. Live recognition accuracy and long-request latency still need user testing.

# Historical verification

Run on 2026-09-06 on Omarchy 4.0.2-1 (Quickshell 0.3.1-1, Qt 6.11.2, Python 3.14.7).

## Automated

- `omarchy plugin validate "$PWD"`: pass.
- `qmltestrunner -input tests`: **43 passed, 0 failed** across Calculator (grammar, bounds, partial input, formatting), Units/Colors, Match/rank/Frecency, Settings, MenuModel (override, alias, link, guard script, cycles). Every behavioral expectation from the prototype's Python suite that still applies was ported.
- `tests/tz_helper_check.py`: 6/6 (two conversions, DST gap, DST fold, invalid 12-hour time, non-time input).
- `tests/lint.sh` (qmllint with `qs` mapped to `/usr/share/omarchy/shell`): no findings except the known Quickshell metadata noise (`PanelWindow is not creatable`, `QProcess::ExitStatus` in `onExited`) and "member not found on QObject" for Omarchy's nested `Style.font.*`/`Color.menu.*` tokens, which qmllint cannot see through and which the stock plugins trigger identically.

`bin/keystroke test` runs all three.

### Voice review and live suggestions (2026-09-06, afternoon)

This supersedes the earlier Enter-to-finish-and-run behavior below.

- `bin/keystroke test` with the offscreen Qt platform and software rendering: **105 QML tests passed**, voice subprocess lifecycle check passed, 6 time-zone checks passed. The new assistant tests use an injected XMLHttpRequest substitute: warm-up deduplication, one-slot serialization, newest-partial coalescing, request and warm-up deadlines, stale callbacks, endpoint changes, live suggestions, final-answer reuse, startup recovery, catalog snapshots and edit/cancellation behavior. The separate Quickshell test drives the real `VoiceSession` Process callbacks with a fake CLI, verifies cancelled readers cannot leak into a new recording, and collects a daemon auto-stop.
- Reproduced the actual query-field anchor bindings in an isolated software-rendered window: original waveform **522 px**, text **-12 px**; corrected waveform **96 px**, text **414 px**, within the same 640 px card. Inspected a rendered image with the live phrase "Open the display settings". For this harness only, PanelWindow was replaced by an ordinary offscreen Window, and voice transport/detection was disabled. No microphone, model or desktop input was used.
- `omarchy plugin validate`, shell syntax checks, `git diff --check`, and `systemd-analyze --user verify helpers/keystroke-llm.service`: pass. qmllint has the existing Omarchy/Quickshell metadata warnings; no new assistant/session-controller warnings. Lint now excludes hidden worktrees, matching the installer exclusions.
- The model's real end-to-end latency, simultaneous Whisper/Gemma GPU inference, physical hold-to-talk bindings and the updated code in the running desktop have **not** been exercised in this pass. Keystroke and the two voice services remain disabled during investigation of the laptop's lid-sensor behavior. The text-only service definition and resource limits are verified but not installed or started. No claim of measured instant inference is made.

### Live words, normalization and the assistant (2026-09-06, evening)

- Measured first, on this laptop (Core Ultra X7 358H, Arc B390 iGPU): the packaged voxtype 1.0.1 on CPU took ~2.6 s per utterance with whisper `small` (every entry in its journal, including the single word "Chrome."); the Vulkan variant of the same binary takes 0.2–0.3 s warm. voxtype's sliding-window streaming (1.1 line) commits words ~1 s behind speech on Vulkan and stalls on CPU because inference overruns the tick. Gemma 4 E2B Q4_0 on llama.cpp Vulkan: pp 1700 tok/s, tg 55 tok/s; text command → catalog number in ~0.15 s with the list cached, 7–8 of 8 synthesized commands right; its own transcription is worse than whisper `small`, so whisper transcribes and Gemma only chooses.
- `qmltestrunner -input tests`: **87 passed, 0 failed**. New: `tst_intent.qml` (normalization of "Chrome.", "Launch Chrome.", "open up the settings, please", a verb alone; normalized transcripts reaching the matcher; numbered catalog lines with truncated details; identical system prompt across requests, grammar, thinking off, warm-up body; answer parsing incl. out-of-range and non-JSON; catalog stamps) and the assistant status row in `tst_settingstree.qml`. `tests/lint.sh`: only the known noise. `omarchy plugin validate`: pass.
- voxtype fork (`~/Documents/ChatGPT/voxtype`, branch `feature/live-transcript-file`, upstream PR peteonrails/voxtype#728): `cargo fmt`, `cargo clippy --all-targets --no-deps -- -D warnings` and the new tests pass; built with `--features gpu-vulkan` through the root-free toolchain under `~/.local/share/keystroke/toolchain`.
- Against the real daemon (the fork build via the systemd drop-in, `[whisper] streaming = true`, `[streaming]` 0.5 s ticks and a 12 s window), an 11 s speech clip fed through a temporary null-sink default source: `$XDG_RUNTIME_DIR/voxtype/transcript` was created empty at 0.1 s, read "And so" at 1.8 s, "And so my fellow Americans." at 2.7 s and grew every tick; `record stop --wait --wait-file … --json` returned `{"status":"ok","chars":121,…}` 0.5 s after the stop and the live file was gone with the state back to idle. The first run showed why `--wait-file` is needed (a streaming session consumes the `--file` override at start; without the flag the CLI errors before signalling) and why the window is capped (with the 29 s default the drain after stop re-transcribed for a minute; upstream #716 addresses the starvation).
- `bin/keystroke voice-setup` ran end to end without root: built and installed the fork, wrote the drop-in and the TOML edits, restarted voxtype (model loaded in 0.34 s on Vulkan0), installed llama.cpp b10821 and the model, enabled `keystroke-llm.service` (health ok). `voice-status` reports all of it.
- Not verified live: the palette journey in the shell (live words in the field, the *Spoken command* row, ↵ waiting for the pick). The worktree copy is installed and the shell restarted; the XMLHttpRequest client and the live-file reader are exercised only through qmllint and the unit-tested pure JS. To try: open the palette, hold `Super+Space`, say "open chrome" or "luck the screen", watch the field, release; Settings › Voice shows the voxtype version, the assistant status and the last answer time; `omarchy-shell shell call omarchy.menu inspect '{}'` shows `voice.command`, `voice.live`, `assist.pick`.

### Voice (2026-09-06, voxtype 1.0.1, Hyprland 0.56.2)

- `qmltestrunner -input tests`: **70 passed, 0 failed**. New: `tst_voicebindings.qml` (block shape, key parsing and Lua escaping, install/update/remove leaving the rest of `bindings.lua` untouched, a block missing its end marker) and voice cases in `tst_settingstree.qml` (screen listing, bindings row states and confirmation, abbreviations from the root, the installer offer without voxtype, no change without a voice model). `tests/lint.sh`: only the pre-existing token noise. `omarchy plugin validate`: pass.
- voxtype CLI checked directly before building on it: `record start --file=… --no-osd` then `record stop --wait --json` returned `{"status":"ok","text":"…"}` after about 3.4 s for a 2.5 s recording on the CPU `small` model; `voxtype-audio-bridge` printed `{"peak","rms","vad","ts_ms"}` frames at 100 Hz only while the daemon recorded. Hyprland's release and long-press semantics were read from `KeybindManager.cpp` at v0.56.2 (release binds require the modmask to still match; long-press fires after the keyboard repeat delay; the hotkey's own release is swallowed, the modifier's is delivered).
- In the shell (worktree copy installed with `bin/keystroke install`, shell restarted because the plugin reloader kept the cached component), driven over IPC: `voiceHold` → listening with the daemon recording and 96 bridge frames after 1.6 s, the string visible in the query field; `voiceRelease` → transcribing → the query became the transcript, status "Transcribed", the daemon back to idle and the runtime transcript file gone. Second-tap flow: `shell toggle` while open → listening (trigger tap), another toggle → transcribing → transcript. `↵` while listening (sent with `wtype`) stopped, transcribed and activated the top row. A synthetic `Super_L` press/release (`wtype -P Super_L -p Super_L`) ended a hold-triggered recording through the search field's key handler. `Esc` cancelled and closed every time. No plugin warnings in the journal.
- Not verified live: the Hyprland long-press and release binds themselves (they are written to the user's `bindings.lua` only through the Settings row, which was not exercised on this machine), the installer row's write and `hyprctl reload`, and dictation of actual speech (the test recordings were silence, which Whisper transcribed as "Thank you.").

### Fuzzy matching (2026-09-06, later the same day)

- `qmltestrunner -input tests`: **62 passed, 0 failed**. New: `tst_match.qml` covers the fzf-style scorer (word starts and exact titles first, gaps and mid-word letters cost, single mid-word letters and scattered letters in prose never match, paths and keywords rank below titles, the abbreviations `prefp`, `keysepro`, `setaiprv`, `kspa`, `ai prov`/`prov ai`, `sysshut`), and `tst_settingstree.qml` drives the flattened settings tree with the real AI schema: every abbreviation above ranks Keystroke Settings › AI & Web Search › Preferred assistant first from the root, `prefcla` selects its Claude choice, `dens comf` selects Comfortable density, scoped searches use breadcrumbs relative to the screen, list-only rows never match, ids are unique, `chrome` finds nothing in settings.
- Timing probe inside the suite: a keystroke over 700 rows where every row matches on three haystacks costs about 10 ms in the QML engine (Qt 6.11); queries that match few rows cost well under 1 ms. The real root has roughly 550 candidates.
- `tests/tz_helper_check.py`: 6/6. `tests/lint.sh`: only the pre-existing Quickshell token noise. `omarchy plugin validate`: pass.
- Not verified live in the shell this round (the checkout was being committed from another session at the time): the ranking above is exercised through the same provider code paths in the unit tests, but the in-shell journey (typing `keysepro` at the root and pressing ↵) is still owed.
- Found while committing: `.gitignore` carried a bare `core` line (a core-dump pattern) that also ignored `core/`, so none of the JavaScript modules had ever been committed. Fixed in the same branch; the files were added byte-identical to the working checkout.

### Files provider (2026-09-06, evening)

- `qmltestrunner -input tests`: **70 passed, 0 failed**. New `tst_files.qml`: no fd run for one-character or blank queries or when both kinds are off; the cache key ignores limit and scope; argv is literal (regex-escaped words behind `--and=` and `--`, a leading dash never a flag), bounded by `--max-results`, and carries `--type`/`--hidden` from the settings; parsing strips the home prefix and marks folders; the last word must be in the name (a file that carries the word only in its folder is dropped, `reports budget` finds it), the limit applies at the root but not in the Files screen, kinds filter, the user name matches nothing; effects are `xdg-open` for files and folders and `setsid uwsm-app -- xdg-terminal-exec --dir=…` for `Ctrl+↵` (a file opens the terminal in its folder), images carry a preview.
- The argv the module builds was run against the real home through the QML engine: `omarchy ray` 7 hits in 9 ms, `README.md` 14 in 8 ms, `hypr conf` with hidden entries 20 in 45 ms, `-v` 39 in 8 ms. A full gitignore-respecting walk of this home is 23 ms (2.7 k entries), a hidden-inclusive one 200 ms (282 k entries).
- Live, on the desktop: the branch build was installed with `bin/keystroke install`, and because a keepLoaded plugin keeps its cached component through `rescanPlugins`, loaded with `omarchy-restart-shell`. Driven over IPC (`omarchy-shell shell summon omarchy.menu '{"query":…}'`, then `call omarchy.menu inspect ""`): `omarchy ray`, `hypr`, `readme`, `bindings lua` each settled within 100–150 ms of the summon including the round trips, with the Omarchy and app rows first, at most ten file rows after them and the fallbacks last; `evindor` produced no file rows; the empty root listed Search Files; the journal had no plugin warnings. Then `bin/keystroke install` from the main checkout and another restart: the installed copy compared byte-identical to main, `shell.json` and `keystroke.json` unchanged. That run predates the last-word-in-the-name rule (it showed `omarchy ray` filling its ten slots with children of the matching folder, which is why the rule exists); the rule is covered by the unit tests and the real-fd run above, not by a second desktop pass.
- Not exercised live: `Ctrl+↵` (IPC cannot press keys; the code path is the same `activate()` with `row.altAction`), opening a file or folder from a row, the fd-missing row, the 3 s watchdog.

## Temporary in-shell install

The checkout was copied (no symlinks) to `~/.config/omarchy/plugins/evindor.keystroke` with a **menu-only manifest variant** for the test, so that enable/disable would leave `shell.json` byte-identical (a bar-widget kind would have re-inserted the stock menu button into the bar on restore). Then `rescanPlugins`, `omarchy plugin enable`. Observed:

- `shell.json` gained `evindor.keystroke` in `plugins[]`, `omarchy.menu` in `disabledPlugins[]`, and `evindor.keystroke` in `cloneSourceRestores[]`; `omarchy menu ping` answered through the replacement.
- Root open: 8 rows. Typing `22` → `22+` → `22+1` kept 4 rows and 4 delegates while the answer changed. `chrome` ranked Google Chrome first; `2m in feet` → `6.56167979 feet`; `10 am in london` → `12:00 EEST` via the helper after one pending pass; `:smile` → emoji rows; `#ff6644` → HEX/RGB/HSL answers with swatch; `nightlight` → the Omarchy entry; an unmatched query → the three fallbacks only.
- Routes: `omarchy menu summon system` opened the System submenu (7 rows); `summon style.font` ran the volatile fonts provider (5 rows); `summon apps` opened Applications (54 rows). Settings, Appearance and per-provider screens rendered; saving `density = comfortable` wrote `~/.config/omarchy/keystroke.json` atomically and the card widened.
- dmenu: `omarchy-menu-select` with glyph/label/subtext options rendered and filtered; selecting returned `Beta`; `omarchy-menu-input` returned `literal $() \`id\` text` unchanged; closing a picker returned exit 1 with no selection; a second picker cancelled the first (exit 1) and completed itself.
- No QML warnings or errors from the plugin in the user journal; hot reload on file changes worked.
- Screenshots were reviewed for theme fit (dark theme, Omarchy tokens, no hard-coded colors).

Afterwards: `omarchy plugin disable evindor.keystroke`, directory removed, `rescanPlugins`. `shell.json` compared **byte-identical** to the pre-test copy, `omarchy menu ping` answered from the stock menu, the test-created `~/.config/omarchy/keystroke.json` and `~/.local/state/keystroke/` were removed, no helper processes remained.

## Not verified

- The bar widget (`BarWidget.qml`) in a live bar; it is a 20-line adaptation of the stock widget and lints clean.
- Community discovery end to end with a real service plugin installed (the example was not installed to avoid a second change to `shell.json`); the code path is the same `shell.serviceFor` used by Omarchy's own panel/service pairs.
- Keyboard interaction (pointer hover selection made IPC-driven selection tests non-deterministic on the live desktop); Ctrl+K, Delete-to-uninstall and PageUp/PageDown were reviewed, not exercised.
- Launching apps, `hyprpicker`, image clipboard copy, the AI CLI hand-off, and light themes. The desktop deep links were verified separately on 2026-09-06 by opening them and reading the resulting windows: `claude://claude.ai/new?q=…&surface=chat` prefilled a new Claude chat; `codex://threads/new?prompt=…` prefilled a new Codex thread; a `chatgpt.com` URL handed to the Codex app only opened a signed-out tab in its embedded browser, which is why browser mode uses the real browser. Typing never contacts a provider; nothing destructive was executed.
- Performance budgets from the review (open latency, PSS, wakeups): not measured yet; the design removes the resident process and the empty first frame by construction, but numbers are still owed.

## Native audio live checkpoint — 2026-09-06

Branch `codex/gemma-audio-vllm` adds the resident vLLM backend to the installed
Keystroke menu. The stable `main` / `v1-voice` checkpoint is unchanged.

- 114 QML tests passed. Both voice process lifecycle tests, synthetic native
  capture/SSE test, clipboard helper test, and palette clipboard tests with each
  backend passed. Time-zone checks passed. qmllint completed with the existing
  shell/type-metadata warnings, including QProcess::ExitStatus on the new process
  handlers; these handlers were exercised in real Quickshell.
- One aggregate host test run timed out in the offscreen palette subprocess.
  Both palette variants passed separately in the sandbox. The HTTP capture test
  ran on the host because the sandbox prohibits binding its loopback test socket.
- Installed through the plugin CLI and restarted the shared shell to clear cached
  QML. Native shell IPC reported `backend:vllm`, `available:true`, `warmed:true`,
  349 catalog rows, and no plugin/config errors. Existing hotkey bindings remain
  installed. The automated test used a synthetic recorder, not the microphone.
- The actual AudioSession → audio_record.py → resident vLLM path processed
  `Open my browser please.` using that catalog. A partial `open my gb` was revised
  to `open my browser please`; the final result selected catalog row 151, Browser,
  in 1,061 ms. This is a short synthetic utterance, not an accuracy/latency survey.
- The live service uses the same pinned INT4 checkpoint and oneDNN XPU kernel as
  the completed experiment, with a 16k context and 512 MiB KV cache for the full
  catalog. Observed cgroup memory ranged from about 8.7–12.4 GiB as file cache was
  reclaimed. It had zero restarts during the live checks.
- `keystroke-vllm` is enabled for subsequent graphical logins; `keystroke-llm` is
  disabled to avoid two resident Gemma models. Voxtype remains available for the
  user's other dictation shortcuts. `bin/keystroke voice-backend voxtype` restores
  the previous backend and services. Switching writes a timestamped config backup.

## Public showcase and GitHub Pages (2026-09-06)

- Added the static landing page in `site/`: feature showcases, full-image views,
  install-command copying, optional voice/Codex/extension setup, and stock-menu
  restoration instructions. Responsive CSS, keyboard focus, native dialog close
  behavior, reduced-motion styles, social metadata and local-only assets are
  included. No runtime product logic or provider contract changed.
- Captured 19 screenshots at 2560 x 2160 using the existing `omarchy-shell`
  process and the real palette, result-row, preview, waveform and conversation
  QML. A disposable independent overlay supplies public sample data. Calculator,
  colors, units and dated time-zone results use production logic; other screens,
  including Codex messages and live voice state, are staged fixtures. These are
  illustrative captures, not new end-to-end claims about those integrations.
- Privacy: no real clipboard history, personal file search, recent conversations,
  microphone audio, desktop background or other windows are captured. Only the
  card is exported with `grabToImage`. All capture plugins were disabled and
  removed; plugin listing showed zero remaining, and the normal menu's `ping`
  returned `ok`. No second Quickshell was launched.
- Inspected the capture contact sheet and detailed Codex, voice, clipboard, apps,
  color and social layouts. Produced two collages and four individual feature
  cards, plus a 2400 x 1260 site social preview. The code-native layouts preserve
  the screenshot pixels; no generated reconstruction of the interface is used.
- `python3 site/check.py`: pass (asset/anchor references, unique ids, image
  descriptions/dimensions, no third-party page resources or private paths).
  `node --check site/script.js`, Python compile checks for the capture tooling,
  `bin/keystroke validate`, and `git diff --check`: pass. Local HTTP preview: 200.
- The GitHub Pages workflow validates and uploads only the public HTML, CSS,
  JavaScript and assets; official actions are pinned to exact commits. Capture
  scripts, preflight source and documentation are excluded from the deployment.
- Not exercised in this pass: end-to-end application launches, real voice/Codex
  sessions, extension installs, full application regression suite, or browser
  interaction/responsive-layout testing. No application behavior was changed.
- Publication completed successfully in [GitHub Actions run 34052616102](https://github.com/evindor/keystroke/actions/runs/34052616102).
  The live HTTPS index and all 23 assets matched local SHA-256 hashes. The
  preflight script, site notes, and capture tooling returned 404 from Pages.
  Repository homepage now points to <https://evindor.github.io/keystroke/>.

## Omarchy 4.0.2 / 4.0.3 application compatibility (2026-09-09)

- The stock menu manifests and `shell/services/AppLibrary.qml` are identical
  between upstream tags `v4.0.2` and `v4.0.3`. The change is in `shell.qml`:
  4.0.3 gives third-party plugins a scoped shell, and gates `appLibrary` on
  `manifestHasKind(manifest, "menu")` using `Array.isArray(manifest.kinds)`.
  The panel Instantiator converts the nested array into a QML sequence for which
  that check is false, even though `indexOf("menu")` returns zero. The stock
  first-party menu bypasses this scoped-shell path; cloning does not bypass it.
- Reproduced on the live 4.0.3-1 host: the injected shell and manifest were
  present, but both the palette and provider had no app library and zero apps.
- Keystroke now prefers the injected library and, if absent, loads the installed
  Omarchy AppLibrary component. This retains native filtering, icons, launch
  feedback and removal without copying its implementation or changing system
  files. The fallback is unloaded if a shared library becomes available.
- `tests/applications_check.py` reproduces the manifest conversion and checks
  both injection paths, hidden/NoDisplay and configured hides, root keyword
  search, refresh delegation, app-change notifications and fallback lifetime.
  Live 4.0.3 verification returned 73 applications after the fix. Compatibility
  with 4.0.2 is checked through its shared-library contract and the identical
  upstream library source; a separate 4.0.2 desktop was not available.
- Validation: 119 QML tests, application compatibility and palette integration
  checks passed. Plugin validation and qmllint passed (existing metadata
  warnings only). The live Applications screen rendered all 73 result rows.
# Query-specific selection learning — 2026-09-09

- Reproduced the `downlo` ranking with actual file scoring and Smart Match merge:
  the Downloads folder loses to hotkeys before learning and ranks first after
  one selection, with embeddings enabled or disabled.
- Verified serialization, query/scope isolation, normalization, decaying/capped
  weights, and answer/fallback tier boundaries. The actual palette integration
  test activates a remembered result, reopens, and verifies the learned ranking.
- Full `bin/keystroke test`: 140 QML tests passed, plus all integration checks;
  plugin validation and `git diff --check` passed. The installed plugin was not
  replaced as part of this change.

## Omarchy 4.0.3 scoped-shell revocation (2026-09-09)

- Applications disappeared again after 1dc4e48 restored `keepLoaded`. The
  4.0.3 manifest conversion has a second consequence beyond the null
  `appLibrary`: `createScopedPluginShell` stamps the API with a capability
  profile computed from the converted manifest (`…|no-menu`), and
  `prunePluginApis` recomputes the expected profile from the registry manifest,
  whose `kinds` is a real array (`…|menu`). The mismatch revokes and destroys
  the API, so the panel's injected `shell` becomes null — the shell assigns it
  once in `Loader.onLoaded`, so it never comes back.
- Without `keepLoaded` the panel is destroyed and recreated on every open, so a
  fresh `shell` was injected each time and the fallback stayed active. With
  `keepLoaded` the single long-lived instance loses `shell` on the first prune,
  which deactivated the fallback Loader and left zero applications.
- `core/ApplicationLibrary.qml` now latches `hostSeen` on the first injection
  and keeps the fallback active while no shared library is present, so the
  library survives revocation. Verified live on 4.0.3-1: `hostShell` drops to
  false a second after startup and the palette still reports 73 applications
  (93 before the configured-hides file loads).
- `tests/applications_check.py` covers the revocation: it drops `hostShell` back
  to null after a shared library and asserts the fallback keeps serving rows.
  The check fails against the pre-fix component.
- Still lost after revocation: everything else the injected `shell` provides —
  `serviceFor`/`ensureService` for extension-provided services, and the `shell`
  handed to extension contexts. This needs an upstream fix in
  `manifestHasKind`, which should accept a QML sequence, not only a JS array.
- Validation: 148 QML tests, application compatibility and palette dictation
  checks passed; plugin validation clean.
