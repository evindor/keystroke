# Review-build verification

Checked on 2026-09-06, on the user's Omarchy 4.0.2 machine.

## Results

- **27 backend tests passed**, using Python's standard-library unittest. Added checks cover strict word matching, calculator partial input, application priority, persistent/decaying frecency, compact settings, and coalesced provider results.
- **Nine live UI test groups passed**: home/native applications; submenu selection reset; stable rows while typing partial arithmetic; actual installed Chrome ranking; calculator/converter/colors; AI/web fallbacks; settings navigation; Omarchy root/dynamic font provider; dmenu select/input/cancel replies. The typing test verifies that delegates are not recreated and the empty/loading state never appears between `22`, `22+`, `22+1`, `22+12`, and `22+123`.
- `omarchy plugin validate` passed against the checkout's manifest and files.
- The native Quickshell review configuration loaded and rendered successfully on Wayland. Screenshots in `assets/` were captured from the palette's own QML item and visually reviewed.
- QML lint reports two installed-Quickshell metadata warnings: `PanelWindow is not creatable` and the missing `QProcess::ExitStatus` parameter type. Both components load in the real runtime. Unqualified component-access warnings were fixed with bound component behavior.
- The standalone QML scanner also warns about `qs.Ui` in the unused native bar entry point. That import resolves relative to the actual Omarchy shell when installed; live in-shell integration remains untested.

Tests use temporary files for config and picker replies. No stock menu actions, AI sessions or clipboard history contents were executed/copied by the automated tests. The user manually confirmed a Google Chrome launch and calculator copy/paste. The review launcher has not been installed as the native menu replacement. Separately, at the user's request, the Dell Copilot binding in `~/.config/hypr/bindings.lua` was changed to launch this checkout's `bin/flint`; the original binding was backed up and the regular Omarchy menu remains available. That local configuration is outside this repository.

## Original review-build measurements (before feedback fixes)

Twenty measured iterations after one warm-up, no user config overrides. These are **in-process backend query times**, excluding IPC, the 24 ms input debounce, rendering, app launching and cold startup.

| Query / scope | Median | Maximum |
| --- | ---: | ---: |
| Home | 0.15 ms | 0.25 ms |
| Calculator | 0.11 ms | 0.16 ms |
| Unit conversion | 0.08 ms | 0.09 ms |
| Time-zone conversion | 0.10 ms | 0.16 ms |
| Emoji search | 4.00 ms | 6.15 ms |
| Omarchy root, warm | 0.32 ms | 0.38 ms |

These measurements do not establish battery impact or end-to-end latency. The app has no recurring search timer or additional clipboard capture watcher; hidden queries are cancelled. Actual battery testing and long-session profiling remain outstanding.

A three-second sample after the live UI and screenshot checks, with the palette hidden, measured **420.0 MiB RSS for the standalone Quickshell review instance** and **27.0 MiB RSS for Python**. The CPU counters increased by 2 ticks for Quickshell and 0 for Python. RSS includes shared/mapped runtime resources; this is not an exclusive-memory measurement. The standalone result is not yet satisfactory for the lightweight goal. Hosting in the existing Omarchy shell should avoid a second Qt runtime, but its marginal memory and power cost must be measured, not assumed.

## Before using this as the daily menu

1. Decide the QML/JS and Omarchy-native provider architecture. Preserve the native menu's remaining route semantics while porting.
2. Test installation in the existing shell, bar integration, keybind/IPC replacement, disable/re-enable, hot reload, shell restart and restoration to the original menu.
3. Restore immediate action-on-summon for direct leaf aliases, or explicitly decide on the current extra activation step. Validate dmenu caller dimensions and simultaneous callers.
4. Exercise application launches, clipboard copy/image copy, hyprpicker, and the installed AI desktop and CLI targets end to end.
5. Broaden accessibility, scaling, multi-monitor and keyboard checks. Confirmation and text-input behaviors are implemented; not every path has automated key-event coverage.
6. Add update/removal tests for third-party providers and settle their discovery/registration API before publishing it.

No claim is made that bundled extensions are guaranteed safe or that the current provider protocol is a security sandbox.

## Attribution

Omarchy's MIT-licensed menu and shell sources informed the adapter and plugin lifecycle. `BarWidget.qml` is adapted from the installed Omarchy menu bar widget. Stock menu and emoji data are read from the installed Omarchy package rather than copied into this repository. Omarchy's copyright notice is retained in the root LICENSE.
