#!/usr/bin/env python3
"""Community extensions load through providers/Registry.qml itself, offscreen.

A fake HOME holds four plugin folders: a marked extension that must become a
provider (with `shell`, `manifest` and `omarchyPath` injected and its rows
answering a query), a marked one whose Service.qml does not compile, a folder
whose name differs from its id, and an ordinary bar widget that must be left
alone. The real Keystroke.qml scans the folder at creation and on every open.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
PROBE = "test.keystroke-probe"
BROKEN = "test.keystroke-broken"

with tempfile.TemporaryDirectory(prefix="keystroke-palette-extensions-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__", "experiments"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text()
    qml = qml.replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))

    plugins = work / ".config/omarchy/plugins"
    def manifest(folder, id, kinds=("service",), marked=True, entry="Service.qml"):
        d = plugins / folder
        d.mkdir(parents=True)
        m = {"schemaVersion": 1, "id": id, "name": id.split(".")[-1].title(), "version": "1.0.0", "author": "Test", "license": "MIT",
             "description": "Probe", "kinds": list(kinds), "keepLoaded": True, "entryPoints": {"service": entry} if "service" in kinds else {"barWidget": entry}}
        if marked: m["x-keystroke"] = {"apiVersion": 1}
        (d / "manifest.json").write_text(json.dumps(m, indent=2))
        return d
    probe = manifest(PROBE, PROBE)
    (probe / "Service.qml").write_text('''import QtQuick
import "core/Model.js" as Model
QtObject {
  id: root
  property var shell: null
  property var manifest: null
  property string omarchyPath: ""
  readonly property var provider: ({
    apiVersion: 1, name: "Probe", icon: "P", description: "Probe extension",
    settings: [{ key: "suffix", type: "string", label: "Suffix", "default": "!" }],
    query: function(ctx) {
      if (ctx.scope || ctx.query.indexOf("probe") !== 0) return []
      return [{ id: "probe", title: Model.title(ctx.query, ctx.settings.suffix), subtitle: (root.manifest ? root.manifest.id : "no manifest") + " " + root.omarchyPath,
                icon: "P", tier: "item", score: 100, action: { type: "noop" } }]
    }
  })
}
''')
    (probe / "core").mkdir()
    (probe / "core/Model.js").write_text('.pragma library\nfunction title(q, suffix) { return "Probe says " + q.slice(5).trim() + suffix }\n')
    broken = manifest(BROKEN, BROKEN)
    (broken / "Service.qml").write_text("import QtQuick\nQtObject { readonly property var provider: ({ apiVersion: 1, name: \"Broken\" \n")
    manifest("wrong-folder", "test.keystroke-misnamed")
    manifest("someone.bar-thing", "someone.bar-thing", kinds=("bar-widget",), marked=False, entry="Widget.qml")
    (home_json := work / ".config/omarchy/keystroke.json").write_text(json.dumps({"version": 1, "matching": {"mode": "off"}}))

    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
 id: test
 property int stage: 0
 property int failures: 0
 function check(ok, msg) { if (!ok) { failures++; console.log("FAIL", msg) } else console.log("ok", msg) }
 function keys() { return palette.registry.entries.map(function(e) { return e.key }) }
 function problem(id) { var p = palette.registry.problems.filter(function(x) { return x.pluginId === id }); return p.length ? p[0].message : "" }
 function titles() { return palette.rows.map(function(r) { return r.title }) }
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 Timer { interval: 100; repeat: true; running: true; onTriggered: {
   switch (test.stage) {
   case 0:   // the scan at creation found the folder
     if (!palette.registry.manifests[%(probe)s]) return
     test.check(keys().indexOf(%(probe)s) >= 0, "probe extension is a provider: " + keys().join(","))
     test.check(keys().indexOf(%(broken)s) < 0, "broken extension is not a provider")
     test.check(keys().indexOf("extensions") >= 0 && keys().indexOf("settings") >= 0, "bundled providers still registered: " + keys().join(","))
     test.check(problem(%(broken)s).indexOf("Service.qml") >= 0, "broken extension is reported with the QML error: " + problem(%(broken)s))
     test.check(problem("wrong-folder").indexOf("Folder name must equal") === 0, "misnamed folder is reported: " + problem("wrong-folder"))
     test.check(!palette.registry.manifests["someone.bar-thing"], "an unmarked bar widget is ignored")
     var svc = palette.registry.services[%(probe)s].instance
     test.check(svc.manifest && svc.manifest.id === %(probe)s && svc.manifest.__sourceDir === undefined, "manifest injected without host stamps")
     test.check(svc.omarchyPath === "/usr/share/omarchy", "omarchyPath injected: " + svc.omarchyPath)
     palette.open(JSON.stringify({ query: "probe tea" }))
     test.stage = 1; return
   case 1:   // its rows answer a query with its settings applied
     if (palette.pending || !palette.rows.length) return
     test.check(titles().indexOf("Probe says tea!") >= 0, "probe row listed: " + titles().join(" | "))
     var r = palette.rows.filter(function(x) { return x.title === "Probe says tea!" })[0]
     test.check(r && r.subtitle === %(probe)s + " /usr/share/omarchy", "provider reads its injected manifest: " + (r && r.subtitle))
     var off = { version: 1, matching: { mode: "off" }, providers: {} }; off.providers[%(probe)s] = { enabled: false }
     palette.applyConfigText(JSON.stringify(off))
     palette.runQuery()
     test.stage = 2; return
   case 2:   // off: still hosted, asked nothing
     if (palette.pending) return
     test.check(titles().indexOf("Probe says tea!") < 0, "turned off, the row is gone: " + titles().join(" | "))
     test.check(keys().indexOf(%(probe)s) >= 0, "turned off, the service stays hosted")
     palette.cancel()
     console.log(test.failures ? "FAIL palette extensions" : "PASS palette extensions")
     Qt.quit(); test.stage = 3; return
   }
 } }
 Timer { interval: 10000; running: true; onTriggered: { console.log("FAIL timeout at stage", test.stage, JSON.stringify(palette.registry.problems), palette.errorMessage); Qt.quit() } }
}
''' % dict(probe=json.dumps(PROBE), broken=json.dumps(BROKEN)))

    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    assert "PASS palette extensions" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    print("PASS palette extensions: a marked plugin folder becomes a provider with shell/manifest/omarchyPath injected; broken and misnamed ones are reported")
