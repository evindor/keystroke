# Timer

Countdown timers for the [Keystroke](../../README.md) command palette. Type `timer 10m tea`, press Enter, and a notification tells you when the tea is ready. Timers keep running after the palette closes because the extension's service object outlives the window.

This is also the reference extension: small enough to read in one sitting, complete enough to copy. It shows a provider with settings, answer and list rows, a scoped screen, confirmations, state that outlives the palette, and unit tests. To write your own, copy this folder and follow [Build an extension](../../CONTRIBUTING.md#build-an-extension).

## Turn it on

Extensions ship with Keystroke switched off. Type `ext`, open **Extensions → Timer**, and confirm **Enabled** (or Keystroke Settings → Timer → Enabled).

## Use

| Query | Result |
| --- | --- |
| `timer 10m tea` | 10 minutes, labelled *tea* |
| `timer 1h30m` · `timer 1:30:00` | 1 h 30 min |
| `timer 90` | a bare number after `timer` is minutes |
| `timer tea` | the default length (Settings → Timer → Default length) |
| `10 min tea` · `45s` | works without the prefix when a unit is present, ranked as an ordinary item |
| `countdown …` · `remind me in …` | aliases for `timer` |

Enter starts the timer and closes the palette. **Timers** at the palette root (or the running timer rows themselves) opens the list: each row shows the remaining time and Enter cancels it after a confirmation. When a timer ends you get an Omarchy notification.

## Settings

Keystroke Settings → Timer:

- **Default length (minutes)**: used when no duration is given. Default 5.
- **Notify when a timer ends**: on by default.

Values live under `providers.timer` in `~/.config/omarchy/keystroke.json`.

## Limits and dependencies

- Timers are kept in memory. Restarting `omarchy-shell` (for example after an Omarchy update) forgets running timers.
- No external dependencies and no setup step. Notifications go through Omarchy's own `omarchy-notification-send`; no sudo, no network, no daemons.
- Like every extension, this one runs unsandboxed inside your shell with your permissions once you turn it on. `Service.qml` is short; read it first.

## Layout

- `extension.json`: name, version, description, icon and `apiVersion` for the Extensions screen; read without loading any code.
- `Service.qml`: the provider object (`query`, `activate`, `opened`, `settings`) and the service state.
- `core/Timer.js`: parsing and row building as pure functions.
- `tests/tst_timer.qml`: unit tests for the pure functions, run by `bin/keystroke check-extensions`.
