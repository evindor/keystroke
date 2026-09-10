#!/usr/bin/env python3
"""Guarded Omarchy catalog uses actual provider code without executing commands."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='keystroke-catalog-') as temp:
    work=Path(temp)
    for folder in ['providers','core','omarchy']:
        shutil.copytree(root/folder,work/folder)
    (work/'qs').symlink_to('/usr/share/omarchy/shell')
    (work/'shell.qml').write_text('''import QtQuick
import Quickshell
import "providers"
ShellRoot {
  OmarchyMenu { id: menu }
  function check(ok,msg) { if(!ok) { console.log("FAIL",msg); Qt.quit(); throw Error(msg) } }
  Timer { interval:100; running:true; onTriggered: {
    menu.items = {
      root:{id:"root",parent:"",kind:"menu",label:"Root",aliases:[]},
      group:{id:"group",parent:"root",kind:"menu",label:"Group",aliases:[],when:"guard-parent"},
      child:{id:"child",parent:"group",kind:"action",label:"Child",aliases:[],action:"never-run"},
      guarded:{id:"guarded",parent:"root",kind:"action",label:"Guarded",aliases:[],when:"guard-child",action:"never-run"},
      visible:{id:"visible",parent:"root",kind:"action",label:"Visible",aliases:[],action:"never-run"}
    }
    menu.itemOrder=["root","group","child","guarded","visible"]
    menu.pathCache=({}); menu.rowsLoaded=true; menu.whenResults=({})
    var ctx={scope:"",sub:"",settings:{confirmDestructive:true}}
    var rows=menu.catalog(ctx)
    check(rows.length===1 && rows[0].id==="visible","unknown guards and their descendants are excluded")
    menu.whenResults={group:true,guarded:false}
    rows=menu.catalog(ctx)
    check(rows.some(r=>r.id==="child") && !rows.some(r=>r.id==="guarded"),"resolved visibility respected")
    ctx.sub="group"
    rows=menu.catalog(ctx)
    check(rows.length===1 && rows[0].id==="child","subtree scope respected")
    menu.whenResults={group:false,guarded:true}
    check(menu.catalog(ctx).length===0,"ancestor becoming unavailable removes descendants")
    console.log("PASS catalog guards and scopes"); Qt.quit()
  } }
}
''')
    env=dict(os.environ,HOME=str(work),OMARCHY_PATH=str(work/'absent'),XDG_RUNTIME_DIR=str(work),QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_BACKEND='software',QML_IMPORT_PATH=str(work))
    env.pop('DISPLAY',None);env.pop('WAYLAND_DISPLAY',None)
    result=subprocess.run(['quickshell','-p',str(work/'shell.qml')],env=env,capture_output=True,text=True,timeout=10)
    output=result.stdout+result.stderr
    assert 'PASS catalog guards and scopes' in output and 'FAIL' not in output,output
    print('PASS catalog: unresolved guards, ancestor visibility, updates and scoped enumeration')
