# Keyboard Cleaner

Block every keyboard and pointer for a moment so you can wipe them down without typing, clicking or launching anything. Type `wipe 30s`, press Enter, and a countdown fills the palette while nothing you press or move counts. When it ends, everything works again.

Written by [ozz1ee](https://github.com/ozz1ee-dev) as the Keystroke counterpart of the [`ozz1ee.keyboard-cleaner`](https://github.com/ozz1ee-dev/ozz1ee.keyboard-cleaner) Omalaunch extension, and ported into Keystroke's extension folder when extensions moved into this repository.

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

A block covers exactly the time it is set for. When it ends the keyboard is live again while the countdown view is still open on top, so presses from a cloth — or a key like CapsLock — land where focus is: wipe for as long as the whole cleaning takes, not just for the first few seconds. Idle handling is parked for the whole block, so a 5-minute wipe does not trip the screensaver or the lock screen on the way.

Omarchy maps Caps Lock to Compose and puts the lock itself on **both Shifts together** (`kb_options = compose:caps,shift:both_capslock_cancel` in its `default/hypr/input.lua`), so a cloth pressing both Shift keys turns Caps Lock on — and the CapsLock key cannot turn it back off, because it is Compose. A single lone Shift releases it, which is what the `_cancel` variant is for. Nothing here can stop a keypress on an unblocked keyboard from doing that; wiping while a block is running is what keeps the cloth off the live keys.

The countdown view says how many devices went quiet and when they come back, and turns into *Input restored* when the time is up; Esc closes it. If nothing could be blocked (not on Hyprland, `hyprctl` missing), the view says so instead of showing a countdown over a keyboard that still works.

## Settings

Keystroke Settings → Keyboard Cleaner:

- **Default duration (seconds)**: used by `wipe` with no duration. Default 30, at most 300.
- **Also block mice and touchpads**: on by default. Off leaves the pointer working so you can wipe the keys while still able to click.

Values live under `providers.keyboard-cleaner` in `~/.config/omarchy/keystroke.json`.

## How it blocks

Hyprland can switch an input device off at runtime: `hyprctl eval 'hl.device({ name = "…", enabled = false })'` makes the compositor drop that device's events, and it is the same call Omarchy's own touchpad toggle makes. `bin/keyboard-cleaner` lists the devices with `hyprctl devices -j`, switches each keyboard (and, unless the setting says otherwise, each mouse and touchpad) off, waits, and switches them back on. No device files are opened and no group membership is needed. The setting is not persisted, so a Hyprland reload or restart brings every device back even if the helper were killed outright.

The helper skips virtual keyboards (fcitx, wtype) and blocks everything else Hyprland calls a keyboard or a mouse — including the power button. That last one matters on Apple hardware: `apple-smc-power/lid-events` is a keyboard to Hyprland, and `XF86PowerOff` is bound to Omarchy's power menu (`omarchy-menu toggle system`), whose rows are Screensaver, Lock, Log out, Reboot and Shut down. Left outside the block, a cloth wiping the keyboard opens that menu and the next stray key ends the session, at any block length. The same device still reaches logind, which handles a lid close on its own; only Hyprland's own clamshell binds stop firing while a block runs.

Before anything is switched off the helper waits for the keyboard to come up: a key held at the moment its device goes dead never delivers its release, so the compositor keeps it pressed for the whole block and CapsLock ends up out of step with its LED. It waits half a second first so the Enter that started the block is released cleanly, then polls `hl.is_key_down` until nothing is held, and refuses to start (the view shows *Something is still holding a key down*) rather than leave a stuck key behind.

Idle handling is parked for the duration with `omarchy-shell idle disable` and handed back afterwards. A disabled keyboard feeds no activity, so without this the screensaver appears over the desktop at the screensaver timeout and `omarchy-system-lock` puts up a password prompt at the lock timeout — with a keyboard that cannot type into it. Parking is remembered in `~/.local/state/keyboard-cleaner/idle-parked` (holding the helper's pid), so a block that was killed outright is un-parked the next time the extension loads; a stay-awake you set yourself is never cleared by the block.

It restores every device when the time is up, on SIGTERM, SIGINT or SIGHUP, and on any error, and turning the extension off during a block restores input at once.

## Limits and dependencies

- Hyprland only: it needs `hyprctl` with `eval` (any Omarchy release with the Lua Hyprland config). On another compositor the view reports that nothing was blocked.
- Runs `python3` (the helper) and `hyprctl`; no network, no sudo, no daemons. Nothing runs until you start a block. It writes one temp file for the held-key probe and, while idle is parked, `~/.local/state/keyboard-cleaner/idle-parked` (removed when the block ends).
- The block happens in the compositor, not the kernel: a pressed key still wakes the display from power saving, it just does nothing else.
- A block will not start while a key is held down — otherwise that key's release would be swallowed and it would read as stuck until input comes back. Let go and start again.
- `omarchy-shell idle` is used when Omarchy is there; without it the block still works, only the idle clock keeps running during it.
- One block at a time; starting another while one runs shows the running one.
- Like every extension, this one runs unsandboxed inside your shell with your permissions once you turn it on. `Service.qml` and `bin/keyboard-cleaner` are short; read them first.

## Layout

- `extension.json`: name, version, description, icon, the `wipe` command and its arguments; read without loading any code.
- `Service.qml`: the provider object (`query`, `activate`, `settings`, `patterns`, `view`) and the helper process.
- `BlockView.qml`: the countdown shown over the palette.
- `core/Parser.js`: durations, rows and the helper argv as pure functions.
- `bin/keyboard-cleaner`: the Python helper that talks to Hyprland.
- `tests/tst_parser.qml`: unit tests for the pure functions, run by `bin/keystroke check-extensions`; `tests/test_helper.py`: unit tests for the helper's device selection and quoting (`python3 tests/test_helper.py`).

To try the helper on its own without losing your keyboard, name a harmless device: `bin/keyboard-cleaner --seconds 2 --device sleep-button` prints what it blocked, waits two seconds and restores it. `bin/keyboard-cleaner --seconds 1 --dry-run` prints what a real `wipe` would cover and touches nothing (on Apple hardware the list ends up with `apple-spi-keyboard`, `apple-smc-power/lid-events`, `apple-spi-trackpad` and any mouse). To see the held-key guard, hold a key down and run it: it prints `Something is still holding a key down` instead of blocking.
