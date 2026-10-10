#!/usr/bin/env python3
"""A compositor close or a lost graphics resource must not leave the palette
logically open, an animation running, or a picker caller waiting. The
offscreen Window declares the PanelWindow's close signals; the check emits
them by hand and the palette's handlers run unchanged."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="keystroke-palette-graphics-loss-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text().replace("  id: root\n", "  id: root\n  property alias testPanel: panel\n", 1)
    assert qml.count("  PanelWindow {") == 1, "Keystroke.qml no longer has exactly one PanelWindow"
    qml = qml.replace("  PanelWindow {", "  Window {\n    transientParent: null\n    signal resourcesLost()\n    signal closed()\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))
    # A failure should produce one notification, never a real desktop toast.
    (work / "bin").mkdir()
    notify = work / "bin/omarchy-notification-send"
    notify.write_text('#!/bin/sh\nprintf "notification\\n" >> "$HOME/notifications"\n')
    notify.chmod(0o755)
    # Ctrl+Enter's copy-close-paste, with stand-ins for wl-copy and the paste key.
    for name, body in [("wl-copy", 'cat > "$HOME/clip"'), ("paste", 'printf "pasted\\n" >> "$HOME/pasted"')]:
        (work / "bin" / name).write_text("#!/bin/sh\n" + body + "\n")
        (work / "bin" / name).chmod(0o755)
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
  id: test
  function check(ok, message) { if (!ok) { console.log("FAIL", message); Qt.quit(); throw Error(message) } }
  function configure(transition) {
    palette.applyConfigText(JSON.stringify({version:1, voice:{enabled:false}, matching:{mode:"off"},
      palette:{animations:"fluid", windowTransition:transition}}))
  }
  Keystroke { id: palette; omarchyPath: Quickshell.env("HOME") }
  // Closes the window once a paste has closed the palette and its fade runs.
  property bool closeWhileLeaving: false
  Connections { target: palette; function onOpenedChanged() {
    if (palette.opened || !test.closeWhileLeaving) return
    test.closeWhileLeaving = false
    Qt.callLater(function() { test.check(palette.closing, "the paste leaves with a fade"); palette.testPanel.closed() })
  } }
  Timer { interval:300; running:true; onTriggered: {
    test.configure("slide")
    palette.open('{}')
    test.check(palette.opened && palette.testPanel.visible, "the window is mapped")
    palette.testPanel.resourcesLost()
    palette.testPanel.closed()
    test.check(!palette.opened && !palette.closing && palette.reveal === 0 && !palette.testPanel.visible, "failure immediately unmaps despite animations")
    test.check(palette.errorMessage.indexOf("graphics resources") >= 0, "failure stays inspectable")
    palette.open('{}')
    test.check(palette.opened && palette.errorMessage === "", "the next open retries and clears the error")
    palette.cancel()
    test.check(palette.closing, "normal cancellation still animates")
    palette.testPanel.closed()
    test.check(!palette.closing && palette.reveal === 0, "compositor close terminates a fade")
    palette.testPanel.closed()
    test.check(!palette.opened && !palette.closing, "a close with nothing open is ignored")

    // The signals may arrive in either order; the failure is reported once.
    palette.open('{}')
    palette.testPanel.closed()
    palette.testPanel.resourcesLost()
    test.check(!palette.opened && !palette.closing && palette.reveal === 0, "close then loss unmaps")
    test.check(palette.errorMessage.indexOf("graphics resources") >= 0, "a loss after the close is still reported")
    palette.testPanel.resourcesLost()
    palette.open('{}')
    test.check(palette.opened && palette.errorMessage === "", "the next open clears it")
    palette.testPanel.resourcesLost()
    palette.cancel()
    palette.testPanel.closed()

    // A picker must finish its IPC request even if the window cannot render.
    palette.open(JSON.stringify({mode:"select",width:800,options:["One"],
      doneFile:Quickshell.env("HOME")+"/picker-done",selectionFile:Quickshell.env("HOME")+"/picker-selection"}))
    test.check(palette.requestActive, "picker is waiting")
    palette.testPanel.resourcesLost()
    palette.testPanel.closed()
    test.check(!palette.requestActive && !palette.opened, "failed picker is canceled")
    palette.open(JSON.stringify({mode:"input",prompt:"Retry"}))
    test.check(palette.opened && palette.errorMessage === "", "input picker retries cleanly")
    palette.cancel()

    // A close while leaving must not cancel the paste that close left running.
    palette.pasteHelper = Quickshell.env("HOME") + "/bin/paste"
    palette.open('{}')
    test.closeWhileLeaving = true
    palette.perform({type:"paste", text:"hello"}, {})
    finish.start()
  } }
  Timer { id: finish; interval:1000; onTriggered: {
    test.check(!test.closeWhileLeaving && !palette.closing && !palette.testPanel.visible, "the paste closed and the close snapped the fade")
    console.log("PASS palette graphics loss"); Qt.quit()
  } }
  Timer { interval:10000; running:true; onTriggered: { console.log("FAIL timeout"); Qt.quit() } }
}
''')
    env = dict(os.environ, PATH=str(work / "bin") + os.pathsep + os.environ["PATH"], HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work), OMARCHY_PATH="/usr/share/omarchy")
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    assert "PASS palette graphics loss" in output and "FAIL" not in output, output
    assert not any(error in output for error in ["TypeError", "ReferenceError", "Binding loop"]), output
    assert (work / "picker-done").exists(), "failed picker did not signal completion"
    assert not (work / "picker-selection").exists(), "failed picker must not return a selection"
    assert (work / "pasted").exists(), "a close while leaving dropped the paste"
    assert (work / "notifications").read_text().splitlines() == ["notification", "notification", "notification", "notification"], "one notification per graphics failure"
    print("PASS palette graphics loss: close and resource-loss signals, immediate unmap, retry, picker completion, one notification per failure, a paste survives a close while leaving")
