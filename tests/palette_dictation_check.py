#!/usr/bin/env python3
"""Exercise the palette's actual dictation routing with fake audio and clipboard."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='keystroke-palette-') as temp:
    work = Path(temp)
    project = work/'project'
    shutil.copytree(root, project, ignore=shutil.ignore_patterns('.git', '.claude', '.agents', '.codex', 'tests', '__pycache__'))
    for name, target in [('qs', '/usr/share/omarchy/shell'), ('Commons', '/usr/share/omarchy/shell/Commons'), ('Ui', '/usr/share/omarchy/shell/Ui')]:
        (work/name).symlink_to(target)
    p=project/'Keystroke.qml'
    s=p.read_text().replace('  id: root\n', '''  id: root
  property alias testVoice: voice
  property alias testSearch: search
  property alias testTransfer: clipboardTransfer
  property alias testSpoken: spoken
  property alias testAssist: assist
  property alias testCard: card
  property alias testPanel: panel
''',1).replace('  PanelWindow {','  Window {\n    transientParent: null\n    width: 1000; height: 800')
    s=s.replace('    anchors { top: true; bottom: true; left: true; right: true }\n','')
    s='\n'.join(line for line in s.splitlines() if 'exclusionMode:' not in line and 'WlrLayershell.' not in line)
    s=s.replace('    id: assist','''    id: assist
    createRequest: function() { return { open: function(){}, send: function(){}, abort: function(){}, setRequestHeader: function(){} } }''')
    p.write_text(s)
    (project/'voice/VoiceSession.qml').write_text('''import QtQuick
Item {
  property var host: null
  property bool detected: true
  property string version: "test"
  property string command: "fake"
  property string daemonState: "idle"
  property string phase: "idle"
  readonly property bool active: phase !== "idle"
  property string liveText: ""
  property var history: []
  property real level: 0
  signal partial(string text)
  signal transcribed(string text)
  signal nothingHeard()
  signal failed(string message)
  function refresh() {}
  function start() { phase = "listening"; return true }
  function stop() { phase = "transcribing" }
  function cancel() { phase = "idle" }
}
''')
    helper=work/'copy.py'
    helper.write_text('import pathlib,sys\np=pathlib.Path(__file__).parent\n(p/sys.argv[1]).write_text(sys.stdin.read() if sys.argv[1]=="clipboard" else "pasted")\n')
    cfg=work/'shell.qml'
    cfg.write_text('''import QtQuick
import QtTest
import Quickshell
import "project"
ShellRoot {
  id: test
  property int stage: 0
  property string text: "Open the document, please.\\nKeep  two spaces! 🐈"
  function check(ok, message) { if (!ok) { console.log("FAIL", message); Qt.quit(); throw Error(message) } }
  Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
  TestCase { id: keys; name: "KeyDriver"; when: false }
  Timer { interval: 250; running: true; onTriggered: {
    palette.testTransfer.copyCommand = ["python3", %s, "clipboard"]
    palette.testTransfer.pasteCommand = ["python3", %s, "paste"]
    palette.open('{}')
    palette.perform({type:"dictate"}, {title:"Dictate to Clipboard"})
    test.check(palette.dictationMode && palette.testVoice.phase === "listening", "extension starts recording")
    test.check(!palette.testSpoken.active && !palette.testAssist.enabled, "dictation bypasses intent model")
    palette.testVoice.partial(test.text)
    test.check(palette.testSearch.text === test.text, "live prose preserved")
    palette.testPanel.requestActivate()
    palette.testSearch.forceActiveFocus()
    test.stage = 10
  } }
  Timer { interval: 80; running: true; repeat: true; onTriggered: {
    if (test.stage !== 10) return
    keys.keyClick(Qt.Key_Return, Qt.ControlModifier)
    test.check(palette.dictationPending === "paste" && palette.opened, "Ctrl+Enter waits for final")
    palette.testVoice.phase = "idle"
    palette.testVoice.transcribed(test.text + " Final correction.")
    test.stage = 1
  } }
  Timer { interval: 25; running: true; repeat: true; onTriggered: {
    if (test.stage === 1 && !palette.testTransfer.busy) {
      test.check(!palette.opened, "copy closes palette")
      // Enter followed by Escape must discard the pending copy.
      palette.open('{}'); palette.perform({type:"dictate"}, {title:"Dictate"})
      palette.testVoice.partial("discard me")
      keys.keyClick(Qt.Key_Return)
      test.check(palette.dictationPending === "copy", "Enter queues copy")
      keys.keyClick(Qt.Key_Escape)
      palette.testVoice.transcribed("must never overwrite clipboard")
      test.check(!palette.testTransfer.busy && !palette.dictationPending, "Escape cancels pending copy")
      // A final transcript on hotkey release stays open for review.
      palette.open('{}'); palette.perform({type:"dictate"}, {title:"Dictate"})
      palette.testVoice.phase = "idle"
      palette.testVoice.transcribed(test.text)
      test.check(palette.opened && !palette.testTransfer.busy && palette.testSearch.text === test.text, "stop alone preserves review")
      palette.requery()
      test.check(palette.current.preview === test.text, "dictation preview contains prose")
      // Normal voice search exposes the same raw prose as a fallback.
      palette.open('{}'); palette.voiceBegin("tap")
      palette.testVoice.partial(test.text)
      palette.testVoice.phase = "idle"
      palette.testVoice.transcribed(test.text)
      palette.requery()
      var found = -1
      for (var i = 0; i < palette.rows.length; i++) if (palette.rows[i].id === "copy-query") found = i
      test.check(found >= 0, "copy fallback exists after normal dictation")
      test.check(palette.rows[found].action.text === test.text, "fallback keeps original unnormalized speech")
      palette.selected = found; palette.selectionTouched = true
      palette.activate(true)
      test.stage = 2
    } else if (test.stage === 2 && !palette.testTransfer.busy) {
      test.check(!palette.opened, "fallback copies and closes normal palette")
      palette.open('{"query":"typed replacement"}')
      palette.requery()
      var copies = palette.rows.filter(function(row) { return row.id === "copy-query" })
      test.check(copies.length === 1 && copies[0].action.text === "typed replacement", "new query forgets prior speech")
      console.log("PASS: dictation keys, final correction, cancellation, raw prose, model bypass")
      Qt.quit(); test.stage = 3
    }
  } }
  Timer { interval: 6000; running: true; onTriggered: { console.log("FAIL timeout", test.stage); Qt.quit() } }
}
''' % (json.dumps(str(helper)),json.dumps(str(helper))))
    env=os.environ.copy(); env.pop('DISPLAY',None)
    env.update(HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_BACKEND='software', QML_IMPORT_PATH=str(work))
    result=subprocess.run(['quickshell','-p',str(cfg)],env=env,capture_output=True,text=True,timeout=12)
    output=result.stdout+result.stderr
    assert 'PASS: dictation keys' in output and 'FAIL' not in output, output
    assert (work/'clipboard').read_text() == 'Open the document, please.\nKeep  two spaces! 🐈'
    assert (work/'paste').read_text() == 'pasted'
    print('PASS: palette dictation keys, final correction, cancellation, raw prose, model bypass')
