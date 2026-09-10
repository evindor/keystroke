#!/usr/bin/env python3
"""Extensions load through providers/Registry.qml itself, offscreen, only when on.

A copy of the project (with the shipped extensions/timer) and a fake HOME with
a local extensions folder holding three more: a probe that must become a
provider once it is turned on (with `shell`, `extension` and `omarchyPath`
injected and its rows answering a query), one whose Service.qml does not
compile, and one whose folder name is not a valid id. The real Keystroke.qml
scans both folders at creation and on every open. Nothing is loaded until the
switch in keystroke.json says so; turning the switch off destroys the service.

The shipped timer also exercises the bar item API: starting a timer through
its service puts a countdown on the palette's barList at once, the real
BarWidget.qml (against a fake bar) shows it after the menu button and summons
the Timers screen when pressed, and turning the extension off clears it.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]

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

    local = work / ".local/share/keystroke/extensions"
    def extension(folder, name, **fields):
        d = local / folder
        d.mkdir(parents=True)
        m = {"name": name, "version": "1.0.0", "author": "Test", "description": "Probe", "apiVersion": 1, "icon": "P"}
        m.update(fields)
        (d / "extension.json").write_text(json.dumps(m, indent=2))
        return d
    probe = extension("probe", "Probe")
    (probe / "Service.qml").write_text('''import QtQuick
import "core/Model.js" as Model
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: ""
  property bool destroyed: false
  readonly property var provider: ({
    apiVersion: 1, name: "Probe", icon: "P", description: "Probe extension",
    settings: [{ key: "suffix", type: "string", label: "Suffix", "default": "!" }],
    query: function(ctx) {
      if (ctx.scope || ctx.query.indexOf("probe") !== 0) return []
      return [{ id: "probe", title: Model.title(ctx.query, ctx.settings.suffix), subtitle: (root.extension ? root.extension.id + " " + root.extension.source : "no extension") + " " + root.omarchyPath,
                icon: "P", tier: "item", score: 100, action: { type: "noop" } }]
    }
  })
}
''')
    (probe / "core").mkdir()
    (probe / "core/Model.js").write_text('.pragma library\nfunction title(q, suffix) { return "Probe says " + q.slice(5).trim() + suffix }\n')
    broken = extension("broken", "Broken")
    (broken / "Service.qml").write_text("import QtQuick\nQtObject { readonly property var provider: ({ apiVersion: 1, name: \"Broken\" \n")
    extension("Bad_Name", "Bad")
    (work / ".config/omarchy").mkdir(parents=True)
    config = work / ".config/omarchy/keystroke.json"
    config.write_text(json.dumps({"version": 1, "matching": {"mode": "off"}}))

    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
 id: test
 property int stage: 0
 property int failures: 0
 property var probeService: null
 function check(ok, msg) { if (!ok) { failures++; console.log("FAIL", msg) } else console.log("ok", msg) }
 function keys() { return palette.registry.entries.map(function(e) { return e.key }) }
 function entry(key) { return palette.registry.entries.filter(function(e) { return e.key === key })[0] || null }
 function problem(id) { var p = palette.registry.problems.filter(function(x) { return x.id === id }); return p.length ? p[0].message : "" }
 function titles() { return palette.rows.map(function(r) { return r.title }) }
 function row(title) { return palette.rows.filter(function(r) { return r.title === title })[0] || null }
 function config(on) { var c = { version: 1, matching: { mode: "off" }, providers: {} }; for (var i = 0; i < on.length; i++) c.providers[on[i]] = { enabled: true }; return JSON.stringify(c) }
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 // The bar widget finds the palette the way the shell exposes it: a Loader per panel plugin, keyed by plugin id.
 QtObject { id: paletteLoader; property var item: palette }
 QtObject { id: fakeShell; property var panelLoaders: ({ "evindor.keystroke": paletteLoader }) }
 QtObject {
   id: fakeBar
   property var shell: fakeShell
   property string fontFamily: "monospace"
   property color barForeground: "white"
   property color urgent: "red"
   property bool vertical: false
   property int barSize: 30
   property bool foregroundAnimationEnabled: false
   property string last: ""
   function run(cmd) { last = String(cmd) }
   function hideTooltip(item) { }
   function showTooltip(item, text) { }
   function registerClickTarget(item) { }
   function unregisterClickTarget(item) { }
   function moduleWidgets(id) { return [widget] }
 }
 BarWidget { id: widget; bar: fakeBar }
 function widgetTexts() {
   var out = [], layout = widget.children[0]
   for (var i = 0; i < layout.children.length; i++) { var c = layout.children[i]; if (c && c.text !== undefined && c.visible) out.push(String(c.text)) }
   return out
 }
 Timer { interval: 100; repeat: true; running: true; onTriggered: {
   switch (test.stage) {
   case 0:   // the scan at creation found both folders; nothing is loaded
     if (!palette.registry.manifests["probe"] || !palette.registry.manifests["timer"]) return
     test.check(palette.registry.manifests["timer"].source === "builtin" && palette.registry.manifests["probe"].source === "local", "shipped and local folders are both found")
     test.check(keys().indexOf("timer") >= 0 && keys().indexOf("probe") >= 0 && keys().indexOf("broken") >= 0, "every extension is listed: " + keys().join(","))
     test.check(!entry("timer").loaded && !entry("probe").loaded && !entry("broken").loaded, "nothing is loaded while off")
     test.check(Object.keys(palette.registry.services).length === 0, "no service objects exist while off")
     test.check(problem("broken") === "", "an extension that is off is not compiled, so its error is not reported yet")
     test.check(problem("Bad_Name").indexOf("Folder name must be") === 0, "a bad folder name is reported: " + problem("Bad_Name"))
     test.check(!palette.providerEnabled(entry("timer")) && palette.providerEnabled(entry("calculator")), "extensions default to off, bundled providers to on")
     palette.open(JSON.stringify({ query: "timer 10m tea" }))
     test.stage = 1; return
   case 1:   // off: the shipped timer answers nothing
     if (palette.pending) return
     test.check(row("Start a 10 min timer: tea") === null, "timer off: no timer row: " + titles().join(" | "))
     palette.cancel()
     palette.applyConfigText(config(["probe", "broken", "timer"]))
     test.stage = 2; return
   case 2:   // on: services are created, the broken one is reported
     var svc = palette.registry.services["probe"]
     if (!svc || !svc.instance || !entry("probe") || !entry("probe").loaded) return
     test.probeService = svc.instance
     test.check(svc.instance.extension && svc.instance.extension.id === "probe" && svc.instance.extension.dir.indexOf("/probe") > 0 && svc.instance.extension.source === "local", "extension injected with id, dir and source")
     test.check(svc.instance.omarchyPath === "/usr/share/omarchy", "omarchyPath injected: " + svc.instance.omarchyPath)
     test.check(entry("timer").loaded && entry("timer").provider.settings.length === 5, "the shipped timer loaded with its settings schema")
     test.check(!entry("broken").loaded && problem("broken").indexOf("Service.qml") >= 0, "broken extension is reported with the QML error: " + problem("broken"))
     palette.open(JSON.stringify({ query: "probe tea" }))
     test.stage = 3; return
   case 3:   // its rows answer a query with its settings applied
     if (palette.pending || !palette.rows.length) return
     var r = row("Probe says tea!")
     test.check(r !== null, "probe row listed: " + titles().join(" | "))
     test.check(r && r.subtitle === "probe local /usr/share/omarchy", "provider reads its injected extension record: " + (r && r.subtitle))
     test.check(r && r.badge === "extension", "extension rows carry the badge: " + (r && r.badge))
     palette.cancel()
     palette.open(JSON.stringify({ query: "timer 10m tea" }))
     test.stage = 4; return
   case 4:
     if (palette.pending || !palette.rows.length) return
     test.check(row("Start a 10 min timer: tea") !== null, "timer on: the shipped extension answers: " + titles().join(" | "))
     // Start it through the service's own activate (the palette's would also send a desktop notification).
     test.check(palette.barList.length === 0 && widgetTexts().length === 1, "nothing in the bar before a timer starts: " + JSON.stringify(widgetTexts()))
     var timerService = palette.registry.services["timer"].instance
     var effect = timerService.activate(row("Start a 10 min timer: tea"), { host: palette, settings: palette.providerSettings("timer"), alternate: false })
     test.check(effect && effect.type === "compound", "starting a timer returns the notify and close effect")
     test.check(palette.barList.length === 1 && /^󰔛 (9:59|10:00)$/.test(palette.barList[0].text), "the countdown is on the bar list right after the start: " + JSON.stringify(palette.barList))
     test.check(palette.barItems.timer && palette.barItems.timer.payload.scope === "timer" && palette.barItems.timer.tooltip.indexOf("tea · 10 min · ends at ") === 0, "the bar item carries the Timers payload and a tooltip: " + JSON.stringify(palette.barItems.timer))
     test.check(widgetTexts().length === 2 && widgetTexts()[1] === palette.barList[0].text, "BarWidget shows the countdown after the menu button: " + JSON.stringify(widgetTexts()))
     widget.openItem(widget.items[0])
     test.check(fakeBar.last === "omarchy-shell shell summon omarchy.menu '{\\"scope\\":\\"timer\\",\\"title\\":\\"Timers\\"}'", "pressing the countdown summons the Timers screen: " + fakeBar.last)
     palette.setBarItem("calculator", { text: "x" })
     palette.setBarItem("probe", { text: "" })
     test.check(palette.barList.length === 2 && palette.barList[0].id === "calculator" && palette.barList[1].id === "timer", "any enabled provider may add an item; an empty text is dropped: " + JSON.stringify(palette.barList.map(function(i) { return i.id })))
     palette.setBarItem("calculator", null)
     palette.setBarItem("nonsense", { text: "y" })
     test.check(palette.barList.length === 1, "null clears an item and an unknown provider adds none")
     palette.cancel()
     palette.open(JSON.stringify({ scope: "extensions", title: "Extensions" }))
     test.stage = 5; return
   case 5:   // the Extensions screen lists all of them with their state
     if (palette.pending || !palette.rows.length) return
     test.check(row("Timer") && row("Timer").accessory === "On", "Timer listed as on: " + JSON.stringify(row("Timer") && row("Timer").accessory))
     test.check(row("Broken") && row("Broken").accessory === "Needs attention", "Broken listed as needing attention")
     test.check(row("Probe") && row("Probe").badge === "local", "Probe carries the local badge")
     test.check(row("Write your own") !== null, "the guide row is there")
     palette.cancel()
     palette.open(JSON.stringify({ scope: "extensions/probe", title: "Probe" }))
     test.stage = 6; return
   case 6:   // one extension's screen: switch, settings, folder
     if (palette.pending || !palette.rows.length) return
     test.check(row("Enabled") && row("Enabled").accessory === "On" && !row("Enabled").confirm, "Enabled row shows on, no confirmation to turn off")
     test.check(row("Open folder") && row("Open folder").action.argv[1].indexOf("/probe") > 0, "local extension offers its folder")
     palette.cancel()
     palette.applyConfigText(config(["timer"]))
     test.stage = 7; return
   case 7:   // off again: the service is destroyed, the listing stays
     if (entry("probe").loaded) return
     test.check(Object.keys(palette.registry.services).sort().join(",") === "timer", "only the timer service remains: " + Object.keys(palette.registry.services).join(","))
     test.check(keys().indexOf("probe") >= 0, "turned off, the extension stays listed")
     test.check(palette.barList.length === 1 && palette.barList[0].id === "timer", "the timer's bar item survives another extension turning off")
     palette.open(JSON.stringify({ scope: "extensions/probe", title: "Probe" }))
     test.stage = 8; return
   case 8:
     if (palette.pending || !palette.rows.length) return
     test.check(row("Enabled") && row("Enabled").accessory === "Off" && row("Enabled").confirm === "Turn on Probe?", "turning on asks first: " + (row("Enabled") && row("Enabled").confirm))
     test.check(row("Enabled") && row("Enabled").confirmDetail.indexOf("local folder in ") > 0 && row("Enabled").confirmDetail.indexOf("/probe") > 0, "the confirmation names the folder: " + (row("Enabled") && row("Enabled").confirmDetail))
     palette.cancel()
     palette.applyConfigText(config([]))
     test.stage = 9; return
   case 9:   // the timer off: its service is destroyed and its bar item goes with it
     if (entry("timer").loaded) return
     test.check(palette.barList.length === 0 && widgetTexts().length === 1, "turning the timer off clears its countdown from the bar: " + JSON.stringify(palette.barList))
     console.log(test.failures ? "FAIL palette extensions" : "PASS palette extensions")
     Qt.quit(); test.stage = 10; return
   }
 } }
 Timer { interval: 15000; running: true; onTriggered: { console.log("FAIL timeout at stage", test.stage, JSON.stringify(palette.registry.problems), palette.errorMessage, keys().join(",")); Qt.quit() } }
}
''')

    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert "PASS palette extensions" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    print("PASS palette extensions: shipped and local extensions are listed unloaded, load with shell/extension/omarchyPath injected when turned on, publish bar items the BarWidget shows, and are destroyed (bar item included) when turned off")
