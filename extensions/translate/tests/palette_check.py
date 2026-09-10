#!/usr/bin/env python3
"""The Translate extension inside the real palette, offscreen, with a fake curl.

A copy of the project runs Keystroke.qml under Quickshell's offscreen platform
with a fake HOME whose bin/ shadows curl, wl-paste, wl-copy, wtype and the
notification script: curl answers from a small table in the endpoint's JSON
shape and logs every request, wl-paste returns a Ukrainian selection, wl-copy
and wtype record what they were given. Nothing reaches the network or the
desktop. Checked: the extension is off until keystroke.json says so; `tr hello
world` produces the answer row, the reverse translation and the follow-up
rows with three requests in the right order; the editor view opens with the
typed text; the selection rows appear and "Copy the translated selection"
delivers to wl-copy after the palette closed; an HTTP 429 pauses requests
with a visible row; the target picker adds a language through a setting;
turning the extension off destroys the service.

Run from the repository root: python3 extensions/translate/tests/palette_check.py
"""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

root = Path(__file__).resolve().parents[3]

with tempfile.TemporaryDirectory(prefix="keystroke-translate-") as temp:
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
    def script(name, body):
        p = fake / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    script("curl", f'''#!/usr/bin/env python3
import json, sys, urllib.parse
args = sys.argv[1:]
url = args[-1]
text = None
if "--data-urlencode" in args: text = args[args.index("--data-urlencode") + 1][2:]
qs = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
sl, tl = qs.get("sl", [""])[0], qs.get("tl", [""])[0]
if text is None: text = qs.get("q", [""])[0]
with open({str(work / "requests.log")!r}, "a") as f: f.write(sl + "\\t" + tl + "\\t" + text + "\\n")
if "ratelimit" in text:
    sys.stdout.write("<html>429</html>\\n__STATUS__429"); sys.exit(0)
table = {{("hello world", "fr"): "Bonjour le monde", ("Bonjour le monde", "en"): "Hello World",
         ("Добрий день", "en"): "Good day", ("Добрий день", "fr"): "Bonjour", ("Good day", "uk"): "Гарного дня"}}
detected = "uk" if any("\\u0400" <= ch <= "\\u04ff" for ch in text) else ("fr" if text.startswith("Bonjour") else "en")
out = table.get((text, tl)) or (text if tl == detected else tl + ":" + text)
body = json.dumps([[[out, text, None, None, 10]], None, detected, None, None, None, 1, [], [[detected], None, [1], [detected]]], ensure_ascii=False)
sys.stdout.write(body + "\\n__STATUS__200")
''')
    script("wl-paste", '#!/bin/sh\nprintf "Добрий день"\n')
    script("wl-copy", f'#!/bin/sh\nprintf "%s\\n" "$@" >> {str(work / "copied.txt")!r}\n')
    script("wtype", f'#!/bin/sh\nprintf "%s\\n" "$@" >> {str(work / "typed.txt")!r}\n')
    script("mpv", '#!/bin/sh\nexit 0\n')
    (work / "omarchy" / "bin").mkdir(parents=True)
    notify = work / "omarchy" / "bin" / "omarchy-notification-send"
    notify.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" >> {str(work / "notified.txt")!r}\n')
    notify.chmod(notify.stat().st_mode | stat.S_IEXEC)

    (work / ".config/omarchy").mkdir(parents=True)
    (work / ".config/omarchy/keystroke.json").write_text(json.dumps({"version": 1, "matching": {"mode": "off"}}))

    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
 id: test
 property int stage: 0
 property int failures: 0
 property var svc: null
 function check(ok, msg) { if (!ok) { failures++; console.log("FAIL", msg) } else console.log("ok", msg) }
 function entry(key) { return palette.registry.entries.filter(function(e) { return e.key === key })[0] || null }
 function titles() { return palette.rows.map(function(r) { return r.title }) }
 function row(title) { return palette.rows.filter(function(r) { return r.title === title })[0] || null }
 function indexOf(title) { for (var i = 0; i < palette.rows.length; i++) if (palette.rows[i].title === title) return i; return -1 }
 property string captureDir: "''' + os.environ.get('KEYSTROKE_CAPTURE_DIR', '') + '''"
 property int settled: 0
 property bool capturing: false
 // With KEYSTROKE_CAPTURE_DIR set, the palette window is saved as PNGs for a look at the rows and the view; the stages wait for each grab.
 function capture(name) {
   if (!captureDir) return
   var win = null, list = palette.resources
   for (var i = 0; i < list.length; i++) if (list[i] && list[i].contentItem) win = list[i]
   if (!win) { console.log("capture: no window found"); return }
   test.capturing = true
   win.contentItem.grabToImage(function(r) { r.saveToFile(captureDir + "/" + name + ".png"); test.capturing = false })
 }
 function config(on, extra) { var c = { version: 1, matching: { mode: "off" }, providers: {} }; for (var i = 0; i < on.length; i++) c.providers[on[i]] = { enabled: true }; if (extra) for (var k in extra) c.providers.translate[k] = extra[k]; return JSON.stringify(c) }
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 Timer { interval: 100; repeat: true; running: true; onTriggered: {
   if (test.capturing) return
   switch (test.stage) {
   case 0:   // listed, not loaded
     if (!palette.registry.manifests["translate"]) return
     test.check(palette.registry.manifests["translate"].source === "builtin" && !entry("translate").loaded, "translate is shipped and off")
     test.check(Object.keys(palette.registry.services).length === 0, "no service exists while off")
     palette.applyConfigText(config(["translate"]))
     test.stage = 1; return
   case 1:   // on: the service loads with its provider surface
     var s = palette.registry.services["translate"]
     if (!s || !s.instance || !entry("translate").loaded) return
     test.svc = s.instance
     test.svc.omarchyPath = "''' + str(work / "omarchy") + '''"
     var p = entry("translate").provider
     test.check(p.patterns.length === 1 && p.settings.length === 7 && !!p.view && typeof p.dismiss === "function", "provider declares a pattern, settings, a view and dismiss")
     test.check(entry("translate").commands.length === 1 && entry("translate").commands[0].prefix === "tr" && entry("translate").settingsSchema[0].key === "prefix", "the command from extension.json is compiled with the prefix setting in front")
     test.check(test.svc.iconSource.indexOf("assets/icon.svg") > 0, "icon resolved next to the service: " + test.svc.iconSource)
     test.check(palette.registry.problems.length === 0, "no problems: " + JSON.stringify(palette.registry.problems))
     palette.open(JSON.stringify({ query: "tr hello world" }))
     test.stage = 2; return
   case 2:   // the answer, the reverse translation and the follow-up rows
     if (palette.pending || !row("Bonjour le monde") || !row("Hello World")) return
     var main = palette.rows[0]
     test.check(main.title === "Bonjour le monde" && main.tier === "answer" && main.subtitle === "English → French", "answer row first: " + JSON.stringify([main.title, main.tier, main.subtitle]))
     test.check(main.action.type === "copy" && main.action.text === "Bonjour le monde" && main.altAction.type === "exec", "copy on Enter, paste on Ctrl+Enter")
     test.check(main.iconSource.indexOf("assets/icon.svg") > 0 && main.badge === "extension", "row carries the icon and the extension badge: " + main.iconSource + " " + main.badge)
     test.check(row("Hello World").subtitle.indexOf("Back to English") === 0, "reverse translation row: " + row("Hello World").subtitle)
     test.check(row("Open in the editor") !== null && row("Open in Google Translate") !== null, "follow-up rows: " + titles().join(" | "))
     test.check(row("Speak") === null, "no Speak row while playback is off")
     test.check(!row("hello world"), "no echo row for the language typed")
     if (test.settled++ < 3) return
     capture("rows")
     test.stage = 21; return
   case 21:
     palette.activateAt(indexOf("Open in the editor"))
     test.settled = 0
     test.stage = 3; return
   case 3:   // the editor view opens with the typed text
     if (!palette.providerViewActive) return
     if (test.settled++ < 8) return
     capture("view")
     test.stage = 31; return
   case 31:
     test.check(palette.activeProviderKey === "translate", "view is ours: " + palette.activeProviderKey)
     test.check(test.svc.draft === "hello world", "draft seeded from the query: " + test.svc.draft)
     var v = test.svc.viewState()
     test.check(v && v.main.text === "Bonjour le monde" && v.reverse && v.reverse.text === "Hello World", "view state has the cached translations")
     palette.cancel()
     palette.open(JSON.stringify({ query: "" }))
     test.stage = 4; return
   case 4:   // the root offers the selection wl-paste returned
     if (palette.pending || !row("Translate the selection")) return
     test.check(row("Translate") !== null, "root navigation row")
     test.check(row("Translate the selection").subtitle === "Добрий день", "selection read on open: " + row("Translate the selection").subtitle)
     test.check(row("Copy the translated selection") === null, "copy/paste rows are not at the root")
     palette.cancel()
     palette.open(JSON.stringify({ scope: "translate", title: "Translate" }))
     test.stage = 5; return
   case 5:   // the scoped screen: selection jobs, hint and picker entry
     if (palette.pending || !row("Copy the translated selection")) return
     test.check(row("Paste the translated selection") !== null && row("Target languages") !== null && row("Type text to translate") !== null, "scoped rows: " + titles().join(" | "))
     test.check(row("Target languages").accessory === "en, fr", "targets shown: " + row("Target languages").accessory)
     capture("scope")
     test.stage = 51; return
   case 51:
     palette.activateAt(indexOf("Copy the translated selection"))
     test.stage = 6; return
   case 6:   // the job delivers after the palette closed
     if (palette.opened || test.svc.jobs.length || Object.keys(test.svc.inflight).length) return
     test.check(!palette.opened, "the palette closed at once")
     palette.open(JSON.stringify({ query: "tr ratelimit please" }))
     test.stage = 7; return
   case 7:   // HTTP 429 pauses requests with a visible row
     if (palette.pending || !row("Too many requests")) return
     test.check(test.svc.blockedUntil > Date.now(), "back-off armed")
     test.check(row("Too many requests").disabled && row("Too many requests").subtitle.indexOf("try again in") > 0, "the row says when: " + row("Too many requests").subtitle)
     test.svc.blockedUntil = 0
     palette.cancel()
     palette.open(JSON.stringify({ scope: "translate/targets", title: "Target languages" }))
     test.stage = 8; return
   case 8:   // the picker: chosen first, Enter adds through a setting
     if (palette.pending || palette.rows.length < 50) return
     test.check(palette.rows.length >= 100, "the languages are listed (the host caps the list): " + palette.rows.length)
     test.check(indexOf("German") > 2, "German is listed below the chosen ones: " + indexOf("German"))
     test.check(palette.rows[0].title === "English" && palette.rows[0].accessory === "✓" && palette.rows[1].title === "French" && palette.rows[2].accessory === "", "chosen targets first: " + titles().slice(0, 3).join(" | "))
     capture("picker")
     test.stage = 81; return
   case 81:
     palette.activateAt(indexOf("German"))
     test.stage = 9; return
   case 9:
     if (!palette.config.providers || !palette.config.providers.translate || palette.config.providers.translate.targets !== "en,fr,de") return
     test.check(test.svc.targets.join(",") === "en,fr,de", "service sees the new targets: " + test.svc.targets.join(","))
     if (palette.rows[2].title !== "German") return
     test.check(palette.rows[2].accessory === "✓", "German is now chosen")
     palette.cancel()
     palette.applyConfigText(config([]))
     test.stage = 10; return
   case 10:  // off: the service is destroyed
     if (entry("translate").loaded) return
     test.check(Object.keys(palette.registry.services).length === 0, "service destroyed: " + Object.keys(palette.registry.services).join(","))
     console.log(test.failures ? "FAIL palette translate" : "PASS palette translate")
     Qt.quit(); test.stage = 11; return
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
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr
    assert "PASS palette translate" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    requests = [line.split("\t") for line in (work / "requests.log").read_text().splitlines()]
    first = requests[:3]
    assert first == [["auto", "en", "hello world"], ["auto", "fr", "hello world"], ["fr", "en", "Bonjour le monde"]], requests
    selection = [r for r in requests if r[2] == "Добрий день"]
    assert selection == [["auto", "en", "Добрий день"]], requests   # the job stops at the main translation
    copied = (work / "copied.txt").read_text().splitlines()
    assert copied == ["--", "Good day"], copied
    assert not (work / "typed.txt").exists()
    notified = (work / "notified.txt").read_text()
    assert "Translation copied" in notified and "Good day" in notified, notified
    print("PASS palette translate: off until switched on, answer + reverse + follow-up rows from three requests, editor view seeded, selection copied after close, 429 back-off, picker setting, service destroyed when off")
