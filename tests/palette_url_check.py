#!/usr/bin/env python3
"""Open URL in the real offscreen palette; capture launches without a browser."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix="keystroke-palette-url-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(
        ".git", ".claude", ".agents", ".codex", "tests", "__pycache__", "experiments"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text().replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))

    fake = work / "bin"
    fake.mkdir()
    # Util.execArgv uses bash -lc with positional arguments. Capture that
    # boundary so we also verify URL punctuation never becomes shell code.
    (fake / "bash").write_text('''#!/usr/bin/python3
import json, os, sys
if len(sys.argv) > 4 and sys.argv[4] == "xdg-open":
    with open(os.environ["URL_LAUNCH_LOG"], "a") as out:
        out.write(json.dumps(sys.argv[1:]) + "\\n")
else:
    os.execv("/bin/bash", ["bash"] + sys.argv[1:])
''')
    (fake / "bash").chmod(0o755)
    (fake / "wl-paste").write_text("#!/bin/sh\nexit 1\n")
    (fake / "wl-paste").chmod(0o755)
    config = work / ".config/omarchy/keystroke.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"version": 1, "matching": {"mode": "off"}}))

    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
 id: test
 property int stage: 0
 property int failures: 0
 property string url: "https://example.com/a%2Fb?q=$(id)&x='a';echo#part"
 function check(ok, msg) { if (!ok) { failures++; console.log("FAIL", msg) } else console.log("ok", msg) }
 function row(title) { return palette.rows.filter(function(r) { return r.title === title })[0] }
 function configure(enabled, prefix) {
   palette.cancel()
   palette.applyConfigText(JSON.stringify({version: 1, matching: {mode: "off"}, providers: {"open-url": {enabled: enabled, prefix: prefix}}}))
 }
 function query(text) { palette.setQuery(text); palette.runQuery() }
 function top(url) {
   var r = palette.rows[0]
   check(r && r.providerKey === "open-url" && r.tier === "answer" && r.action.url === url, "URL ranks first: " + url)
 }
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 Timer { interval: 100; repeat: true; running: true; onTriggered: {
   switch (test.stage) {
   case 0:
     if (!palette.registryEntry("open-url")) return
     palette.open(JSON.stringify({query: test.url}))
     test.stage++; return
   case 1:
     if (palette.pending || !palette.rows.length) return
     top(test.url)
     check(palette.registryEntry("open-url").source === "bundled", "native provider")
     query("example.com/path?q=a+b&x=%26#part")
     top("https://example.com/path?q=a+b&x=%26#part")
     query("//example.com/path")
     top("https://example.com/path")
     query("$example.com/path?q=1")
     top("https://example.com/path?q=1")
     check(palette.rows.every(function(r) { return r.providerKey === "open-url" }), "prefix routes exclusively")
     query("$")
     check(palette.rows[0].disabled && JSON.parse(palette.inspect()).ghost === "<url>", "bare prefix hints without an action")
     palette.activate()
     check(palette.opened, "Enter on empty prefix stays open")
     query("$javascript:alert(1)")
     check(palette.rows[0].disabled, "unsupported scheme cannot launch")
     query("user@example.com")
     check(!palette.rows.some(function(r) { return r.providerKey === "open-url" }), "email is not a URL offer")
     // A file name must not take the answer slot away from the file itself.
     var files = ["readme.md", "notes.txt", "package.json", "photo.jpg", "archive.zip"]
     check(files.every(function(name) {
       palette.setQuery(name); palette.runQuery()
       return !palette.rows.some(function(r) { return r.providerKey === "open-url" })
     }), "bare file names make no URL offer")
     query("readme.md/raw")
     top("https://readme.md/raw")
     query("$readme.md")
     top("https://readme.md")
     query("docs.rs")
     top("https://docs.rs")
     query("/")
     check(row("Open URL") && row("Open URL").accessory === "$", "command appears in help")
     palette.cancel()
     palette.open(JSON.stringify({scope: "settings/open-url", title: "Open URL"}))
     test.stage++; return
   case 2:
     if (palette.pending || !row("Prefix")) return
     check(row("Enabled") && row("Enabled").accessory === "On" && row("Prefix").accessory === "$", "enabled and prefix settings default correctly")
     check(palette.rows.length === 2, "only the two requested settings")
     configure(true, "go")
     palette.open(JSON.stringify({query: "go intranet/docs"}))
     test.stage++; return
   case 3:
     if (palette.pending || !palette.rows.length) return
     top("https://intranet/docs")
     check(palette.rows.every(function(r) { return r.providerKey === "open-url" }), "renamed prefix routes exclusively")
     query("$example.com")
     check(!palette.rows.some(function(r) { return r.providerKey === "open-url" }), "old prefix stops matching")
     configure(false, "go")
     palette.open(JSON.stringify({query: "example.com"}))
     test.stage++; return
   case 4:
     if (palette.pending) return
     check(!palette.rows.some(function(r) { return r.providerKey === "open-url" }), "disabled provider makes no URL offer")
     check(!palette.commandItems().some(function(i) { return i.key === "open-url" }), "disabled provider has no prefix")
     configure(true, "$")
     palette.open(JSON.stringify({query: test.url}))
     test.stage++; return
   case 5:
     if (palette.pending || !palette.rows.length) return
     top(test.url)
     palette.selected = 0
     palette.activate() // The same path as the Enter key handler.
     check(!palette.opened, "Enter closes the palette before launching")
     test.stage++; return
   case 6:
     console.log(test.failures ? "FAIL palette URL" : "PASS palette URL")
     Qt.quit(); test.stage++; return
   }
 } }
 Timer { interval: 20000; running: true; onTriggered: { console.log("FAIL timeout", test.stage, palette.errorMessage); Qt.quit() } }
}
''')
    log = work / "launches.jsonl"
    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work),
               PATH=f"{fake}:{os.environ.get('PATH', '')}", URL_LAUNCH_LOG=str(log),
               QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic",
               QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env,
                            capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert "PASS palette URL" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    launches = [json.loads(line) for line in log.read_text().splitlines()]
    assert launches == [["-lc", 'exec "$@"', "bash", "xdg-open",
                         "https://example.com/a%2Fb?q=$(id)&x='a';echo#part"]], launches
    print("PASS palette URL: native registration, first result, routing, help, settings, disable, rename and literal default-browser launch")
