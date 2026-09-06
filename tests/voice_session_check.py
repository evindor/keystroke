#!/usr/bin/env python3
"""Exercise real Quickshell Process callbacks against a fake dictation CLI."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="keystroke-session-") as work:
    directory = Path(work)
    runtime = directory / "runtime"
    runtime.mkdir(mode=0o700)
    mock = directory / "voxtype"
    mock.write_text('''#!/usr/bin/python3
import json, pathlib, sys, time
counter = pathlib.Path(__file__).with_name("takes")
action = sys.argv[2]
if action == "start":
    counter.write_text(str(int(counter.read_text()) + 1 if counter.exists() else 1))
elif action == "stop":
    take = counter.read_text()
    time.sleep(.25)
    print(json.dumps({"status": "ok", "text": "take-" + take}))
elif action == "cancel":
    time.sleep(.05)
''')
    mock.chmod(0o700)
    bridge = directory / "voxtype-audio-bridge"
    bridge.write_text("#!/bin/sh\nexit 0\n")
    bridge.chmod(0o700)
    config = directory / "shell.qml"
    config.write_text('''import QtQuick
import Quickshell
import %s
ShellRoot {
    id: test
    property int stage: 0
    property double resumeAt: 0
    property bool rejectedOverlap: false
    property var results: []
    VoiceSession {
        id: voice
        command: %s
        detectedAt: Date.now()
        onTranscribed: function(text) { test.results = test.results.concat([text]) }
    }
    Timer {
        interval: 100; running: true
        onTriggered: { voice.start(); test.stage = 1 }
    }
    Timer {
        interval: 20; running: true; repeat: true
        onTriggered: {
            if (test.stage === 1 && voice.phase === "listening") {
                voice.stop(); test.stage = 2
            } else if (test.stage === 2 && voice.phase === "transcribing") {
                voice.cancel()
                test.rejectedOverlap = !voice.start()
                test.resumeAt = Date.now() + 150
                test.stage = 3
            } else if (test.stage === 3 && Date.now() >= test.resumeAt) {
                if (!voice.start()) { console.log("FAIL: second start"); Qt.quit(); return }
                test.stage = 4
            } else if (test.stage === 4 && voice.phase === "listening") {
                voice.stop(); test.stage = 5
            } else if (test.stage === 5 && voice.phase === "idle" && test.results.length) {
                if (!test.rejectedOverlap || JSON.stringify(test.results) !== '["take-2"]') {
                    console.log("FAIL: " + JSON.stringify(test.results)); Qt.quit(); return
                }
                test.resumeAt = Date.now() + 100
                test.stage = 6
            } else if (test.stage === 6 && Date.now() >= test.resumeAt) {
                voice.start(); test.stage = 7
            } else if (test.stage === 7 && voice.phase === "listening") {
                voice.daemonState = "streaming"
                voice.daemonState = "idle"
                test.stage = 8
            } else if (test.stage === 8 && test.results.length === 2) {
                console.log(JSON.stringify(test.results) === '["take-2","take-3"]'
                    ? "PASS: cancelled recording cannot leak; auto-stop collected" : "FAIL: auto-stop")
                Qt.quit()
            }
        }
    }
    Timer { interval: 4000; running: true; onTriggered: { console.log("FAIL: timeout at stage " + test.stage); Qt.quit() } }
}
''' % (json.dumps((root / "voice").as_uri()), json.dumps(str(mock))))
    env = os.environ.copy()
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    env.update(XDG_RUNTIME_DIR=str(runtime), QT_QPA_PLATFORM="offscreen",
               QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software")
    run = subprocess.run(["quickshell", "-p", str(config)], env=env,
                         capture_output=True, text=True, timeout=8)
    output = run.stdout + run.stderr
    if run.returncode or "PASS: cancelled recording" not in output:
        raise SystemExit(output)
    print("PASS cancelled recording: overlap rejected, old reader retired, next transcript intact; auto-stop collected")
