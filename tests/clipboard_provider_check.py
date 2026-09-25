#!/usr/bin/env python3
"""Verify Clipboard provider defaults and both copy/paste actions."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="keystroke-clipboard-provider-") as temp:
    work = Path(temp)
    (work / "providers").symlink_to(root / "providers")
    (work / "core").symlink_to(root / "core")
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "providers"
import "core/Settings.js" as Settings
ShellRoot {
  Clipboard { id: clipboard }
  function check(ok, message) { if (!ok) throw Error(message) }
  Timer { interval: 100; running: true; onTriggered: {
    var settings = Settings.values(Settings.empty(), ["providers", "clipboard"], clipboard.provider.settings)
    check(settings.pasteOnSelect === false, "paste must default off")
    clipboard.entries = [
      { type: "text", text: "hello", search: "hello" },
      { type: "image", path: "/tmp/example.png", mime: "image/png", capturedAt: "today" }
    ]
    var ctx = { scope: "clipboard", query: "", settings: settings }
    var rows = clipboard.query(ctx)
    check(rows.length === 2, "expected both clipboard entries")
    check(rows[0].action.type === "copy" && rows[1].action.argv[1] === "--copy-only", "default actions must copy")
    settings.pasteOnSelect = true
    rows = clipboard.query(ctx)
    check(rows[0].verb === "Paste" && rows[0].action.type === "dictation-copy" && rows[0].action.paste === true, "text must paste")
    check(rows[1].verb === "Paste" && rows[1].action.argv.length === 3, "image must paste")
    console.log("PASS clipboard provider copy and paste actions"); Qt.quit()
  } }
}
''')
    env = os.environ.copy()
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    env.update(QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(work), OMARCHY_PATH="/usr/share/omarchy")
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    assert "PASS clipboard provider copy and paste actions" in output and "Error:" not in output, output
    print("PASS: Clipboard provider defaults and copy/paste actions")
