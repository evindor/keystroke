> Historical checkpoints below include retired local-model implementations. Current build: [Codex integration verification](codex-integration-verification.md).


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
