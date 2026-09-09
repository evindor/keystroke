#!/usr/bin/env python3
"""Exercise actual palette routing with deterministic local embedding responses."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='keystroke-palette-matching-') as temp:
    work = Path(temp)
    project = work/'project'
    shutil.copytree(root, project, ignore=shutil.ignore_patterns('.git','.claude','.agents','.codex','tests','__pycache__'))
    (work/'qs').symlink_to('/usr/share/omarchy/shell')
    source = project/'Keystroke.qml'
    qml = source.read_text().replace('  id: root\n', '  id: root\n  property alias testMatching: matchingSession\n', 1)
    qml = qml.replace('  PanelWindow {','  Window {\n    transientParent: null\n    width: 1000; height: 800')
    qml = qml.replace('    anchors { top: true; bottom: true; left: true; right: true }\n','')
    source.write_text('\n'.join(line for line in qml.splitlines() if 'exclusionMode:' not in line and 'WlrLayershell.' not in line))
    fake = work/'worker.py'
    fake.write_text('''import json,sys,time
print(json.dumps({'type':'ready'}),flush=True)
for line in sys.stdin:
 r=json.loads(line)
 if 'rows' in r: rows=r['rows']
 time.sleep(.05)
 print(json.dumps({'type':'result','id':r['id'],'matches':[{'id':x['id'],'score':.85} for x in rows]}),flush=True)
''')
    (work/'shell.qml').write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
 id: test
 property int stage: 0
 property int ticks: 0
 property bool targetVisible: true
 property string rawSeen: ""
 property string querySeen: ""
 function check(ok,msg) { if(!ok) { console.log("FAIL",msg); Qt.quit(); throw Error(msg) } }
 function configure(mode) { palette.applyConfigText(JSON.stringify({version:1,matching:{mode:mode,model:"small"}})) }
 function fixture() {
   palette.registry.entries = [{key:"fixture",source:"bundled",patterns:[],provider:{name:"Fixture",settings:[],
     query:function(ctx) { test.rawSeen=ctx.rawQuery; test.querySeen=ctx.query; return ctx.query==="literal" ? [{id:"exact",title:"Literal",score:120,action:{type:"noop"}}] : [] },
     catalog:function(ctx) { return test.targetVisible ? [{id:"target",title:"Workspace overview",score:1,action:{type:"noop"}}] : [] }
   }}]
 }
 Keystroke { id: palette; omarchyPath:"/usr/share/omarchy" }
 Timer { interval:250; running:true; onTriggered:{
   palette.testMatching.command=["python3",%s]
   test.configure("voice")
   palette.open('{}'); test.fixture()
   var before=palette.generation
   palette.setQuery("show everythings"); palette.requery()
   palette.setQuery("show everything"); palette.requery()
   test.check(palette.generation===before,"typing and async refreshes respect debounce")
   test.check(!palette.testMatching.starting && !palette.testMatching.queued,"voice-only excludes typed input")
   test.stage=1
 } }
 Timer { interval:50; repeat:true; running:true; onTriggered:{
   if(test.stage===1 && ++test.ticks>4) {
     test.check(test.querySeen==="show everything","debounce eventually processes the latest edit")
     test.check(palette.rows.length===0,"debounced typed query has no semantic results in voice-only mode")
     test.check(!palette.testMatching.loaded,"typed input never loads voice-only model")
     palette.voiceRawText="show everything"; palette.runQuery(); test.stage=2
   } else if(test.stage===2 && palette.rows.length) {
     test.check(palette.rows[0].uid==="fixture/target" && palette.rows[0].smartMatch,"voice semantic result merged")
     test.check(test.rawSeen==="show everything","raw transcript reaches provider unchanged")
     test.targetVisible=false; palette.runQuery()
     test.check(palette.rows.length===0,"removed catalog entry disappears immediately")
     test.targetVisible=true; test.configure("all")
     palette.setQuery("show everything"); palette.runQuery(); test.stage=3
   } else if(test.stage===3 && palette.rows.length) {
     test.check(palette.rows[0].smartMatch,"default all mode matches typed input")
     palette.setQuery("MiXeD/path.PDF"); palette.runQuery()
     test.check(test.querySeen==="MiXeD/path.PDF","smart matching preserves typed provider arguments and case")
     palette.scope="unrelated"; palette.runQuery()
     test.check(palette.rows.length===0,"scope excludes other providers")
     palette.scope=""; test.configure("off"); palette.runQuery()
     test.check(!palette.testMatching.loaded && !palette.testMatching.queued && palette.rows.length===0,"off unloads and removes semantic rows")
     palette.setQuery("literal"); palette.runQuery()
     test.check(palette.rows.length===1 && palette.rows[0].id==="exact","off preserves ordinary matching")
     palette.selectionTouched=true; palette.selected=0
     var chosen=palette.rows[0]
     palette.applyRows([{uid:"new",title:"New",score:130},chosen])
     test.check(palette.current.uid===chosen.uid,"late ranking preserves selected UID")
     palette.usage={}
     palette.registry.entries=[{key:"fixture",source:"bundled",patterns:[],provider:{name:"Fixture",settings:[],
       query:function(ctx) { return [
         {id:"video",title:"Download video from web app",score:100,remember:true,action:{type:"noop"}},
         {id:"downloads",title:"Downloads",score:55,remember:true,action:{type:"noop"}}
       ] }
     }}]
     palette.setQuery("downlo"); palette.runQuery()
     test.check(palette.rows[0].id==="video","unlearned provider scores establish order")
     var learningFixture=palette.registry.entries
     palette.selected=1; palette.activate(false)
     palette.open('{}'); palette.registry.entries=learningFixture; palette.setQuery("downlo"); palette.runQuery()
     test.check(palette.rows[0].id==="downloads","one activation teaches the host query preference")
     test.configure("all"); palette.runQuery()
     test.check(palette.rows[0].id==="downloads","smart merge preserves learned ranking")
     palette.setQuery("download video"); palette.runQuery()
     test.check(palette.rows[0].id==="video","learning is local to the chosen query")
     var usageBefore=JSON.stringify(palette.usage)
     palette.setQuery("downlo"); palette.activate(false)
     test.check(palette.rows[0].id==="downloads" && JSON.stringify(palette.usage)!==usageBefore,"Enter flushes pending query before activation")
     palette.registry.entries=[
       {key:"files",source:"bundled",patterns:[],provider:{name:"Files",settings:[],query:function(ctx){
         test.check(ctx.query==="~dwnlds","file prefix reaches its provider unchanged")
         return [{id:"Downloads",title:"Downloads",score:55,action:{type:"noop"}}]
       }}},
       {key:"fixture",source:"bundled",patterns:[],provider:{name:"Other",settings:[],query:function(){throw Error("tilde must isolate files")}}}
     ]
     palette.setQuery("~dwnlds"); palette.runQuery()
     test.check(palette.rows.length===1 && palette.rows[0].providerKey==="files" && !palette.errorMessage,"tilde restricts search to files")
     test.check(!palette.testMatching.queued && palette.testMatching.requestedKey==="","tilde bypasses embeddings")
     palette.cancel()
     console.log("PASS palette matching modes, scope, catalog invalidation, raw text, exact fallback and selection")
     Qt.quit(); test.stage=4
   }
 } }
 Timer { interval:10000; running:true; onTriggered:{ console.log("FAIL timeout",test.stage,palette.errorMessage,palette.testMatching.status,palette.testMatching.error); Qt.quit() } }
}
''' % json.dumps(str(fake)))
    env=dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_BACKEND='software', QML_IMPORT_PATH=str(work))
    env.pop('DISPLAY', None)
    env.pop('WAYLAND_DISPLAY', None)
    result=subprocess.run(['quickshell','-p',str(work/'shell.qml')],env=env,capture_output=True,text=True,timeout=15)
    output=result.stdout+result.stderr
    assert 'PASS palette matching modes' in output and 'FAIL' not in output, output
    assert 'TypeError' not in output and 'ReferenceError' not in output, output
    print('PASS palette matching: modes, scopes, catalog invalidation, raw text, exact fallback and selection')
