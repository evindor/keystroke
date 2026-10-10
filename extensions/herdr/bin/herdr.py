#!/usr/bin/env python3
"""List and focus Herdr sessions, workspaces, tabs, panes and agents.

`herdr.py list` prints one JSON object: every running Herdr session with its
live snapshot (read over the session's own socket, the request Herdr's CLI
makes) and the Hyprland window that hosts it, if exactly one does.

`herdr.py focus <session> <kind> <id>` focuses a workspace, tab or pane inside
the session, then brings its terminal window forward, or opens a terminal
attached to the session when none shows it.

Standard library only. Adapted from Everything's Herdr adapter,
https://github.com/brianblakely/omarchy-everything (everything/providers/herdr.py).
Copyright (c) 2026 Brian Blakely. MIT License; see LICENSE at Keystroke's root.
"""
import json
import os
import socket
import stat
import subprocess
import sys

KINDS = {"workspace": "workspace.focus", "tab": "tab.focus", "pane": "pane.focus"}
MAX_BYTES = 8 * 1024 * 1024


def run(argv, timeout=1.5):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r if r.returncode == 0 else None


def native_id(value):
    return isinstance(value, str) and value.strip() != "" and not any(c in value for c in "\x00\r\n")


def safe_socket(path):
    if not isinstance(path, str) or not os.path.isabs(path):
        return False
    try:
        info = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    return info.st_uid == os.getuid() and stat.S_ISSOCK(info.st_mode)


def request(path, method, params, timeout=1.1):
    """One JSON line out, one JSON line back."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(path)
        s.sendall((json.dumps({"id": "keystroke:herdr", "method": method, "params": params}) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
            if len(data) > MAX_BYTES:
                raise ValueError("Herdr returned an oversized response")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("Herdr returned something other than an object")
    if isinstance(value.get("error"), dict):
        raise ValueError(str(value["error"].get("message") or "Herdr request failed"))
    return value.get("result")


def sessions():
    r = run(["herdr", "session", "list", "--json"])
    if r is None:
        return None
    try:
        value = json.loads(r.stdout)
    except ValueError:
        return None
    items = value.get("sessions", []) if isinstance(value, dict) else []
    return [s for s in items if isinstance(s, dict)]


# --- which Hyprland window shows a session -----------------------------------

def proc_table():
    table = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", "rb") as f:
                fields = f.read().rsplit(b")", 1)[1].split()
            with open(f"/proc/{entry}/cmdline", "rb") as f:
                argv = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
        except (OSError, IndexError):
            continue
        table[int(entry)] = {"ppid": int(fields[1]), "argv": argv}
    return table


def client_session(argv):
    """The session a running `herdr` client is attached to, or None for a server or another tool."""
    if not argv or os.path.basename(argv[0]) != "herdr" or "server" in argv:
        return None
    # A --remote client shows another machine's session, a --no-session one runs its own.
    if any(a in ("--remote", "--no-session") or a.startswith("--remote=") for a in argv):
        return None
    name = "default"
    for i, arg in enumerate(argv):
        if arg.startswith("--session="):
            name = arg[len("--session="):]
        elif i + 1 < len(argv) and arg == "--session":
            name = argv[i + 1]
        elif i + 1 < len(argv) and arg == "attach" and i > 0 and argv[i - 1] == "session":
            name = argv[i + 1]
    # `herdr <subcommand> ...` is a one-off CLI call, not a client showing the session.
    if len(argv) > 1 and argv[1] in ("api", "workspace", "worktree", "tab", "pane", "agent", "notification",
                                     "status", "config", "channel", "integration", "completion", "update"):
        return None
    if len(argv) > 2 and argv[1] == "session" and argv[2] != "attach":
        return None
    return name


def hyprland_clients():
    r = run(["hyprctl", "-j", "clients"], timeout=1.0)
    try:
        value = json.loads(r.stdout) if r else []
    except ValueError:
        value = []
    return [c for c in value if isinstance(c, dict) and c.get("mapped") is not False]


def address(value):
    a = str(value or "").strip().lower()
    if a and not a.startswith("0x"):
        a = "0x" + a
    return a if len(a) > 2 and all(ch in "0123456789abcdef" for ch in a[2:]) and len(a) <= 18 else ""


def hosts(table, clients):
    """session name -> list of window addresses that show it, most recently focused first."""
    by_pid = {}
    for c in clients:
        by_pid.setdefault(int(c.get("pid") or 0), []).append(c)
    out = {}
    for pid, p in table.items():
        name = client_session(p["argv"])
        if name is None:
            continue
        seen, cursor = set(), pid
        while cursor > 1 and cursor not in seen:
            seen.add(cursor)
            if cursor in by_pid:
                # One terminal process can own several windows (foot --server); only an unambiguous one counts.
                if len(by_pid[cursor]) == 1:
                    c = by_pid[cursor][0]
                    out.setdefault(name, []).append((c.get("focusHistoryID", 999), address(c.get("address"))))
                break
            cursor = table.get(cursor, {}).get("ppid", 0)
    return {k: [a for _, a in sorted(set(v)) if a] for k, v in out.items()}


# --- commands ----------------------------------------------------------------

def list_command():
    found = sessions()
    if found is None:
        print(json.dumps({"sessions": [], "error": "Herdr is not installed or did not answer"}))
        return 0
    running = [s for s in found if s.get("running") is True]
    # Walking /proc and asking Hyprland is only worth it when a session is up.
    shown = hosts(proc_table(), hyprland_clients()) if running else {}
    out = []
    for s in running:
        name = str(s.get("name") or "default")
        path = s.get("socket_path")
        if not safe_socket(path):
            continue
        try:
            result = request(path, "session.snapshot", {})
        except (OSError, ValueError) as e:
            out.append({"name": name, "error": str(e)})
            continue
        if not isinstance(result, dict) or not isinstance(result.get("snapshot"), dict):
            continue
        out.append({"name": name, "windows": shown.get(name, []), "snapshot": result["snapshot"]})
    print(json.dumps({"sessions": out}))
    return 0


def focus_window(addr):
    expression = 'hl.dsp.focus({ window = "address:%s" })' % addr
    r = run(["hyprctl", "dispatch", expression], timeout=1.0)
    if r is None or r.stdout.strip() not in ("", "ok"):
        run(["hyprctl", "dispatch", "focuswindow", "address:" + addr], timeout=1.0)


def focus_command(name, kind, target):
    valid_kind = kind in KINDS or kind == "session"
    if not native_id(name) or not valid_kind or (kind != "session" and not native_id(target)):
        print("refusing an invalid target", file=sys.stderr)
        return 2
    session = next((s for s in sessions() or [] if str(s.get("name") or "default") == name and s.get("running") is True), None)
    if not session or not safe_socket(session.get("socket_path")):
        print(f"Herdr session {name} is not running", file=sys.stderr)
        return 1
    if kind in KINDS:
        try:
            request(session["socket_path"], KINDS[kind], {kind + "_id": target}, timeout=1.0)
        except (OSError, ValueError) as e:
            print(f"Herdr could not focus that {kind}: {e}", file=sys.stderr)
            return 1
    windows = hosts(proc_table(), hyprland_clients()).get(name, [])
    if windows:
        focus_window(windows[0])
    else:
        subprocess.Popen(["omarchy-launch-terminal", "herdr", "session", "attach", name],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return 0


def main(argv):
    if argv[1:2] == ["list"]:
        return list_command()
    if len(argv) == 5 and argv[1] == "focus":
        return focus_command(argv[2], argv[3], argv[4])
    print("usage: herdr.py list | focus <session> <workspace|tab|pane|session> <id>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
