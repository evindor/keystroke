#!/usr/bin/env python3
"""Exercise the Files provider against fd and an isolated home directory."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="keystroke-files-") as temp:
    work = Path(temp)
    for folder in ["providers", "core"]:
        shutil.copytree(root / folder, work / folder)
    home = work / "home"
    for folder in ["Downloads", "Documents", ".config", ".git"]:
        (home / folder).mkdir(parents=True)
    (home / "Downloads" / "unrelated.pdf").touch()
    (home / "Documents" / "report.pdf").touch()
    (home / "line\nreport.pdf").touch()
    (home / ".config" / "secret-note.txt").touch()
    (home / ".git" / "secret-note.txt").touch()
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "providers"
ShellRoot {
  id: test
  property int stage: 0
  property var cases: [
    {query:"dwnlds",mode:"fuzzy",expected:["Downloads"]},
    {query:"dwnlds",mode:"literal",expected:[]},
    {query:"~dwnlds",mode:"literal",expected:["Downloads"]},
    {query:"dwnlds",mode:"prefix",expected:[],noWalk:true},
    {query:"~dwnlds",mode:"prefix",expected:["Downloads"]},
    {query:"dwnlds",mode:"prefix",scope:"files",expected:["Downloads"]},
    {query:"~/dcmnts rpt",mode:"fuzzy",expected:["Documents/report.pdf"]},
    {query:"~/dcmnts/rpt",mode:"fuzzy",expected:["Documents/report.pdf"]},
    {query:"~",mode:"fuzzy",expected:["hint"],noWalk:true},
    {query:"~secret",mode:"fuzzy",expected:[]},
    {query:"~secret",mode:"fuzzy",hidden:true,expected:[".config/secret-note.txt"]},
    {query:"~line",mode:"fuzzy",expected:["line\\nreport.pdf"]}
  ]
  Files { id: files }
  function check(ok,msg) { if(!ok) { console.log("FAIL",msg); Qt.quit(); throw Error(msg) } }
  Timer { interval:40; running:true; repeat:true; onTriggered: {
    if(!files.available) return
    var c=test.cases[test.stage], pending=false
    var rows=files.query({query:c.query,scope:c.scope||"",settings:{files:true,folders:true,hidden:!!c.hidden,limit:10,searchMode:c.mode},pending:function(){pending=true}})
    if(c.noWalk) test.check(!files.inflight,"prefix-only avoids disk work")
    if(pending) return
    test.check(JSON.stringify(rows.map(r=>r.id).sort())===JSON.stringify(c.expected.slice().sort()),"case "+test.stage+": "+JSON.stringify(rows.map(r=>r.id)))
    files.cache={}
    if(++test.stage===test.cases.length) { console.log("PASS files actual fd modes, prefix, folders, paths, hidden and newline names"); Qt.quit(); stop() }
  } }
  Timer { interval:8000; running:true; onTriggered:{console.log("FAIL files timeout",test.stage);Qt.quit()} }
}
''')
    env = dict(os.environ, HOME=str(home), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software")
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    assert "PASS files actual fd" in output and "FAIL" not in output, output
    print("PASS files: actual fd, modes, tilde, directories, path abbreviations, hidden filters and newline names")
