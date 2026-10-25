#!/usr/bin/env python3
"""Private text in the real offscreen palette: copies and picker input reach their
process on stdin, never as an argument other local users could read in /proc."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix="keystroke-palette-copy-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(
        ".git", ".claude", ".agents", ".codex", "tests", "__pycache__", "experiments"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text().replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))

    fake = work / "bin"
    fake.mkdir()
    # One JSON line per wl-copy run: its arguments and what arrived on stdin.
    (fake / "wl-copy").write_text('''#!/usr/bin/python3
import json, os, sys
with open(os.environ["COPY_LOG"], "a") as out:
    out.write(json.dumps({"args": sys.argv[1:], "stdin": sys.stdin.read()}) + "\\n")
''')
    # Every bash the palette starts logs its arguments, then runs for real.
    (fake / "bash").write_text('''#!/usr/bin/python3
import json, os, sys
with open(os.environ["BASH_LOG"], "a") as out:
    out.write(json.dumps(sys.argv[1:]) + "\\n")
os.execv("/bin/bash", ["bash"] + sys.argv[1:])
''')
    (fake / "wl-paste").write_text("#!/bin/sh\nexit 1\n")
    for name in ("wl-copy", "bash", "wl-paste"):
        (fake / name).chmod(0o755)
    config = work / ".config/omarchy/keystroke.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"version": 1, "matching": {"mode": "off"}}))

    secret = "token=hunter2\nline two -- $(id) 'quoted' é"
    typed = "hunter2 $(id) 'q' é"
    selection, done = work / "selection", work / "done"
    report = work / "Docs/My Report #1.pdf"
    report.parent.mkdir()
    report.write_text("report")
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
 id: test
 property int stage: 0
 property int failures: 0
 function check(ok, msg) { if (!ok) { failures++; console.log("FAIL", msg) } else console.log("ok", msg) }
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 Timer { interval: 100; repeat: true; running: true; onTriggered: {
   switch (test.stage) {
   case 0:
     if (!palette.registryEntry("calculator")) return
     palette.open(JSON.stringify({query: "2+3"}))
     test.stage++; return
   case 1:
     if (palette.pending || !palette.rows.length) return
     check(palette.rows[0].action.type === "copy" && palette.rows[0].action.text === "5", "calculator answer copies")
     palette.selected = 0
     palette.activate() // The same path as the Enter key handler.
     test.stage++; return
   case 2:
     if (palette.opened) return
     palette.open(JSON.stringify({query: ""}))
     palette.perform({type: "copy", text: __SECRET__}, {})
     test.stage++; return
   case 3:
     if (palette.opened) return
     // What omarchy-menu-input sends, then typing and Enter.
     palette.openDmenu({mode: "input", prompt: "Password", selectionFile: __SELECTION__, doneFile: __DONE__})
     palette.setQuery(__TYPED__)
     palette.activate()
     test.stage++; return
   case 4:
     if (palette.opened) return
     palette.open(JSON.stringify({query: "~my report"}))
     test.stage++; return
   case 5:
     var file = palette.rows.filter(function(r) { return r.title === "My Report #1.pdf" })[0]
     if (palette.pending || !file) return
     palette.selected = palette.rows.indexOf(file)
     var labels = palette.footerActions.map(function(a) { return a.label + " " + a.key })
     check(labels.indexOf("Copy file ctrl C") >= 0 && labels.indexOf("Copy path ctrl ⇧ C") >= 0, "footer names both copy keys: " + labels)
     check(palette.copySelection(false), "Ctrl+C copies the file")
     test.stage++; return
   case 6:
     if (palette.opened) return
     palette.open(JSON.stringify({query: "~my report"}))
     test.stage++; return
   case 7:
     var again = palette.rows.filter(function(r) { return r.title === "My Report #1.pdf" })[0]
     if (palette.pending || !again) return
     palette.selected = palette.rows.indexOf(again)
     check(palette.copySelection(true), "Ctrl+Shift+C copies the path")
     test.stage++; return
   case 8:
     if (palette.opened) return
     palette.open(JSON.stringify({query: "2+3"}))
     test.stage++; return
   case 9:
     if (palette.pending || !palette.rows.length) return
     palette.selected = 0
     check(!palette.copySelection(false) && palette.opened, "a row without copy actions leaves Ctrl+C alone")
     palette.cancel()
     console.log(test.failures ? "FAIL palette private text" : "PASS palette private text")
     Qt.quit(); test.stage++; return
   }
 } }
 Timer { interval: 20000; running: true; onTriggered: { console.log("FAIL timeout", test.stage, palette.errorMessage); Qt.quit() } }
}
'''.replace("__SECRET__", json.dumps(secret)).replace("__TYPED__", json.dumps(typed))
   .replace("__SELECTION__", json.dumps(str(selection))).replace("__DONE__", json.dumps(str(done))))
    log, bash_log = work / "copies.jsonl", work / "bash.jsonl"
    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work),
               PATH=f"{fake}:{os.environ.get('PATH', '')}", COPY_LOG=str(log), BASH_LOG=str(bash_log),
               QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic",
               QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    env["OMARCHY_LANGUAGE_FILE"] = str(work / "test-language")
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env,
                            capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert "PASS palette private text" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    copies = [json.loads(line) for line in log.read_text().splitlines()]
    assert copies == [{"args": [], "stdin": "5"}, {"args": [], "stdin": secret},
                      {"args": ["--type", "text/uri-list"], "stdin": "file://" + str(work).replace(" ", "%20") + "/Docs/My%20Report%20%231.pdf\r\n"},
                      {"args": [], "stdin": str(report)}], copies
    deadline = time.monotonic() + 5
    while not done.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert done.exists(), "the picker completes"
    assert selection.read_text() == typed + "\n", selection.read_text()
    argvs = bash_log.read_text() if bash_log.exists() else ""
    assert "hunter2" not in argvs, argvs
    print("PASS palette private text: copies, file and path copies and picker input reach their process on stdin, byte for byte, never as arguments")
