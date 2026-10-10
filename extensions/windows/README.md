# Windows

Switch to any open Hyprland window from Keystroke. Turn on **Extensions >
Windows**, then type `>` to list every window, most recently used first, or
`> firefox` to narrow it. Enter focuses the window, switching workspace if
needed.

The window you came from is left out by default, so `>` then Enter goes back
to the previous window, like Alt+Tab. Opened from an empty workspace, nothing
is left out: the window you used last is listed first.

To bind a key straight to the window list:

```sh
omarchy-shell shell summon omarchy.menu '{"scope":"windows","title":"Windows"}'
```

## Settings

- **Show windows in the main search** (on by default): window titles and
  classes match at the root from two characters on. Off: windows appear only
  after `>` or on this extension's screen.
- **Windows in the main search** (5): at most this many windows mix into the
  root results.
- **List the focused window** (off): also list the window you came from, last.
- The `>` prefix can be renamed under `providers.windows` in Keystroke's
  configuration.

Each row shows the window title, its application class and its workspace
(`Scratchpad` for Omarchy's special workspace, the name for named ones). The
icon comes from the application's desktop entry.

## Data access and dependencies

On every palette open the service runs `hyprctl clients -j` once,
asynchronously, and keeps the parsed list in memory until the next open. It
also reads the focused workspace from the shell's own connection to Hyprland
(Quickshell's Hyprland IPC), to tell the window you came from. Queries only
filter that list; nothing runs per keystroke. Focusing a window
closes the palette first and then sends one Hyprland dispatch
(`hl.dsp.focus({ window = "address:0x..." })` on a Lua config,
`focuswindow address:0x...` otherwise) through Quickshell's Hyprland IPC.
Addresses are validated as hex before they reach the dispatch. No files are
written, nothing touches the network.

Needs Hyprland. Inspired by
[Everything](https://github.com/brianblakely/omarchy-everything) by Brian
Blakely.
