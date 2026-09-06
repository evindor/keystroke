#!/usr/bin/env python3
"""Real QML process callbacks: quick release, final correction and stale cancellation."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='keystroke-audio-session-') as temp:
    work = Path(temp)
    helper = work/'capture.py'
    helper.write_text('''import json, sys, time
if '--probe' in sys.argv:
    print('{"detected":true}'); sys.exit()
json.loads(sys.stdin.readline())
print('{"event":"listening"}', flush=True)
print('{"event":"preview","text":"Draft"}', flush=True)
for line in sys.stdin:
    action = json.loads(line)['action']
    if action == 'cancel': time.sleep(.1)
    print(json.dumps({'event':'result','final':True,'text':'Final correction' if action=='stop' else 'STALE','index':1,'ms':250}), flush=True)
    break
''')
    config = work/'shell.qml'
    config.write_text('''import QtQuick
import Quickshell
import %s
ShellRoot {
  id: test
  property int stage: 0
  property var texts: []
  property var picks: []
  property double resumeAt: 0
  function check(ok, why) { if (!ok) { console.log("FAIL: " + why); Qt.quit(); throw Error(why) } }
  AudioSession {
    id: voice
    helperPath: %s
    catalog: [{title:"Browser"}]
    onTranscribed: function(text) { test.texts = test.texts.concat([text]) }
    onRecognized: function(index, text, ms) { test.picks = test.picks.concat([index]) }
  }
  Timer { interval: 100; running: true; onTriggered: {
    voice.enabled = true; voice.detected = true; voice.available = true
    test.check(voice.start(), "start")
    voice.stop() // release before Process.onStarted
    test.stage = 1
  } }
  Timer { interval: 20; running: true; repeat: true; onTriggered: {
    if (test.stage === 1 && test.texts.length === 1) {
      test.check(test.texts[0] === "Final correction" && test.picks[0] === 1, "final before recognized")
      test.resumeAt = Date.now()+150; test.stage = 2
    } else if (test.stage === 2 && Date.now() > test.resumeAt) {
      voice.available = true; test.check(voice.start(), "second start"); test.stage = 3
    } else if (test.stage === 3 && voice.liveText === "Draft") {
      voice.cancel()
      test.check(!voice.start(), "overlap rejected")
      test.resumeAt = Date.now()+250; test.stage = 4
    } else if (test.stage === 4 && Date.now() > test.resumeAt) {
      test.check(test.texts.length === 1 && test.picks.length === 1, "cancel ignores stale result")
      voice.available = true; test.check(voice.start(), "third start"); test.stage = 5
    } else if (test.stage === 5 && voice.phase === "listening") {
      voice.stop(); test.stage = 6
    } else if (test.stage === 6 && test.texts.length === 2) {
      test.check(test.texts[1] === "Final correction" && !voice.active, "next session intact")
      console.log("PASS: native audio quick release, final correction, cancellation and stale callback guards")
      Qt.quit()
    }
  } }
  Timer { interval: 4000; running: true; onTriggered: { console.log("FAIL: timeout " + test.stage); Qt.quit() } }
}
''' % (json.dumps((ROOT/'voice').as_uri()), json.dumps(str(helper))))
    env = dict(os.environ, XDG_RUNTIME_DIR=temp, QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_BACKEND='software')
    env.pop('DISPLAY', None); env.pop('WAYLAND_DISPLAY', None)
    run = subprocess.run(['quickshell','-p',str(config)], env=env, capture_output=True, text=True, timeout=8)
    output = run.stdout+run.stderr
    if run.returncode or 'PASS: native audio' not in output or 'FAIL:' in output: raise SystemExit(output)
    print('PASS: native audio quick release, final correction, cancellation and stale callback guards')
