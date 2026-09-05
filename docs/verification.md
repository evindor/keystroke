# Verification

Run on 2026-09-06 on Omarchy 4.0.2-1 (Quickshell 0.3.1-1, Qt 6.11.2, Python 3.14.7).

## Automated

- `omarchy plugin validate "$PWD"`: pass.
- `qmltestrunner -input tests`: **43 passed, 0 failed** across Calculator (grammar, bounds, partial input, formatting), Units/Colors, Match/rank/Frecency, Settings, MenuModel (override, alias, link, guard script, cycles). Every behavioral expectation from the prototype's Python suite that still applies was ported.
- `tests/tz_helper_check.py`: 6/6 (two conversions, DST gap, DST fold, invalid 12-hour time, non-time input).
- `tests/lint.sh` (qmllint with `qs` mapped to `/usr/share/omarchy/shell`): no findings except the known Quickshell metadata noise (`PanelWindow is not creatable`, `QProcess::ExitStatus` in `onExited`) and "member not found on QObject" for Omarchy's nested `Style.font.*`/`Color.menu.*` tokens, which qmllint cannot see through and which the stock plugins trigger identically.

`bin/keystroke test` runs all three.

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
- Launching apps, `hyprpicker`, image clipboard copy, the AI desktop/CLI hand-offs, and light themes. Typing never contacts a provider; nothing destructive was executed.
- Performance budgets from the review (open latency, PSS, wakeups): not measured yet; the design removes the resident process and the empty first frame by construction, but numbers are still owed.
