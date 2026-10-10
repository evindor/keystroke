# Performance log: open latency and process spawning

Branch `perf/open-latency` (from `ext/windows`). Prepared for a later pull request.

Per-keystroke cost was already low (`docs/verification.md`: total median 10 ms, p90 16 ms).
The remaining cost is on palette open and in spawned processes. These changes target that.
Timings are single runs on one machine and are indicative, not a benchmark.

## Changes

| # | Change | Files | Effect |
|---|--------|-------|--------|
| 1 | Codex app-server no longer starts on every open. It warms when the Codex scope is entered or the query starts with `?`. A version mismatch (exit 65) is remembered for the session, so it is not respawned. | `providers/Codex.qml`, `codex/AppServer.qml`, `codex/CodexSession.qml` | Removes a `bash -lc` + `codex --version` + app-server spawn (about 131 MiB PSS when it runs) from each open. |
| 2 | `bash -lc` replaced by `bash -c` for probes and Omarchy scripts. The login shell cost about 45 ms per spawn (`bash -lc true` 49 ms, `bash -c true` 3 ms). The Codex app-server launch keeps `-lc` because it can depend on login-shell PATH. | `core/Hotkeys.js`, `providers/{Codex,OmarchyMenu,AiWeb,Files,Converter}.qml` | Faster guards, hotkeys load and start-time probes. Quickshell's inherited PATH already contains `~/.local/bin`, mise shims and the Omarchy bin. |
| 3 | Removed the unconditional `providerRegistry.rebuild()` from `notifyOpened`. `sync()` already rebuilds when the extension scan changes. | `Keystroke.qml` | Avoids recompiling patterns/commands for every provider and the follow-on catalog invalidation on every open. |
| 4 | Omarchy menu guards and Hotkeys only call `requery()` when their results changed. | `providers/OmarchyMenu.qml`, `providers/Hotkeys.qml` | Skips a full catalog enumeration and re-rank after each open when nothing changed. |
| 5 | Recent projects and Browser profiles rescan at most once a minute instead of every open (the first query still scans on demand). | `extensions/{recent-projects,browser-profiles}/Service.qml` | Saves a Python helper spawn (about 90-120 ms each) per open. |
| 6 | The Herdr helper walks `/proc` and asks Hyprland only when a session is running. | `extensions/herdr/bin/herdr.py` | The helper was about 85-155 ms with no sessions. |

## Measured (tools/bench_open.py, offscreen, 8 steady-state opens per run, 3 runs each, medians)

| Metric | Before (`d84b822`) | After (`a557a11`) |
|--------|--------------------|-------------------|
| `open()` blocking the UI thread | 37 / 37.5 / 42 ms | 27 / 33.5 ms |
| CPU per open (Quickshell + children) | 1835 / 1785 / 1875 ms | 1660 / 1665 ms |
| Processes spawned per open | 157 / 157 / 156 | 143 / 147 |
| `bash -lc exec` (Codex start) per 8 opens | 34 | 0 |

Roughly 7-10% less CPU and 7% fewer processes per open. The offscreen harness cannot reproduce the real
layer-shell reveal, so wall-clock-to-visible is not measured. Processes are sampled from /proc, so very short ones can be missed.
Most of what remains is the Omarchy menu guard batch (`bash -c declare ...`, which calls omarchy-network-status, omarchy-hw-*, omarchy-dns
and others) plus `xdg-mime` and `xdg-terminal-exec` lookups. That is the next target.

## Second run: 4 interleaved runs x 8 opens (32 opens per side)

```
open() blocking the UI thread (ms, median)
  before ████████████████████████████████████████████    61
  after  █████████████████████████████████████████       56   -7.4%

CPU per open, Quickshell + children (ms, median)
  before ████████████████████████████████████████████  1920
  after  █████████████████████████████████████████     1795   -6.5%

Processes spawned per open (median)
  before ████████████████████████████████████████████   175
  after  █████████████████████████████████████████      165   -5.7%

CPU per open, median of each run (ms)
  run 1: before 1810  after 1635  (-9.7%)
  run 2: before 1910  after 1740  (-8.9%)
  run 3: before 1915  after 2025  (+5.7%)
  run 4: before 2105  after 2020  (-4.0%)
```

