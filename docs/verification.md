# Verification

Run on 2026-09-06 on Omarchy 4.0.2-1 (Quickshell 0.3.1-1, Qt 6.11.2, Python 3.14.7).

## Automated

- `omarchy plugin validate "$PWD"`: pass.
- `qmltestrunner -input tests`: **43 passed, 0 failed** across Calculator (grammar, bounds, partial input, formatting), Units/Colors, Match/rank/Frecency, Settings, MenuModel (override, alias, link, guard script, cycles). Every behavioral expectation from the prototype's Python suite that still applies was ported.
- `tests/tz_helper_check.py`: 6/6 (two conversions, DST gap, DST fold, invalid 12-hour time, non-time input).
- `tests/lint.sh` (qmllint with `qs` mapped to `/usr/share/omarchy/shell`): no findings except the known Quickshell metadata noise (`PanelWindow is not creatable`, `QProcess::ExitStatus` in `onExited`) and "member not found on QObject" for Omarchy's nested `Style.font.*`/`Color.menu.*` tokens, which qmllint cannot see through and which the stock plugins trigger identically.

`bin/keystroke test` runs all three.

### Fuzzy matching (2026-09-06, later the same day)

- `qmltestrunner -input tests`: **62 passed, 0 failed**. New: `tst_match.qml` covers the fzf-style scorer (word starts and exact titles first, gaps and mid-word letters cost, single mid-word letters and scattered letters in prose never match, paths and keywords rank below titles, the abbreviations `prefp`, `keysepro`, `setaiprv`, `kspa`, `ai prov`/`prov ai`, `sysshut`), and `tst_settingstree.qml` drives the flattened settings tree with the real AI schema: every abbreviation above ranks Keystroke Settings › AI & Web Search › Preferred assistant first from the root, `prefcla` selects its Claude choice, `dens comf` selects Comfortable density, scoped searches use breadcrumbs relative to the screen, list-only rows never match, ids are unique, `chrome` finds nothing in settings.
- Timing probe inside the suite: a keystroke over 700 rows where every row matches on three haystacks costs about 10 ms in the QML engine (Qt 6.11); queries that match few rows cost well under 1 ms. The real root has roughly 550 candidates.
- `tests/tz_helper_check.py`: 6/6. `tests/lint.sh`: only the pre-existing Quickshell token noise. `omarchy plugin validate`: pass.
- Not verified live in the shell this round (the checkout was being committed from another session at the time): the ranking above is exercised through the same provider code paths in the unit tests, but the in-shell journey (typing `keysepro` at the root and pressing ↵) is still owed.
- Found while committing: `.gitignore` carried a bare `core` line (a core-dump pattern) that also ignored `core/`, so none of the JavaScript modules had ever been committed. Fixed in the same branch; the files were added byte-identical to the working checkout.

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
