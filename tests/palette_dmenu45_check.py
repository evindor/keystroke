#!/usr/bin/env python3
"""Omarchy 4.5 multi-pickers preserve values, apply results and serialize live changes."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="keystroke-palette-dmenu-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text()
    qml = qml.replace("  id: root\n", "  id: root\n  property alias testCard: card\n  property alias testContent: content\n  property alias testEmptyState: emptyState\n", 1)
    qml = qml.replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))
    (work / "callback.py").write_text("import json,sys,time\nfrom pathlib import Path\nv=json.loads(sys.argv[-1]);time.sleep(0.03)\nwith Path(sys.argv[1]).open('a') as f:f.write(json.dumps(v)+'\\n')\nif 'Bad' in v:sys.exit(1)\nprint(json.dumps(v))\n")
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
  id: test
  property int phase: 0
  property string base: Quickshell.env("HOME")
  function check(ok, msg) { if (!ok) { console.log("FAIL", msg); Qt.quit(); throw Error(msg) } }
  Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
  Timer { interval: 250; running: true; repeat: true; onTriggered: {
    if (test.phase === 0) {
      palette.open(JSON.stringify({mode:"select", prompt:"Pick", options:["x\\tOne\\tid1","Two","Bad"], multiple:true, selected:["Two","unknown"], selectionFile:test.base+"/selection",doneFile:test.base+"/done"}))
      test.check(palette.rows.length === 4 && palette.rows[0].title === "Apply", "multi picker has Apply row")
      test.check(palette.dmenuSelected.length === 1 && palette.dmenuSelected[0] === "Two", "invalid preselection dropped")
      palette.selected=1; palette.activate()
      test.check(palette.opened && palette.dmenuSelected.length === 2, "toggle keeps picker open")
      palette.setQuery("Two"); palette.runQuery()
      test.check(palette.rows.length === 2 && palette.rows[0].id === "apply", "Apply survives filtering")
      palette.selected=0; palette.activate()
      test.check(!palette.opened, "Apply closes picker")
      palette.open(JSON.stringify({mode:"select",options:["One","Two","Bad"],multiple:true,selected:[],onChange:["python3",test.base+"/callback.py",test.base+"/changes"],changeKey:"synthetic"}))
      test.check(palette.rows.length === 3, "live picker has no Apply row")
      palette.selected=0; palette.activate()
      palette.selected=1; palette.activate()
      test.phase=1
    } else if (test.phase === 1) {
      if (palette.dmenuSaved.length !== 2) return
      test.check(palette.opened && palette.dmenuSelected.join(",") === "One,Two", "queued live changes applied in order")
      palette.selected=2; palette.activate()
      test.phase=2
    } else if (test.phase === 2) {
      if (palette.dmenuSelected.indexOf("Bad") >= 0 || palette.dmenuSaved.length !== 2) return
      palette.cancel()
      // Disabled actions must never reach the shell even through keyboard activation.
      var menu=palette.registry.bundled[0]
      menu.items={root:{id:"root",parent:"",label:"Root",kind:"menu",aliases:[]},installed:{id:"installed",parent:"root",label:"Installed",kind:"action",action:"touch " + test.base+"/forbidden",disabled:"true",aliases:[]}}
      menu.itemOrder=["root","installed"];menu.rowsLoaded=true;menu.disabledResults={installed:true};menu.pathCache=({})
      var row=menu.rowFor(menu.items.installed,"",1,true)
      palette.mode="palette";palette.applyRows([palette.normalize(row,{key:"omarchy",provider:menu.provider},"",0)]);palette.selected=0
      test.check(palette.current.disabled, "disabled row reaches host")
      palette.activate()
      console.log("PASS palette Omarchy 4.5 multi picker")
      Qt.quit()
    }
  } }
  Timer { interval: 8000; running: true; onTriggered: { console.log("FAIL timeout",test.phase); Qt.quit() } }
}
''')
    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    assert "PASS palette Omarchy 4.5 multi picker" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    import json
    assert json.loads((work / "selection").read_text()) == ["One\tid1", "Two"]
    changes=[json.loads(line) for line in (work / "changes").read_text().splitlines()]
    assert changes == [["One"], ["One", "Two"], ["One", "Two", "Bad"]], changes
    assert not (work / "forbidden").exists(), "disabled action reached shell"
    print("PASS 4.5 multi-pickers: preselection, filtered Apply, JSON result, serial callbacks, rejected change and blocked disabled action")
