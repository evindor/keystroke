#!/usr/bin/env python3
"""Web search in the real offscreen palette: engine setting, search command, launch."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix="keystroke-palette-websearch-") as temp:
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
    # Capture the xdg-open boundary so no browser starts and the launched URL
    # is checked exactly as the shell would receive it.
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
 function check(ok, msg) { if (!ok) { failures++; console.log("FAIL", msg) } else console.log("ok", msg) }
 function row(title) { return palette.rows.filter(function(r) { return r.title === title })[0] }
 function search() { return palette.rows.filter(function(r) { return r.providerKey === "ai" && r.id === "search" })[0] }
 function configure(ai, mode) {
   palette.cancel()
   palette.applyConfigText(JSON.stringify({version: 1, matching: {mode: mode || "off"}, providers: {ai: ai}}))
 }
 function query(text) { palette.setQuery(text); palette.runQuery() }
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 Timer { interval: 100; repeat: true; running: true; onTriggered: {
   switch (test.stage) {
   case 0:
     if (!palette.registryEntry("ai")) return
     palette.open(JSON.stringify({query: "g rust lifetimes"}))
     test.stage++; return
   case 1:
     if (palette.pending || !palette.rows.length) return
     var r = palette.rows[0]
     check(palette.rows.length === 1 && r.providerKey === "ai" && r.title === "Search Google" && r.tier === "answer"
           && r.action.url === "https://www.google.com/search?q=rust+lifetimes", "g routes to one Google answer")
     check(r.altAction && r.altAction.type === "copy" && r.altAction.text === r.action.url, "Ctrl+Enter copies the URL")
     query("rust lifetimes")
     r = search()
     check(r && r.title === "Search Google" && r.tier === "fallback" && r.section === "Continue with", "ordinary query keeps the fallback")
     query("g")
     check(!search() && JSON.parse(palette.inspect()).ghost === " <query>", "bare prefix hints without a search")
     query("/")
     check(row("Search the web") && row("Search the web").accessory === "g", "command appears in help")
     configure({searchEngine: "duckduckgo", prefix: "s"})
     palette.open(JSON.stringify({query: "s how to center a div"}))
     test.stage++; return
   case 2:
     if (palette.pending || !palette.rows.length) return
     var d = palette.rows[0]
     check(palette.rows.length === 1 && d.title === "Search DuckDuckGo" && d.tier === "answer"
           && d.action.url === "https://duckduckgo.com/?q=how+to+center+a+div", "renamed prefix searches the chosen engine")
     query("g rust")
     check(!palette.rows.some(function(x) { return x.tier === "answer" && x.providerKey === "ai" }), "old prefix stops matching")
     check(search() && search().title === "Search DuckDuckGo" && search().tier === "fallback", "fallback follows the engine")
     // Smart Match on: a blocked request and whole arithmetic keep the command's text.
     configure({searchEngine: "duckduckgo", prefix: "s"}, "all")
     palette.open(JSON.stringify({query: "s install rust"}))
     test.stage++; return
   case 3:
     if (palette.pending || !palette.rows.length) return
     check(palette.rows.length === 1 && palette.rows[0].action.url === "https://duckduckgo.com/?q=install+rust", "Smart Match keeps a blocked request")
     query("s 27 plus 90")
     check(palette.rows.length === 1 && palette.rows[0].action.url === "https://duckduckgo.com/?q=27+plus+90", "Smart Match keeps arithmetic text")
     configure({searchEngine: "duckduckgo", prefix: "s"})
     palette.open(JSON.stringify({scope: "settings/ai", title: "AI & Web Search"}))
     test.stage++; return
   case 4:
     if (palette.pending || !row("Search engine")) return
     check(row("Search engine").accessory === "DuckDuckGo", "engine setting shows its label")
     check(row("Prefix") && row("Prefix").accessory === "s", "prefix setting shows the user's prefix")
     palette.cancel()
     palette.open(JSON.stringify({query: "s a & b"}))
     test.stage++; return
   case 5:
     if (palette.pending || !palette.rows.length) return
     palette.selected = 0
     palette.activate() // The same path as the Enter key handler.
     check(!palette.opened, "Enter closes the palette before launching")
     test.stage++; return
   case 6:
     console.log(test.failures ? "FAIL palette web search" : "PASS palette web search")
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
    assert "PASS palette web search" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    launches = [json.loads(line) for line in log.read_text().splitlines()]
    assert launches == [["-lc", 'exec "$@"', "bash", "xdg-open", "https://duckduckgo.com/?q=a+%26+b"]], launches
    print("PASS palette web search: command, fallback, engine setting, renamed prefix, Smart Match, settings and literal launch")
