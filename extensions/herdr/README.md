# Herdr

Jump to anything inside [Herdr](https://herdr.dev), the terminal workspace
manager for coding agents, from Keystroke. Turn on **Extensions > Herdr**,
then type `%` to list every agent, workspace, tab, pane and session of every
running Herdr session, or `% claude` to narrow it. Enter focuses the target in
Herdr and brings forward the terminal window that shows the session; when no
window shows it, a terminal attached to the session opens instead.

Rows are grouped like [Everything](https://github.com/brianblakely/omarchy-everything):
agents first (with their status: Working, Idle, ...), then workspaces, tabs,
panes and sessions. A pane that runs an agent is listed once, as the agent.

To bind a key straight to the list:

```sh
omarchy-shell shell summon omarchy.menu '{"scope":"herdr","title":"Herdr"}'
```

## Settings

- **Show agents and workspaces in the main search** (on): agent and workspace
  names match at the root from two characters on. Tabs, panes and sessions
  appear only after `%` or on this extension's screen.
- **List panes** (on) and **List tabs** (on).
- The `%` prefix can be renamed under `providers.herdr` in Keystroke's
  configuration.

## Data access and dependencies

Needs Python 3 (standard library only) and `herdr` on `PATH`.

On every palette open, the service runs `python3 bin/herdr.py list` once,
asynchronously. The helper:

- runs `herdr session list --json`;
- for each running session whose socket is a Unix socket owned by you, sends
  one `session.snapshot` request over that socket (the same JSON-lines API
  Herdr's own CLI uses) and reads one line back (at most 8 MB);
- runs `hyprctl -j clients` and reads `/proc/*/stat` and `/proc/*/cmdline` to
  find which terminal window runs a `herdr` client for each session.

Queries only filter the parsed result; nothing runs per keystroke.

Activating a row closes the palette and runs `python3 bin/herdr.py focus
<session> <kind> <id>`, which sends one `workspace.focus`, `tab.focus` or
`pane.focus` request to the session socket, then focuses the session's window
with `hyprctl dispatch`, or runs `omarchy-launch-terminal herdr session attach
<session>` when no window shows it. Ids are passed as separate argv elements
and rejected if empty or containing control characters.

Nothing is written to disk and nothing touches the network.

The helper is adapted from Everything's Herdr adapter by Brian Blakely (MIT).

## Tests

```sh
python3 -m unittest discover -s tests -p 'test_*.py'   # helper, against a fake herdr and socket
```
