#!/usr/bin/env python3
"""Real palette + reader, isolated HOME and synthetic Chromium data."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile

root = Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix="keystroke-browser-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__", "experiments"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text().replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))
    config = work / ".config"
    (config / "omarchy").mkdir(parents=True)
    (config / "omarchy/keystroke.json").write_text(json.dumps({"version": 1, "matching": {"mode": "off"}}))
    profile = config / "chromium/Default"
    profile.mkdir(parents=True)
    with sqlite3.connect(profile / "History") as db:
        db.execute("CREATE TABLE urls (title TEXT, url TEXT, last_visit_time INTEGER, hidden INTEGER)")
        db.execute("INSERT INTO urls VALUES ('Fixture history', 'https://example.org/history', 100, 0)")
    (profile / "Bookmarks").write_text(json.dumps({"roots": {"bookmark_bar": {"type": "folder", "children": [
        {"type": "url", "name": "Fixture bookmark", "url": "https://example.org/bookmark"}]}}}))
    fake = work / "bin"
    fake.mkdir()
    (fake / "xdg-settings").write_text('#!/bin/sh\nprintf "chromium.desktop\\n"\n')
    (fake / "xdg-settings").chmod(0o755)
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
  id: test
  property int stage: 0
  property int failures: 0
  Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
  function service() { var s = palette.registry.services["browser-search"]; return s ? s.instance : null }
  function check(ok, msg) { if (!ok) { failures++; console.log("FAIL", msg) } }
  function items() { return palette.rows.filter(function(r) { return r.providerKey === "browser-search" && !r.disabled }) }
  function configure(on, history, bookmarks, prefix) {
    palette.applyConfigText(JSON.stringify({ version: 1, matching: { mode: "off" }, providers: {
      "browser-search": { enabled: on, history: history, bookmarks: bookmarks, prefix: prefix || "browser" }
    } }))
  }
  Timer { interval: 120; running: true; repeat: true; onTriggered: {
    if (palette.pending || (service() && service().inflight)) return
    switch (test.stage) {
    case 0:
      if (!palette.registry.manifests["browser-search"]) return
      check(!service(), "disabled extension is not loaded")
      configure(true, true, true)
      test.stage++; return
    case 1:
      if (!service()) return
      check(service().provider.settings.length === 2, "two source settings")
      palette.open(JSON.stringify({ query: "browser fixture" }))
      test.stage++; return
    case 2:
      check(items().length === 2, "command returns both sources")
      check(items()[0] && items()[0].action.type === "url", "activation opens URL")
      check(items()[0] && items()[0].altAction.type === "copy", "alternate copies URL")
      configure(true, false, true)
      palette.setQuery("browser fixture")
      test.stage++; return
    case 3:
      check(items().length === 1 && items()[0].title === "Fixture bookmark", "history disabled")
      configure(true, true, false, "web")
      palette.setQuery("web fixture")
      test.stage++; return
    case 4:
      check(items().length === 1 && items()[0].title === "Fixture history", "bookmarks disabled and renamed prefix")
      configure(true, false, false, "web")
      palette.setQuery("web fixture")
      test.stage++; return
    case 5:
      check(items().length === 0 && !service().inflight, "both disabled stops search")
      configure(true, true, true)
      palette.setQuery("fixture")
      test.stage++; return
    case 6:
      check(items().length === 2, "main palette searches browser")
      service().provider.opened()
      check(Object.keys(service().cache).length === 0, "open clears cache")
      // Start obsolete work before the latest query reaches the helper.
      service().query({ query: "obsolete", scope: "", settings: {}, pending: function() {} })
      palette.setQuery("browser bookmark")
      test.stage++; return
    case 7:
      check(items().length === 1 && items()[0].title === "Fixture bookmark", "obsolete process cannot replace latest results")
      test.stage++; return
    case 8:
      // The helper's exit code can reach the service before its output does.
      var probe = service()
      probe.inflight = "probe"; probe.superseded = false
      probe.output = ""; probe.outputDone = false; probe.exitCode = -1; probe.failure = ""
      probe.exitCode = 0; probe.settle()
      check(probe.cache["probe"] === undefined, "exit before output does not judge the run")
      probe.output = '{"browser":"Chromium","results":[]}'; probe.outputDone = true; probe.settle()
      check(probe.cache["probe"] && !probe.cache["probe"].error, "run judged once the output follows")
      configure(false, true, true)
      test.stage++; return
    case 9:
      check(!service(), "disabling destroys service")
      console.log(test.failures ? "FAIL browser palette" : "PASS browser palette")
      Qt.quit(); stop(); return
    }
  } }
  Timer { interval: 15000; running: true; onTriggered: {
    console.log("FAIL timeout", test.stage, JSON.stringify(palette.registry.problems)); Qt.quit()
  } }
}
''')
    env = dict(os.environ, HOME=str(work), XDG_CONFIG_HOME=str(config), XDG_RUNTIME_DIR=str(work),
               PATH=f"{fake}:{os.environ['PATH']}", QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic",
               QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    for key in ("DISPLAY", "WAYLAND_DISPLAY", "CHROME_CONFIG_HOME", "CHROME_USER_DATA_DIR", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        env.pop(key, None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=25)
    output = result.stdout + result.stderr
    assert "PASS browser palette" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    print("PASS browser palette: load/unload, root search, commands, settings, URL effects, refresh and obsolete queries")
