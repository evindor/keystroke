#!/usr/bin/env python3
"""Direct routes never strand the palette inside a disabled provider."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="keystroke-palette-route-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text()
    qml = qml.replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
  id: test
  function check(ok, msg) { if (!ok) { console.log("FAIL", msg); Qt.quit(); throw Error(msg) } }
  function appsRoute() {
    var menu = palette.registry.bundled[0]
    menu.items = {
      root: { id: "root", parent: "", kind: "menu", label: "Root", aliases: [] },
      apps: { id: "apps", parent: "root", kind: "provider", provider: "apps", label: "Apps", aliases: [] }
    }
    menu.itemOrder = ["root", "apps"]
    menu.rowsLoaded = true
  }
  Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
  Timer { interval: 250; running: true; onTriggered: {
    palette.applyConfigText(JSON.stringify({ version: 1, matching: { mode: "off" }, providers: { applications: { enabled: false } } }))
    test.appsRoute()
    palette.open('{"menu":"apps"}')
    test.check(palette.scope === "", "a disabled apps route falls back to root")
    test.check(palette.scopeTitle === "", "the disabled breadcrumb is cleared")
    test.check(palette.statusMessage === "Applications is disabled in Keystroke Settings", "the fallback explains why")

    palette.applyConfigText(JSON.stringify({ version: 1, matching: { mode: "off" }, providers: { applications: { enabled: true } } }))
    test.appsRoute()
    palette.open('{"menu":"apps"}')
    test.check(palette.scope === "applications", "an enabled apps route still opens Applications")
    test.check(palette.scopeTitle === "Applications", "the enabled breadcrumb is preserved")
    test.check(palette.statusMessage === "", "an enabled route has no warning")
    palette.cancel()
    console.log("PASS palette routes")
    Qt.quit()
  } }
  Timer { interval: 8000; running: true; onTriggered: { console.log("FAIL timeout", palette.errorMessage); Qt.quit() } }
}
''')
    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    assert "PASS palette routes" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    print("PASS palette routes: disabled providers fall back to root; enabled routes remain scoped")
