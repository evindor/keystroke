#!/usr/bin/env python3
"""The Windows extension inside the real palette, offscreen, with a fake Hyprland.

Keystroke comes from $KEYSTROKE_ROOT, else the checkout this folder sits in,
else the installed plugin (for a copy under ~/.local/share/keystroke/extensions).
This extension is copied into the fake HOME's local extensions folder.

Nothing reaches the real compositor: HYPRLAND_INSTANCE_SIGNATURE and
XDG_RUNTIME_DIR point Quickshell's Hyprland IPC at sockets this script serves
(status, monitors, workspaces, and every dispatch logged and answered "ok"),
and a fake hyprctl on PATH answers `clients -j` from a fixture and logs its
argv. Checked: nothing runs while the extension is off; one `hyprctl clients
-j` per palette open; `>` lists windows most recently used first without the
one you came from; Enter closes the palette and then dispatches
hl.dsp.focus with the window's address only, never its title; `> chrom`
narrows; the root shows windows from two characters, capped, without the
obvious hit crowded out; on an empty workspace the last focused window is
listed (it is not the one you came from); the root switch; turning the
extension off destroys the service.

Run from the repository root: python3 extensions/windows/tests/palette_check.py
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading

here = Path(__file__).resolve().parents[1]
checkout = Path(__file__).resolve().parents[3]
root = Path(os.environ.get("KEYSTROKE_ROOT") or (checkout if (checkout / "Keystroke.qml").is_file()
            else Path.home() / ".config/omarchy/plugins/evindor.keystroke"))

# If a title ever reached a shell, the fake hyprctl would log "dispatch exit".
EVIL = 'x"; hyprctl dispatch exit; echo "$(hyprctl dispatch exit)'
# focusHistoryID 0 is the window the palette was opened from, on workspace 1.
CLIENTS = [
    {"address": "0x5a01", "class": "Alacritty", "title": "nvim ~/Work/omarchy-raycast/README.md", "workspace": {"id": 1, "name": "1"}, "focusHistoryID": 0},
    {"address": "0x5a02", "class": "org.gnome.FileRoller", "title": "Archive Manager - photos.zip", "workspace": {"id": 1, "name": "1"}, "focusHistoryID": 1},
    {"address": "0x5a03", "class": "Alacritty", "title": "Activity: htop on server", "workspace": {"id": 2, "name": "2"}, "focusHistoryID": 2},
    {"address": "0x5a04", "class": "thunderbird", "title": "Thunderbird - Inbox", "workspace": {"id": 2, "name": "2"}, "focusHistoryID": 3},
    {"address": "0x5a05", "class": "gnome-calendar", "title": "Calendar - Thursday", "workspace": {"id": 2, "name": "2"}, "focusHistoryID": 4},
    {"address": "0x5a06", "class": "lichess", "title": "Chess - Match history report", "workspace": {"id": 4, "name": "4"}, "focusHistoryID": 5},
    {"address": "0x5a07", "class": "Alacritty", "title": "Archive: march photos", "workspace": {"id": 4, "name": "4"}, "focusHistoryID": 6},
    {"address": "0x5a08", "class": "obsidian", "title": "Notes", "workspace": {"id": -98, "name": "special:scratchpad"}, "focusHistoryID": 7},
    {"address": "0x5a09", "class": "chromium", "title": "GitHub - keystroke - Chromium", "workspace": {"id": 5, "name": "5"}, "focusHistoryID": 8},
    {"address": "0x5a0a", "class": "evil", "title": EVIL, "workspace": {"id": 5, "name": "5"}, "focusHistoryID": 9},
    {"address": "0x5a0b; exit", "class": "bad", "title": "Bad address", "workspace": {"id": 5, "name": "5"}, "focusHistoryID": 10},
    {"address": "0x5a0c", "class": "ghost", "title": "Unmapped", "mapped": False, "workspace": {"id": 5, "name": "5"}, "focusHistoryID": 11},
]
for c in CLIENTS:
    c.setdefault("mapped", True)
    c.setdefault("hidden", False)

with tempfile.TemporaryDirectory(prefix="keystroke-windows-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__", "experiments"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text().replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))
    shutil.copytree(here, work / ".local/share/keystroke/extensions/windows", ignore=shutil.ignore_patterns("__pycache__"))
    config = work / ".config"
    (config / "omarchy").mkdir(parents=True)
    (config / "omarchy/keystroke.json").write_text(json.dumps({"version": 1, "matching": {"mode": "off"}}))

    fake = work / "bin"
    fake.mkdir()
    (work / "clients.json").write_text(json.dumps(CLIENTS))
    hyprctl_log = work / "hyprctl.log"
    (fake / "hyprctl").write_text(f'''#!/bin/sh
printf '%s\\n' "$*" >> {str(hyprctl_log)!r}
[ "$*" = "clients -j" ] && exec cat {str(work / "clients.json")!r}
exit 1
''')
    (fake / "hyprctl").chmod(0o755)

    # A fake Hyprland: the request socket answers what Quickshell asks at
    # start and logs every dispatch; "keystroke-test-workspace N" (sent by the
    # test through the same dispatch) switches the focused workspace with a
    # workspacev2 event.
    his = "keystroke-test"
    sockets = work / "hypr" / his
    sockets.mkdir(parents=True)
    dispatches, events, active = [], [], {"workspace": 1}
    def answer(request):
        if request == "j/status":
            return json.dumps({"configProvider": "lua"})
        if request == "j/monitors":
            ws = active["workspace"]
            return json.dumps([{"id": 0, "name": "FAKE-1", "description": "", "x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1,
                                "focused": True, "activeWorkspace": {"id": ws, "name": str(ws)}}])
        if request == "j/workspaces":
            return json.dumps([{"id": i, "name": str(i), "monitor": "FAKE-1", "monitorID": 0, "windows": 1} for i in (1, 2, 3, 4, 5)])
        if request == "j/clients":
            return "[]"
        if request.startswith("dispatch "):
            body = request[len("dispatch "):]
            if body.startswith("keystroke-test-workspace "):
                ws = int(body.split()[1])
                active["workspace"] = ws
                for conn in list(events):
                    try: conn.sendall(f"workspacev2>>{ws},{ws}\n".encode())
                    except OSError: pass
            else:
                dispatches.append(body)
            return "ok"
        return "unknown request"
    def serve_requests(server):
        while True:
            try: conn, _ = server.accept()
            except OSError: return
            with conn:
                data = conn.recv(65536).decode()
                conn.sendall(answer(data).encode())
    def serve_events(server):
        while True:
            try: conn, _ = server.accept()
            except OSError: return
            events.append(conn)
    servers = []
    for name, loop in ((".socket.sock", serve_requests), (".socket2.sock", serve_events)):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(str(sockets / name))
        s.listen(16)
        servers.append(s)
        threading.Thread(target=loop, args=(s,), daemon=True).start()

    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import Quickshell.Hyprland
import "project"
ShellRoot {
  id: test
  property int stage: 0
  property int failures: 0
  property real since: 0
  Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
  function service() { var s = palette.registry.services["windows"]; return s ? s.instance : null }
  function check(ok, msg) { if (!ok) { failures++; console.log("FAIL", msg) } }
  function items() { return palette.rows.filter(function(r) { return r.providerKey === "windows" && !r.disabled }) }
  function titles(rows) { return (rows || items()).map(function(r) { return r.title }) }
  function configure(on, rootSearch) {
    palette.applyConfigText(JSON.stringify({ version: 1, matching: { mode: "off" }, providers: {
      windows: { enabled: on, root: rootSearch }
    } }))
  }
  function busy() { return palette.pending || (service() && service().worker.running) }
  Timer { interval: 120; running: true; repeat: true; onTriggered: {
    if (busy()) return
    switch (test.stage) {
    case 0:
      if (!palette.registry.manifests["windows"] || !Hyprland.focusedWorkspace || !Hyprland.usingLua) return
      check(!service(), "disabled extension is not loaded")
      palette.open(JSON.stringify({ query: "> chrom" }))
      test.stage++; return
    case 1:
      check(items().length === 0, "off: > is not routed to it")
      check(palette.activeCommand === null, "off: no command is recognised")
      palette.cancel()
      configure(true, true)
      test.stage++; return
    case 2:
      if (!service()) return
      palette.open(JSON.stringify({ query: ">" }))
      test.stage++; return
    case 3:
      if (!service().list) return
      check(palette.activeCommand && palette.activeCommand.key === "windows" && palette.activeCommand.rest === "", "> is the declared command")
      var t = titles()
      check(t.indexOf("nvim ~/Work/omarchy-raycast/README.md") < 0, "the window you came from is left out: " + t.join(" | "))
      check(t.length === 9 && t[0] === "Archive Manager - photos.zip" && t[7] === "GitHub - keystroke - Chromium", "most recently used first: " + t.join(" | "))
      check(t.indexOf("Bad address") < 0 && t.indexOf("Unmapped") < 0, "bad address and unmapped windows are skipped")
      var notes = items().filter(function(r) { return r.title === "Notes" })[0]
      check(notes && notes.subtitle === "obsidian \\u00b7 Scratchpad", "scratchpad label: " + (notes && notes.subtitle))
      check(items()[0].section === "Windows" && items()[0].verb === "Switch to", "section and verb")
      // The evil title is a row title, nothing more.
      var evil = items().filter(function(r) { return r.action && r.action.address === "0x5a0a" })[0]
      check(!!evil, "a window with shell syntax in its title is listed as text")
      palette.activateAt(palette.rows.indexOf(evil))
      check(!palette.opened, "Enter closes the palette first")
      test.since = Date.now()
      test.stage++; return
    case 4:
      if (Date.now() - test.since < 400) return
      palette.open(JSON.stringify({ query: "> chrom" }))
      test.stage++; return
    case 5:
      check(titles()[0] === "GitHub - keystroke - Chromium" && titles().length < 4, "> chrom narrows, the hit first: " + titles().join(" | "))
      check(items()[0] && items()[0].subtitle === "chromium \\u00b7 Workspace 5", "subtitle: " + (items()[0] && items()[0].subtitle))
      palette.open(JSON.stringify({ query: "c" }))
      test.stage++; return
    case 6:
      check(items().length === 0, "one character is not enough at the root: " + titles().join(" | "))
      palette.open(JSON.stringify({ query: "chr" }))
      test.stage++; return
    case 7:
      check(items().length <= 5, "the root is capped: " + items().length)
      check(titles().indexOf("GitHub - keystroke - Chromium") >= 0, "the obvious hit is not crowded out at the root: " + titles().join(" | "))
      palette.cancel()
      Hyprland.dispatch("keystroke-test-workspace 3")
      test.stage++; return
    case 8:
      if (!Hyprland.focusedWorkspace || Hyprland.focusedWorkspace.id !== 3) return
      palette.open(JSON.stringify({ query: ">" }))
      test.stage++; return
    case 9:
      check(titles()[0] === "nvim ~/Work/omarchy-raycast/README.md", "on an empty workspace the last focused window is listed first: " + titles().slice(0, 3).join(" | "))
      configure(true, false)
      palette.open(JSON.stringify({ query: "chrom" }))
      test.stage++; return
    case 10:
      check(items().length === 0, "root search can be turned off")
      palette.open(JSON.stringify({ query: "> chrom" }))
      test.stage++; return
    case 11:
      check(titles()[0] === "GitHub - keystroke - Chromium", "the command still works with root search off: " + titles().join(" | "))
      palette.cancel()
      configure(false, true)
      test.stage++; return
    case 12:
      if (service()) return
      console.log(test.failures ? "FAIL windows palette" : "PASS windows palette")
      Qt.quit(); test.stage++; return
    }
  } }
  Timer { interval: 20000; running: true; onTriggered: {
    console.log("FAIL timeout", test.stage, JSON.stringify(palette.registry.problems), palette.errorMessage, titles(palette.rows).join(" | ")); Qt.quit()
  } }
}
''')
    env = dict(os.environ, HOME=str(work), XDG_CONFIG_HOME=str(config), XDG_RUNTIME_DIR=str(work),
               HYPRLAND_INSTANCE_SIGNATURE=his, PATH=f"{fake}:/usr/bin:/bin", QT_QPA_PLATFORM="offscreen",
               QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    for key in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        env.pop(key, None)
    try:
        result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=40)
    finally:
        for s in servers:
            s.close()
    output = result.stdout + result.stderr
    assert "PASS windows palette" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    calls = hyprctl_log.read_text().splitlines()
    # The host asks hyprctl for its own things (options, binds, devices); this extension asks for clients only.
    assert [c for c in calls if c.startswith("clients")] == ["clients -j"] * 7, calls   # one per open while on, none while off
    assert not [c for c in calls if "dispatch" in c], calls
    assert dispatches == ['hl.dsp.focus({ window = "address:0x5a0a" })'], dispatches
    print("PASS windows palette: off until switched on, one hyprctl per open, MRU listing, close-then-focus over IPC with the address only, command and root search, empty-workspace focus, root switch, unload")
