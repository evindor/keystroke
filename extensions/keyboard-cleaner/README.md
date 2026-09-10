# Keyboard Cleaner

Block every keyboard and pointer for a moment so you can wipe them down without typing, clicking or launching anything. Type `wipe 30s`, press Enter, and a countdown fills the palette while nothing you press or move counts. When it ends, everything works again.

Written by [ozz1ee](https://github.com/radiohost-cloud) as the Keystroke counterpart of the [`ozz1ee.keyboard-cleaner`](https://github.com/radiohost-cloud/ozz1ee.keyboard-cleaner) Omalaunch extension, and ported into Keystroke's extension folder when extensions moved into this repository.

## Turn it on

Extensions ship with Keystroke switched off. Type `ext`, open **Extensions → Keyboard Cleaner**, and confirm **Enabled** (or Keystroke Settings → Keyboard Cleaner → Enabled).

## Use

| Query | Result |
| --- | --- |
| `wipe 30s` | 30 seconds |
| `wipe 2m` · `wipe 2 minutes` · `wipe 1m30s` | 2 minutes, 2 minutes, 1 minute 30 seconds |
| `wipe 90` | a bare number after `wipe` is seconds |
| `wipe` | the default length (Settings → Keyboard Cleaner → Default duration) |
| `wipe 30s kitchen` | trailing words are a note shown next to the countdown |
| `block 30s` · `clean 2 minutes` · `wash 45s` · `block` | the same without the prefix, ranked as a *Continue with* row |
| `30s` · `5m` | a bare duration also offers a block, below the Timer's row |

`wipe` is the extension's declared prefix: typing it shows *Block input to wipe the keyboard · duration: …* under the search field, `/` lists it with every other command, and Settings → Keyboard Cleaner → **Prefix** renames it. The other verbs keep working whatever the prefix is.

Enter starts the block. Anything over a minute asks first, because once the block runs nothing you press can cancel it. The maximum is 5 minutes. **Keyboard Cleaner** at the palette root opens the extension's own screen with three fixed lengths (15 seconds, 30 seconds, 1 minute).

The countdown view says how many devices went quiet and when they come back, and turns into *Input restored* when the time is up; Esc closes it. If nothing could be blocked (not on Hyprland, `hyprctl` missing), the view says so instead of showing a countdown over a keyboard that still works.

## Settings

Keystroke Settings → Keyboard Cleaner:

- **Default duration (seconds)**: used by `wipe` with no duration. Default 30, at most 300.
- **Also block mice and touchpads**: on by default. Off leaves the pointer working so you can wipe the keys while still able to click.

Values live under `providers.keyboard-cleaner` in `~/.config/omarchy/keystroke.json`.

## How it blocks

Hyprland can switch an input device off at runtime: `hyprctl eval 'hl.device({ name = "…", enabled = false })'` makes the compositor drop that device's events, and it is the same call Omarchy's own touchpad toggle makes. `bin/keyboard-cleaner` lists the devices with `hyprctl devices -j`, switches each keyboard (and, unless the setting says otherwise, each mouse and touchpad) off, waits, and switches them back on. No device files are opened and no group membership is needed. The setting is not persisted, so a Hyprland reload or restart brings every device back even if the helper were killed outright.

The helper skips virtual keyboards (fcitx, wtype) and leaves every power and lid button alone — the ones named `power-button`/`sleep-button` and anything Hyprland lists as a switch, whatever the kernel calls it — so they remain a way out. It waits half a second before switching anything off so the Enter that started it is released cleanly. It restores every device when the time is up, on SIGTERM, SIGINT or SIGHUP, and on any error, and turning the extension off during a block restores input at once.

## Limits and dependencies

- Hyprland only: it needs `hyprctl` with `eval` (any Omarchy release with the Lua Hyprland config). On another compositor the view reports that nothing was blocked.
- Runs `python3` (the helper) and `hyprctl`; no network, no files written, no sudo, no daemons. Nothing runs until you start a block.
- The block happens in the compositor, not the kernel: a pressed key still wakes the display from power saving, it just does nothing else.
- A key held down at the moment of blocking may register its release only after input is back; the half-second grace covers the Enter that starts the block.
- One block at a time; starting another while one runs shows the running one.
- Like every extension, this one runs unsandboxed inside your shell with your permissions once you turn it on. `Service.qml` and `bin/keyboard-cleaner` are short; read them first.

## Layout

- `extension.json`: name, version, description, icon, the `wipe` command and its arguments; read without loading any code.
- `Service.qml`: the provider object (`query`, `activate`, `settings`, `patterns`, `view`) and the helper process.
- `BlockView.qml`: the countdown shown over the palette.
- `core/Parser.js`: durations, rows and the helper argv as pure functions.
- `bin/keyboard-cleaner`: the Python helper that talks to Hyprland.
- `tests/tst_parser.qml`: unit tests for the pure functions, run by `bin/keystroke check-extensions`; `tests/test_helper.py`: unit tests for the helper's device selection and quoting (`python3 tests/test_helper.py`).

To try the helper on its own without losing your keyboard, name a harmless device: `bin/keyboard-cleaner --seconds 2 --device sleep-button` prints what it blocked, waits two seconds and restores it.
