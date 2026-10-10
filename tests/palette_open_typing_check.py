#!/usr/bin/env python3
"""Keys typed in the same turn as open() all land in the field, the deferred first query then runs on them, and the loading bar follows setBusy(): the real palette, offscreen."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='keystroke-palette-open-typing-') as temp:
    work = Path(temp)
    project = work/'project'
    shutil.copytree(root, project, ignore=shutil.ignore_patterns('.git','.claude','.agents','.codex','tests','__pycache__'))
    (work/'qs').symlink_to('/usr/share/omarchy/shell')
    source = project/'Keystroke.qml'
    qml = source.read_text()
    qml = qml.replace('  id: root\n', '''  id: root
  property alias testSearch: search
  property alias testPanel: panel
  property var testAppLibrary: null
''', 1)
    qml = qml.replace('readonly property var appLibrary: applicationLibrary.library',
                      'readonly property var appLibrary: root.testAppLibrary || applicationLibrary.library')
    qml = qml.replace('  PanelWindow {','  Window {\n    transientParent: null\n    width: 1000; height: 800')
    qml = qml.replace('    anchors { top: true; bottom: true; left: true; right: true }\n','')
    source.write_text('\n'.join(line for line in qml.splitlines() if 'exclusionMode:' not in line and 'WlrLayershell.' not in line))
    (work/'shell.qml').write_text('''import QtQuick
import QtTest
import Quickshell
import "project"
ShellRoot {
 id: test
 property int round: 0
 property int phase: 0
 property bool busyChecked: false
 function check(ok,msg) { if(!ok) { console.log("FAIL",msg); Qt.quit(); throw Error(msg) } }
 Keystroke { id: palette; omarchyPath:"/usr/share/omarchy" }
 TestCase { id: keys; name:"KeyDriver"; when:false }
 Timer { interval:200; repeat:true; running:true; onTriggered:{
   if (test.round === 0 && test.phase === 0) {
     palette.applyConfigText(JSON.stringify({version:1,matching:{mode:"off"}}))
     palette.testPanel.requestActivate()
   }
   if (test.round < 12) {
     if (test.phase === 0) {
       palette.open('{}')
       // Typed in the same turn as open(): nothing has run yet but the window state.
       "screenshot".split("").forEach(function(c) { keys.keyClick(c) })
       test.check(palette.testSearch.text === "screenshot", "round " + test.round + ": every key reached the field, got '" + palette.testSearch.text + "'")
       test.phase = 1
       return
     }
     // One frame later the deferred work ran on the typed text.
     test.check(palette.testSearch.text === "screenshot", "round " + test.round + ": the field kept its text")
     test.check(palette.rows.length > 0, "round " + test.round + ": the first query ran on the typed text")
     palette.cancel()
     test.phase = 0
     test.round++
     return
   }
   if (!test.busyChecked) {
     palette.open('{}')
     test.check(!palette.showBusy, "no loading bar on a fresh open")
     palette.setBusy("fixture", true)
     test.check(palette.busy && !palette.showBusy, "busy is known at once, the bar waits out the delay")
     test.busyChecked = true
     return
   }
   test.check(palette.showBusy, "the loading bar shows after the delay")
   palette.setBusy("fixture", false)
   test.check(!palette.busy && !palette.showBusy, "the bar goes when the work ends")
   palette.cancel()
   console.log("PASS palette open typing")
   Qt.quit()
 } }
 Timer { interval:12000; running:true; onTriggered:{ console.log("FAIL timeout",palette.errorMessage); Qt.quit() } }
}
''')
    env=dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_BACKEND='software', QML_IMPORT_PATH=str(work))
    env.pop('DISPLAY', None)
    env.pop('WAYLAND_DISPLAY', None)
    result=subprocess.run(['quickshell','-p',str(work/'shell.qml')],env=env,capture_output=True,text=True,timeout=25)
    output=result.stdout+result.stderr
    assert 'PASS palette open typing' in output and 'FAIL' not in output, output
    assert 'TypeError' not in output and 'ReferenceError' not in output, output
    print('PASS palette open typing: keys typed with open() are kept, the first query runs on them, and the loading bar follows setBusy()')
