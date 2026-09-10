#!/usr/bin/env python3
"""Declared commands inside the real palette, offscreen.

A copy of the project runs Keystroke.qml under Quickshell's offscreen platform
with a fake HOME (a fake curl on PATH keeps the Translate extension off the
network). Checked, through the palette's own state and inspect(): the empty
root offers "What can I type?"; typing a prefix produces the hint line and
the ghost placeholders that follow the caret; a typed command routes the text
to its owner ("timer 10m tea" starts a timer, "tm 10m tea" after the prefix
is renamed in keystroke.json); a typed command is exclusive (":smi" lists only emoji);
"/" lists every command and "/tr" filters it; a name ("trans") suggests the
command and Tab types its prefix; Tab after a bare prefix adds the space; an
extension's screen starts with Usage rows and a runnable example; turning an
extension on says what to type; the Prefix setting shows the renamed trigger.
"""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix="keystroke-palette-commands-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__", "experiments"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text()
    qml = qml.replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))

    fake = work / "bin"
    fake.mkdir()
    curl = fake / "curl"
    curl.write_text('#!/bin/sh\nprintf \'%s\' \'[[["x","x",null,null,10]],null,"en",null,null,null,1,[],[["en"],null,[1],["en"]]]\'; printf \'\\n__STATUS__200\'\n')
    curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
    (fake / "wl-paste").write_text('#!/bin/sh\nexit 1\n')
    (fake / "wl-paste").chmod(0o755)

    (work / ".config/omarchy").mkdir(parents=True)
    config = work / ".config/omarchy/keystroke.json"
    config.write_text(json.dumps({"version": 1, "matching": {"mode": "off"}, "providers": {"translate": {"enabled": True}}}))

    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
 id: test
 property int stage: 0
 property int failures: 0
 function check(ok, msg) { if (!ok) { failures++; console.log("FAIL", msg) } else console.log("ok", msg) }
 function state() { return JSON.parse(palette.inspect()) }
 function titles() { return palette.rows.map(function(r) { return r.title }) }
 function row(title) { return palette.rows.filter(function(r) { return r.title === title })[0] || null }
 function indexOf(title) { for (var i = 0; i < palette.rows.length; i++) if (palette.rows[i].title === title) return i; return -1 }
 function config(providers) { return JSON.stringify({ version: 1, matching: { mode: "off" }, providers: providers }) }
 property string captureDir: "''' + os.environ.get('KEYSTROKE_CAPTURE_DIR', '') + '''"
 property bool capturing: false
 // With KEYSTROKE_CAPTURE_DIR set, the palette window is saved as PNGs; the stages wait for each grab.
 function capture(name) {
   if (!captureDir) return
   var win = null, list = palette.resources
   for (var i = 0; i < list.length; i++) if (list[i] && list[i].contentItem) win = list[i]
   if (!win) { console.log("capture: no window found"); return }
   test.capturing = true
   win.contentItem.grabToImage(function(r) { r.saveToFile(captureDir + "/" + name + ".png"); test.capturing = false })
 }
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 Timer { interval: 100; repeat: true; running: true; onTriggered: {
   if (test.capturing) return
   switch (test.stage) {
   case 0:
     if (!palette.registry.manifests["translate"] || !palette.registry.services["translate"] || !palette.registry.services["translate"].instance) return
     palette.open(JSON.stringify({ query: "" }))
     test.stage = 1; return
   case 1:   // the empty root
     if (palette.pending || !palette.rows.length) return
     test.check(row("What can I type?") !== null, "the root offers the commands screen: " + titles().slice(-3).join(" | "))
     test.check(state().hint === "" && state().command === null, "no command yet")
     var items = palette.commandItems().map(function(i) { return i.command.prefix })
     test.check(items.indexOf("/") >= 0 && items.indexOf(":") >= 0 && items.indexOf("~") >= 0 && items.indexOf("tr") >= 0 && items.indexOf("timer") < 0, "index holds the enabled providers' prefixes: " + items.join(" "))
     palette.setQuery("tr")
     test.stage = 2; return
   case 2:   // a bare prefix: hint and ghost at once, before the query runs
     var s = state()
     test.check(s.command && s.command.key === "translate" && s.command.rest === "", "tr is recognised live: " + JSON.stringify(s.command))
     test.check(s.hint === "Translate · to: a language code or name; leave it out to use your targets (optional)", "hint names the action and the first argument: " + s.hint)
     test.check(s.ghost === " [to] <text>", "ghost after a bare prefix: " + JSON.stringify(s.ghost))
     palette.completeCommand()
     test.check(state().query === "tr " && state().ghost === "[to] <text>", "Tab after a bare prefix adds the space: " + JSON.stringify(state().query) + " " + JSON.stringify(state().ghost))
     palette.setQuery("tr fr ")
     test.check(state().ghost === "<text>" && state().hint === "Translate · text: what to translate", "the ghost and the hint follow the caret: " + state().ghost + " / " + state().hint)
     capture("ghost")
     test.stage = 21; return
   case 21:
     palette.setQuery("tr fr hello")
     test.check(state().ghost === "", "no ghost once every argument has a word")
     palette.cancel()
     palette.applyConfigText(config({ translate: { enabled: true }, timer: { enabled: true } }))
     test.stage = 3; return
   case 3:   // a word command routes to its owner
     if (!palette.registry.services["timer"] || !palette.registry.services["timer"].instance) return
     palette.open(JSON.stringify({ query: "timer 10m tea" }))
     test.stage = 4; return
   case 4:
     if (palette.pending || !palette.rows.length) return
     test.check(row("Start a 10 min timer: tea") !== null && palette.rows[0].title === "Start a 10 min timer: tea", "timer answers through ctx.command: " + titles().slice(0, 2).join(" | "))
     test.check(state().hint === "Set a timer · name: a label for the notification (optional)", "hint on the last argument: " + state().hint)
     palette.cancel()
     palette.applyConfigText(config({ translate: { enabled: true }, timer: { enabled: true, prefix: "tm" } }))
     palette.open(JSON.stringify({ query: "tm 10m tea" }))
     test.stage = 5; return
   case 5:   // the user renamed the prefix
     if (palette.pending || !palette.rows.length) return
     test.check(palette.rows[0].title === "Start a 10 min timer: tea", "tm routes to the timer after the rename: " + titles().slice(0, 2).join(" | "))
     test.check(state().command && state().command.prefix === "tm", "the live match carries the renamed prefix")
     palette.cancel()
     palette.open(JSON.stringify({ query: ":smi" }))
     test.stage = 6; return
   case 6:   // a sigil is exclusive
     if (palette.pending || !palette.rows.length) return
     var owners = palette.rows.map(function(r) { return r.providerKey }).filter(function(k, i, a) { return a.indexOf(k) === i })
     test.check(owners.length === 1 && owners[0] === "emoji", "only the emoji provider answers a sigil: " + owners.join(","))
     test.check(state().hint === "Emoji · feeling: a name or a feeling: smile, cat, party", "sigil hint: " + state().hint)
     palette.cancel()
     palette.open(JSON.stringify({ query: "/" }))
     test.stage = 7; return
   case 7:   // the "/" screen
     if (palette.pending || !palette.rows.length) return
     test.check(row("Translate") !== null && row("Set a timer") !== null && row("Emoji") !== null && row("Find files") !== null && row("What can I type?") === null, "/ lists every command: " + titles().join(" | "))
     test.check(row("Set a timer").subtitle.indexOf("tm <duration> [name]") === 0 && row("Set a timer").accessory === "tm", "usage uses the renamed prefix: " + row("Set a timer").subtitle)
     capture("help")
     test.stage = 71; return
   case 71:
     palette.setQuery("/tr")
     test.stage = 8; return
   case 8:
     if (palette.pending || !palette.rows.length) return
     test.check(row("Translate") !== null && row("Emoji") === null, "/tr filters the list: " + titles().join(" | "))
     palette.cancel()
     palette.open(JSON.stringify({ query: "trans" }))
     test.stage = 9; return
   case 9:   // a name suggests the command; Tab types its prefix
     if (palette.pending || !palette.rows.length) return
     var i = indexOf("Translate")
     var suggestion = palette.rows.filter(function(r) { return r.title === "Translate" && r.providerKey === "commands" })[0]
     test.check(suggestion !== null && suggestion !== undefined && suggestion.hint === "tab types tr", "a command row is suggested for its name: " + (suggestion ? suggestion.hint : titles().join(" | ")))
     palette.selected = palette.rows.indexOf(suggestion)
     palette.completeCommand()
     test.check(state().query === "tr " && state().scope === "" && state().command && state().command.key === "translate", "Tab typed the prefix: " + JSON.stringify(state().query))
     palette.cancel()
     palette.open(JSON.stringify({ scope: "extensions/translate", title: "Translate" }))
     test.stage = 10; return
   case 10:  // Usage on the extension's screen
     if (palette.pending || !palette.rows.length) return
     test.check(palette.rows[0].title === "tr [to] <text>" && palette.rows[0].section === "Usage", "usage line first: " + titles().slice(0, 3).join(" | "))
     test.check(row("tr bonjour") !== null && row("tr bonjour").verb === "Try", "examples are runnable")
     test.check(row("Prefix") !== null && row("Prefix").accessory === "tr" && row("Prefix").action.scope === "settings/translate/prefix", "the prefix row leads to the setting")
     test.check(row("Enabled") !== null, "the switch is still there")
     capture("usage")
     test.stage = 101; return
   case 101:
     palette.activateAt(indexOf("tr bonjour"))
     test.stage = 11; return
   case 11:
     if (state().scope !== "" || state().query !== "tr bonjour") return
     test.check(true, "an example types itself at the root")
     test.check(state().command && state().command.rest === "bonjour", "and is recognised as the command")
     palette.cancel()
     palette.applyConfigText(config({ translate: { enabled: true }, timer: { enabled: false, prefix: "tm" } }))
     palette.open(JSON.stringify({ scope: "extensions/timer", title: "Timer" }))
     test.stage = 12; return
   case 12:  // turning an extension on says what to type
     if (palette.pending || !row("Enabled")) return
     test.check(palette.rows[0].title === "tm <duration> [name]", "usage known while the extension is off, with the renamed prefix: " + palette.rows[0].title)
     palette.perform({ type: "setting", path: ["providers", "timer"], key: "enabled", value: true, schema: { key: "enabled", type: "boolean" } }, row("Enabled"))
     test.check(palette.statusMessage === "Timer is on · type tm <duration> [name], or find it by name", "the notice says what to type: " + palette.statusMessage)
     palette.cancel()
     palette.open(JSON.stringify({ scope: "settings/timer", title: "Timer" }))
     test.stage = 13; return
   case 13:  // the reserved prefix setting
     if (palette.pending || !palette.rows.length) return
     test.check(row("Prefix") !== null && row("Prefix").accessory === "tm", "Prefix is a setting: " + (row("Prefix") ? row("Prefix").accessory : titles().join(" | ")))
     palette.cancel()
     console.log(test.failures ? "FAIL palette commands" : "PASS palette commands")
     Qt.quit(); test.stage = 14; return
   }
 } }
 Timer { interval: test.captureDir ? 40000 : 20000; running: true; onTriggered: { console.log("FAIL timeout at stage", test.stage, JSON.stringify(palette.registry.problems), palette.errorMessage, titles().join(" | ")); Qt.quit() } }
}
''')

    if os.environ.get("KEYSTROKE_CAPTURE_DIR"):
        Path(os.environ["KEYSTROKE_CAPTURE_DIR"]).mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), PATH=f"{fake}:{os.environ.get('PATH', '')}",
               QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=40)
    output = result.stdout + result.stderr
    assert "PASS palette commands" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    print("PASS palette commands: hint line and ghost placeholders, routing through ctx.command, renamed prefixes, exclusive commands, the / screen, Tab completion, Usage rows, the enable notice and the Prefix setting")
