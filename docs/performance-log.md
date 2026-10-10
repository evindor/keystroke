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

## Not done yet (candidates)

- Omarchy menu guards: re-evaluate on a TTL instead of on every open; this is the largest remaining cost (about 100+ processes per open).

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
