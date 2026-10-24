#!/usr/bin/env python3
"""Real palette: closing, actions and navigation cancel a running file walk."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="keystroke-files-lifecycle-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text().replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))
    # Only replace the executable in the isolated copy. Keep the real provider's
    # process, watchdog, cache and host signal handling intact.
    files = project / "providers/Files.qml"
    files.write_text(files.read_text().replace("fd.command = Files.argv(query, root.home, settings)",
        'fd.command = ["' + str(work / "slow-fd") + '"]'))
    log = work / "walks.log"
    slow = work / "slow-fd"
    slow.write_text("#!/usr/bin/python\n" + """import os, signal, time
from pathlib import Path
log = Path(os.environ["WALK_LOG"])
def record(event):
    with log.open("a") as f:
        f.write(f"{os.getpid()} {event}\\n")
def stop(*args):
    record("cancelled")
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
record("started")
print(os.environ["HOME"] + "/stale-report.pdf\\0", end="", flush=True)
time.sleep(30)
""")
    slow.chmod(0o755)
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
  id: test
  property int stage: 0
  property var files: null
  Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
  function check(ok, msg) { if (!ok) { console.log("FAIL", msg); Qt.quit(); throw Error(msg) } }
  Timer { id: steps; interval: 250; running: true; repeat: true; onTriggered: {
    if (!test.files) {
      test.files = palette.registry.bundled.filter(function(p) { return p.provider.id === "files" })[0]
      if (!test.files.available) return
      palette.applyConfigText(JSON.stringify({version: 1, matching: {mode: "off"}}))
    }
    if (test.stage % 3 === 0) {
      palette.open(JSON.stringify({query: "~report"}))
      palette.runQuery()
      test.check(!!test.files.inflight, "walk starts")
    } else if (test.stage % 3 === 1) {
      switch (Math.floor(test.stage / 3)) {
        case 0: palette.cancel(); break
        case 1: palette.perform({type: "exec", argv: ["/usr/bin/true"]}, {}); break
        case 2: palette.setQuery(""); palette.runQuery(); break
        case 3: palette.navigate("calculator", "Calculator"); break
        case 4: palette.openDmenu({mode: "select", options: []}); break
      }
    } else {
      test.check(!test.files.inflight, "walk exits promptly, before the 3-second watchdog: " + test.stage)
      test.check(Object.keys(test.files.cache).length === 0, "cancelled output is not cached")
      palette.cancel()
    }
    if (++test.stage === 15) { console.log("PASS files lifecycle"); Qt.quit(); steps.stop() }
  } }
  Timer { interval: 8000; running: true; onTriggered: { console.log("FAIL lifecycle timeout"); Qt.quit() } }
}
''')
    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work), WALK_LOG=str(log))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    assert "PASS files lifecycle" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    events = log.read_text().splitlines()
    assert sum(line.endswith("started") for line in events) == 5, events
    assert sum(line.endswith("cancelled") for line in events) == 5, events
    print("PASS files lifecycle: close, action, empty query, navigation and dmenu stop walks without caching stale output")