Spread within a side is wide (CPU per open, after: 630-3300 ms; before: 1740-2180 ms), so the machine's background load
swamps a gain this small. Read the result as "a few percent lower, direction consistent in 3 of 4 runs", not a precise figure.
The Codex launch is gone entirely (34 `bash -lc exec` per 8 opens before, 0 after).

Keystroke cost (`tools/profile_palette.py`, 41 keystrokes) did not change: total median 104 ms before, 105 ms after
(p90 202 vs 180 ms). Both are well above the 10 ms in `docs/verification.md`, which points to a busy machine during the run.
These changes do not touch the typing path.

## Third change set: window first, guards on a TTL, loading bar

Goal: every key typed after SUPER+SPACE is captured; plugins load in the background; results stream in; the user sees that work is running.

| # | Change | Files |
|---|--------|-------|
| 7 | `open()` sets `opened = true` and returns. `notifyOpened()` and the first `runQuery()` run one frame (16 ms) later from a timer, so the surface can map before the UI thread is busy. A key typed in between only restarts the debounce. | `Keystroke.qml` (`openWork`) |
| 8 | Omarchy menu guards (about 100 processes) re-run on open at most every 45 s. They still run on first load and when the menu files change. | `providers/OmarchyMenu.qml` (`guardsAt`) |
| 9 | Loading bar: a 2 px segment sliding along the search field's bottom edge while background work runs, shown after the 180 ms delay so fast opens never flicker. Still, faint line when animations are off. Driven by `busy` = pending provider, extension scan, matching engine starting, or a provider reporting through the new `host.setBusy(key, on)` (used by the guards and Hotkeys). | `Keystroke.qml`, `providers/Registry.qml` (`scanning`), `providers/OmarchyMenu.qml`, `providers/Hotkeys.qml` |
| 10 | Test: keys typed in the same turn as `open()` all reach the field (12 rounds), the first query runs on them, and the bar follows `setBusy()`. | `tests/palette_open_typing_check.py` |

### Results: 3 variants, 4 interleaved runs x 8 opens each

```
32 opens per variant (4 interleaved runs x 8)

Longest UI stall in first 400 ms after open (ms, median) - keys wait this long
  baseline d84b822           ████████████████████████████████████          50
  + first 6 fixes            █████████████████████████████████             46  -8%
  + deferred open, TTL, bar  ████████████████████████████████████████      56  +12%
  spread min/max             44/91   41/98   46/103

open() blocking the UI thread (ms, median)
  baseline d84b822           ████████████████████████████████████████      34
  + first 6 fixes            ████████████████████████                      20  -40%
  + deferred open, TTL, bar  █                                              1  -97%
  spread min/max             22/72   16/60   1/4

CPU per open (ms, median)
  baseline d84b822           ████████████████████████████████████████    1805
  + first 6 fixes            ████████████████████████████████████        1610  -11%
  + deferred open, TTL, bar  ██████████████                               620  -66%
  spread min/max             1690/2280   1560/2010   600/750

Processes spawned per open (median)
  baseline d84b822           ████████████████████████████████████████     154
  + first 6 fixes            ███████████████████████████████████          136  -11%
  + deferred open, TTL, bar  ████                                          16  -90%
  spread min/max             137/169   129/162   12/23
```

How to read it:
- **CPU and processes drop a lot (-66%, -90%)**, mostly from the guard TTL. The benchmark opens every 2.5 s, so the guards are skipped
  after the first. A cold open (more than 45 s since the last) still pays the full guard batch, now after the window has mapped.
  Real-world savings depend on how often the palette is opened.
