#!/usr/bin/env python3
"""Ctrl+1…Ctrl+8 run the nth result: activateAt() on the real palette, offscreen."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='keystroke-palette-shortcut-') as temp:
    work = Path(temp)
    project = work/'project'
    shutil.copytree(root, project, ignore=shutil.ignore_patterns('.git','.claude','.agents','.codex','tests','__pycache__'))
    (work/'qs').symlink_to('/usr/share/omarchy/shell')
    source = project/'Keystroke.qml'
    qml = source.read_text()
    qml = qml.replace('  PanelWindow {','  Window {\n    transientParent: null\n    width: 1000; height: 800')
    qml = qml.replace('    anchors { top: true; bottom: true; left: true; right: true }\n','')
    source.write_text('\n'.join(line for line in qml.splitlines() if 'exclusionMode:' not in line and 'WlrLayershell.' not in line))
    (work/'shell.qml').write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
 id: test
 property var activated: []
 function check(ok,msg) { if(!ok) { console.log("FAIL",msg); Qt.quit(); throw Error(msg) } }
 Keystroke { id: palette; omarchyPath:"/usr/share/omarchy" }
 Timer { interval:250; running:true; onTriggered:{
   palette.applyConfigText(JSON.stringify({version:1,matching:{mode:"off"}}))
   palette.open('{}')
   palette.registry.entries = [{key:"fixture",source:"bundled",patterns:[],provider:{name:"Fixture",settings:[],
     query:function(ctx) { return ["a","b","c"].map(function(id, i) { return {id:id,title:"Row "+id,score:100-i,disabled:id==="b",action:{type:"noop"}} }) },
     activate:function(row) { test.activated.push(row.id); return {type:"noop"} }
   }}]
   palette.runQuery()
   test.check(palette.rows.length===3,"fixture rows are listed")
   palette.activateAt(2)
   test.check(test.activated.join()==="c","Ctrl+3 runs the third row")
   test.check(palette.selected===2 && palette.selectionTouched,"the shortcut also moves the selection there")
   palette.activateAt(0)
   test.check(test.activated.join()==="c,a","Ctrl+1 runs the first row")
   palette.activateAt(1)
   test.check(test.activated.join()==="c,a","a disabled row is selected but not run")
   palette.activateAt(7)
   test.check(test.activated.join()==="c,a" && palette.selected===1,"a number past the list does nothing")
   palette.cancel()
   console.log("PASS palette shortcut")
   Qt.quit()
 } }
 Timer { interval:8000; running:true; onTriggered:{ console.log("FAIL timeout",palette.errorMessage); Qt.quit() } }
}
''')
    env=dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_BACKEND='software', QML_IMPORT_PATH=str(work))
    env.pop('DISPLAY', None)
    env.pop('WAYLAND_DISPLAY', None)
    result=subprocess.run(['quickshell','-p',str(work/'shell.qml')],env=env,capture_output=True,text=True,timeout=15)
    output=result.stdout+result.stderr
    assert 'PASS palette shortcut' in output and 'FAIL' not in output, output
    assert 'TypeError' not in output and 'ReferenceError' not in output, output
    print('PASS palette shortcut: Ctrl+number runs the nth row, skips disabled rows and numbers past the list')
