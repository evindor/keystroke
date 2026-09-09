#!/usr/bin/env python3
"""Animation tiers on the real palette, offscreen: the window reveal and
close, the highlight gliding to a new selection, a menu level sliding in and
the activated row's flash, in the Fluid tier and with animations off."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='keystroke-palette-motion-') as temp:
    work = Path(temp)
    project = work/'project'
    shutil.copytree(root, project, ignore=shutil.ignore_patterns('.git','.claude','.agents','.codex','tests','__pycache__'))
    (work/'qs').symlink_to('/usr/share/omarchy/shell')
    source = project/'Keystroke.qml'
    qml = source.read_text()
    qml = qml.replace('  id: root\n', '  id: root\n  property alias testList: resultList\n  property alias testShift: levelShift\n  property alias testCard: card\n  property alias testPanel: panel\n', 1)
    qml = qml.replace('  PanelWindow {','  Window {\n    transientParent: null\n    width: 1000; height: 800')
    qml = qml.replace('    anchors { top: true; bottom: true; left: true; right: true }\n','')
    source.write_text('\n'.join(line for line in qml.splitlines() if 'exclusionMode:' not in line and 'WlrLayershell.' not in line))
    (work/'shell.qml').write_text('''import QtQuick
import Quickshell
import "project"
import "project/ui"
ShellRoot {
 id: test
 property var flashes: []
 property var steps: []
 property int step: 0
 function check(ok,msg) { if(!ok) { console.log("FAIL",msg); Qt.quit(); throw Error(msg) } }
 function after(ms, fn) { steps.push({ms: ms, fn: fn}) }
 function next() { if (step >= steps.length) { console.log("PASS palette motion"); Qt.quit(); return } var s = steps[step++]; stepTimer.interval = s.ms; stepTimer.fn = s.fn; stepTimer.restart() }
 Timer { id: stepTimer; property var fn: null; onTriggered: { fn(); test.next() } }
 Keystroke { id: palette; omarchyPath:"/usr/share/omarchy"; onFlashed: function(uid) { test.flashes.push(uid) } }
 ResultRow { id: row; width: 400; flashRise: 20; flashFall: 60; selectedText: "#ffffff" }
 function flashLayer() { for (var i = 0; i < row.children.length; i++) { var c = row.children[i]; if (c.color !== undefined && String(c.color) === "#ffffff" && c.radius !== undefined) return c } return null }
 function fixture() {
   return [{key:"fixture",source:"bundled",patterns:[],provider:{name:"Fixture",settings:[],
     query:function(ctx) {
       if (ctx.scope === "deeper") return [{id:"d1",title:"Deep 1",score:100,action:{type:"noop"}}]
       return ["a","b","c","d"].map(function(id, i) { return {id:id,title:"Row "+id,score:100-i,action: id === "d" ? {type:"close"} : {type:"navigate",scope:"deeper",title:"Deeper"}} })
     }}}]
 }
 function highlightTarget() { var c = palette.testList.currentItem; return c.y + c.rowY }
 function configure(tier, transition) { palette.applyConfigText(JSON.stringify({version:1,matching:{mode:"off"},palette:{animations:tier,windowTransition:transition}})) }
 property real restingY: 0
 Timer { interval:250; running:true; onTriggered: {
   // ---- Fluid tier, sliding window
   test.configure("fluid", "slide")
   test.check(palette.motion.level === 2 && palette.motion.window >= 80, "fluid profile is active")
   palette.open('{}')
   palette.registry.entries = test.fixture()
   palette.runQuery()
   test.check(palette.opened && palette.testPanel.visible, "the window is mapped at once")
   test.check(palette.reveal < 1, "the reveal starts below 1: " + palette.reveal)
   test.after(300, function() {
     test.check(palette.reveal === 1, "the reveal reaches 1: " + palette.reveal)
     test.restingY = palette.testCard.y
     var h = palette.testList.highlightItem
     test.check(!!h && h.visible, "a highlight exists")
     test.check(h.y === test.highlightTarget() && h.height === palette.testList.currentItem.rowHeight, "the highlight sits on the first row: " + h.y + " " + h.height)
     palette.select(2)
     test.check(h.y !== test.highlightTarget(), "the highlight glides rather than jumps: " + h.y + " vs " + test.highlightTarget())
   })
   test.after(300, function() {
     var h = palette.testList.highlightItem
     test.check(palette.selected === 2 && h.y === test.highlightTarget(), "the highlight arrives on the third row: " + h.y + " vs " + test.highlightTarget())
     palette.activate()   // Row c navigates deeper
     test.check(test.flashes.join() === "fixture/c", "activation flashes the activated row")
     test.check(palette.scope === "deeper" && palette.testShift.x > 0 && palette.levelOpacity < 1, "a deeper level enters from the right: " + palette.testShift.x)
   })
   test.after(300, function() {
     test.check(palette.testShift.x === 0 && palette.levelOpacity === 1, "the level settles")
     palette.goBack()
     test.check(palette.scope === "" && palette.testShift.x < 0, "the parent level enters from the left: " + palette.testShift.x)
     var h = palette.testList.highlightItem
     test.check(!palette.selectionTouched && palette.selected === 0, "going back resets the selection")
   })
   test.after(300, function() {
     var h = palette.testList.highlightItem
     test.check(h.y === test.highlightTarget() && palette.selected === 0, "the highlight is back on the first row without gliding: " + h.y)
     palette.select(3)
   })
   test.after(300, function() {
     palette.activate()   // Row d closes the palette
     test.check(test.flashes.join() === "fixture/c,fixture/d", "closing through a row flashes it too")
     test.check(!palette.opened && palette.closing && palette.testPanel.visible, "the window stays mapped while leaving")
     test.check(palette.flashUntil > Date.now() - 5, "leaving waits for the flash to peak")
   })
   test.after(30, function() {
     test.check(palette.closing && palette.reveal > 0 && palette.reveal <= 1, "the reveal runs down: " + palette.reveal)
   })
   test.after(300, function() {
     test.check(!palette.closing && palette.reveal === 0 && !palette.testPanel.visible, "the window is unmapped after the fade: " + palette.reveal)
     test.check(palette.testCard.y > test.restingY, "slide up: the card rests lower while hidden: " + palette.testCard.y + " > " + test.restingY)
     // Reopening while leaving cancels the fade-out.
     palette.open('{}'); palette.registry.entries = test.fixture(); palette.runQuery()
     palette.cancel()
     test.check(palette.closing, "cancel starts leaving")
     palette.open('{}'); palette.registry.entries = test.fixture(); palette.runQuery()
     test.check(palette.opened && !palette.closing, "reopening while leaving keeps the window")
   })
   test.after(300, function() {
     test.check(palette.reveal === 1, "…and reveals it fully")
     palette.cancel()
   })
   // ---- Animations off: every change lands at once
   test.after(300, function() {
     test.configure("off", "fade")
     test.check(palette.motion.level === 0, "off profile is active")
     test.flashes = []
     palette.open('{}'); palette.registry.entries = test.fixture(); palette.runQuery()
     test.check(palette.reveal === 1 && !palette.closing, "off: the reveal is complete at once")
   })
   test.after(100, function() {
     var h = palette.testList.highlightItem
     test.check(h.y === test.highlightTarget(), "off: the highlight sits on the first row")
     palette.select(2)
     test.check(h.y === test.highlightTarget(), "off: the highlight jumps: " + h.y + " vs " + test.highlightTarget())
     palette.activate()
     test.check(test.flashes.length === 0 && palette.scope === "deeper" && palette.testShift.x === 0 && palette.levelOpacity === 1, "off: no flash, no slide")
     palette.goBack()
     test.check(palette.testShift.x === 0, "off: no slide back")
     palette.cancel()
     test.check(!palette.opened && !palette.closing && !palette.testPanel.visible && palette.reveal === 0, "off: the window unmaps at once")
   })
   // ---- The row's flash overlay pulses and settles
   test.after(10, function() {
     var layer = test.flashLayer()
     test.check(!!layer && layer.opacity === 0, "the flash layer starts transparent")
     row.flash()
   })
   test.after(25, function() {
     var layer = test.flashLayer()
     test.check(layer.opacity > 0.05, "the flash layer brightens: " + layer.opacity)
   })
   test.after(250, function() {
     var layer = test.flashLayer()
     test.check(layer.opacity === 0, "the flash layer settles back: " + layer.opacity)
     row.flashRise = 0; row.flashFall = 0
     row.flash()
     test.check(layer.opacity === 0, "a zero-length flash does nothing")
   })
   test.next()
 } }
 Timer { interval:15000; running:true; onTriggered:{ console.log("FAIL timeout at step",test.step,palette.errorMessage); Qt.quit() } }
}
''')
    env=dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_BACKEND='software', QML_IMPORT_PATH=str(work))
    env.pop('DISPLAY', None)
    env.pop('WAYLAND_DISPLAY', None)
    result=subprocess.run(['quickshell','-p',str(work/'shell.qml')],env=env,capture_output=True,text=True,timeout=25)
    output=result.stdout+result.stderr
    if os.environ.get("MOTION_VERBOSE"): print(output)
    assert 'PASS palette motion' in output and 'FAIL' not in output, output
    assert 'TypeError' not in output and 'ReferenceError' not in output, output
    print('PASS palette motion: reveal and close, gliding highlight, level slides, activation flash, and the off tier')