- **`open()` itself now returns in about 1 ms** (-97%), because the work moved out of it.
- **The longest UI stall in the first 400 ms did not improve** (50 -> 56 ms median, within noise). The work moved about one frame later;
  it did not shrink. A key typed during that stall is queued, not lost, and appears when it ends. The remaining stall is the first
  `runQuery()`, catalog enumeration and `applyRows`. Shrinking it is the next job (chunk the catalog, prewarm at startup).
- **Keys sent before the layer surface is mapped and focused still go to the previously focused window.** That gap (hotkey ->
  `bin/keystroke` -> `omarchy-shell` -> `quickshell ipc` -> surface map -> keyboard enter) is outside the plugin. The offscreen harness
  cannot measure it. A real-compositor check (`bin/keystroke toggle`, then `wtype`, then read the field back) has not been run.

## Security notes

Reviewed by the author, not independently audited. No new path from outside input to a shell, file path or network call.

- **`bash -lc` -> `bash -c`:** removes profile sourcing. Scripts still take inputs as positional arguments (`$0`, `$1`). `PATH` now comes from Quickshell's environment, which is the same user-controlled value a login shell would build; the risk is a missing tool, not a hijack.
- **Codex lazy start:** fewer unprompted processes. The version pin in `helpers/codex-start.sh` is unchanged, and a remembered mismatch fails closed (an unpinned `codex` is never run).
- **Guards re-run every 45 s on open:** guards decide which menu items are shown or checked; they do not authorize anything. Stale results can show an item that no longer applies for up to 45 s; activating it runs the same command as before.
- **Registry rebuild no longer runs on open:** relies on `sync()` rebuilding when an extension is turned on or off. This was reasoned from the code, not covered by a test; if wrong, a just-disabled extension could stay loaded until the next config reload.
- **Deferred open work (16 ms):** `applyRows([])` clears old rows before the window appears, so Enter in that gap cannot run a stale result. A key can arrive before the first query has run (a correctness trade-off).
- **60 s scan caches (recent projects, browser profiles) and the lazy Herdr helper:** read the same data less often; nothing new is read or exposed.
- **`host.setBusy(key, on)`:** new function callable by providers and extensions. A bad extension could keep the loading bar on or add many keys. Extensions already run with the user's full privileges, so this is cosmetic.
- **Tools:** `tools/bench_open.py` and `tests/palette_open_typing_check.py` run `quickshell` on a temporary copy of the repo and read `/proc`. No network calls; nothing is written outside the temp directory.
- **Unchanged and out of scope:** extensions and the Codex integration run with the user's privileges.

## Not done yet (candidates)

- Cut the first-query stall after open (about 50 ms): prewarm the catalog at startup, chunk enumeration, cheaper `applyRows`.
- Real-compositor key-loss measurement (`wtype` right after `bin/keystroke toggle`) and a lighter launch chain / persistent mapped surface.

- Files provider: require 3+ characters at the root, longer debounce for spawning providers.
- Windows extension: use `Quickshell.Hyprland.toplevels` instead of spawning `hyprctl` on open; cache icon lookups by window class.
- `applyRows` (`Keystroke.qml`): skip `ListModel.set` for unchanged rows.
- Memoize `settingsFor` and `Qt.md5` in `Clipboard.qml`.
- Embedding engine start: skip re-hashing the model when size/mtime match.
- Browser search: opt-in at the root or 3+ characters, SQL prefilter, cache `xdg-mime`.
- Config only: `windowTransition: "slide"` with `animations: "fluid"` adds a 90 ms reveal.

## Verification

Passing: `tests/codex_session_check.py`, `tests/palette_extensions_check.py`, `tests/files_check.py`,
`tests/catalog_check.py`, `extensions/herdr/tests/test_helper.py`.
`tests/hotkeys_check.py` fails ("Close window availability follows the host binding") with and without these changes.

Open latency is still not measured in the repo. Before merging, time `open()` to first rows and count spawned
processes per open, before and after, and run `tools/profile_palette.py` to confirm keystroke totals did not regress.
