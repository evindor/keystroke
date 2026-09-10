# Timer

Countdown timers for the [Keystroke](../../README.md) command palette. Type `timer 10m tea`, press Enter, and the countdown shows next to the menu button in the bar until a chime sounds and a notification tells you the tea is ready. Timers keep running after the palette closes because the extension's service object outlives the window.

This is also the reference extension: small enough to read in one sitting, complete enough to copy. It shows a provider with settings, answer and list rows, a scoped screen, confirmations, state that outlives the palette, a bar item and unit tests. To write your own, copy this folder and follow [Build an extension](../../CONTRIBUTING.md#build-an-extension).

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

`timer` is the extension's declared prefix: typing it shows *Set a timer · duration: …* under the search field and the `<duration> [name]` placeholders after the caret, `/` lists it with every other command, and Settings → Timer → **Prefix** renames it (`tm 10m tea`). The aliases above keep working whatever the prefix is.

Enter starts the timer and closes the palette. From that moment the soonest timer counts down in the bar, right after the Keystroke menu button (`󰔛 9:59`, with `+1` when another is running behind it); hovering shows its label and end time, and pressing it opens the Timers screen. **Timers** at the palette root (or the running timer rows themselves) opens the same list: each row shows the remaining time and Enter cancels it after a confirmation. When a timer ends the chime sounds and you get an Omarchy notification.

## Settings

Keystroke Settings → Timer:

- **Default length (minutes)**: used when no duration is given. Default 5.
- **Sound when a timer ends**: Off, Chime (default), Bell or Alarm. The three sounds are the freedesktop sound theme in `/usr/share/sounds/freedesktop/stereo`, which Omarchy has through libcanberra.
- **Custom sound file**: a path to any audio file (`~` is expanded), played instead of the built-in sound while the sound is not Off.
- **Notify when a timer ends**: on by default.
- **Show the countdown in the bar**: on by default. Off keeps the bar as it was; the Timers screen still shows the countdowns.

Values live under `providers.timer` in `~/.config/omarchy/keystroke.json`.

## Limits and dependencies

- Timers are kept in memory. Restarting `omarchy-shell` (for example after an Omarchy update) forgets running timers.
- No setup step and no network. Notifications go through Omarchy's own `omarchy-notification-send`; the sound is played by `pw-play` (PipeWire), falling back to `mpv` and then `paplay`, and a sound file that does not exist is skipped silently. No sudo, no daemons.
- The countdown in the bar is Keystroke's own bar widget: it shows only where that widget is in the bar (Omarchy puts the menu button on the left by default) and, like Omarchy's other text widgets, not on a vertical bar.
- Like every extension, this one runs unsandboxed inside your shell with your permissions once you turn it on. `Service.qml` is short; read it first.

## Layout

- `extension.json`: name, version, description, icon and `apiVersion` for the Extensions screen; read without loading any code.
- `Service.qml`: the provider object (`query`, `activate`, `opened`, `settings`), the service state, the once-a-second clock that fires sounds and notifications and refreshes the bar item.
- `core/Timer.js`: parsing, row building, the sound argv and the bar item as pure functions.
- `tests/tst_timer.qml`: unit tests for the pure functions, run by `bin/keystroke check-extensions`.
