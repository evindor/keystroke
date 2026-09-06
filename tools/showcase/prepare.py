#!/usr/bin/env python3
"""Build a disposable capture plugin. Never reads personal provider data.

The running omarchy-shell renders the actual palette/row/preview/conversation
components. Demo rows are deliberate fixtures, not reconstructed UI artwork.
The production plugin is never changed. See README.md for the live lifecycle.
"""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
DEST = Path('/tmp/keystroke-showcase-plugin')
DEST.mkdir(exist_ok=True)
for folder in ('core', 'ui', 'voice', 'codex'):
    shutil.copytree(ROOT / folder, DEST / folder, dirs_exist_ok=True)
(DEST / 'providers').mkdir(exist_ok=True)
for name in ('Calculator', 'Colors'):
    shutil.copy2(ROOT / 'providers' / (name + '.qml'), DEST / 'providers' / (name + '.qml'))
# No provider with access to user files, history, installed apps, network or mic
# is instantiated. The fixture registry still satisfies the host contract.
(DEST / 'providers/Registry.qml').write_text('''import QtQuick
Item {
  property var host: null
  property var entries: []
  property var problems: []
  property var bundled: [{reload: function() {}, routeFor: function() { return {id:"root"} }, provider: {id:"omarchy",name:"Omarchy"}}]
  function rebuild() {}
}
''')
(DEST / 'voice/VoiceSession.qml').write_text('''import QtQuick
Item {
  property var host: null
  property bool detected: true
  property string version: "demo"
  property string command: ""
  property string daemonState: "idle"
  property string phase: "idle"
  readonly property bool active: phase !== "idle"
  property string liveText: ""
  property var history: []
  property real level: 0
  signal partial(string text)
  signal transcribed(string text)
  signal nothingHeard()
  signal failed(string message)
  function refresh() {}
  function start() { return false }
  function stop() { phase = "idle" }
  function cancel() { phase = "idle" }
}
''')
s = (ROOT / 'Keystroke.qml').read_text()
s = s.replace('import "core/Match.js" as Match', 'import "codex"\nimport "core/Units.js" as Units\nimport "core/Match.js" as Match')
s = s.replace('Quickshell.env("HOME")', '"/tmp/keystroke-showcase-empty-home"')
s = s.replace('  function runQuery() {', '  function runQuery() { return;')
s = s.replace('  function activate(alternate) {', '  function activate(alternate) { return;')
s = s.replace('  function perform(effect, row) {', '  function perform(effect, row) { return;')
s = s.replace('  function open(payloadJson) {', '''  Calculator { id: demoCalculator }
  Colors { id: demoColors }
  QtObject {
    id: demoSession
    property var approvals: []
    property var messages: []
    property string draft: ""
    property string mode: "quick"
    property string cwd: ""
    property string threadId: "demo"
    property string phase: "idle"
    property bool busy: false
    property string error: ""
    property string activity: ""
    property var settings: ({model:"gpt-5.6-luna",fast:true})
    function dismiss() {}
    function answer() { return messages.length > 1 ? messages[1].text : "" }
  }
  Component { id: demoConversation; ConversationView { session: demoSession } }
  function screenshot(arg) {
    var p = JSON.parse(arg)
    card.grabToImage(function(result) { result.saveToFile(p.path) }, Qt.size(card.width * 2, card.height * 2))
    return "capturing"
  }
  function open(payloadJson) {
    var p = JSON.parse(payloadJson || "{}")
    root.closeProviderView()
    voice.cancel()
    root.scope = p.scope || ""
    root.scopeTitle = p.title || ""
    search.text = p.query || ""
    search.cursorVisible = false
    root.applyConfigText(JSON.stringify({version:1,palette:{accent:"ember"},providers:{}}))
    var rows = p.rows || []
    if (p.compute === "calculator") rows = demoCalculator.query({query:p.query,scope:"calculator",settings:{precision:12}}).concat(rows)
    if (p.compute === "colors") rows = demoColors.query({query:p.query,scope:"",settings:{format:"hex"}}).concat(rows)
    if (p.compute === "converter") {
      var c = Units.convert(p.query), answer = Units.formatValue(c.value) + " " + c.unit
      rows.unshift({id:"conversion",title:answer,subtitle:Units.detailFor(c.unit),icon:"󰯍",section:"Converter",verb:"Copy result",tier:"answer",score:195,preview:answer,previewLabel:"CONVERSION",previewDetail:p.query})
    }
    root.applyRows(rows.map(function(row, i) {
      row.id = row.id || "demo-" + i
      row.score = 100
      return root.normalize(row, {key:p.provider || "demo",provider:{name:p.providerName || p.title || "Keystroke"},source:row.badge ? "community" : "bundled"}, "")
    }))
    root.resetSelection()
    resultList.positionViewAtBeginning()
    root.opened = true
    if (p.voice) {
      voice.phase = "listening"
      voice.history = [0.1,0.2,0.5,0.7,0.4,0.2,0.4,0.9,0.7,0.3,0.15,0.6,0.8,0.4,0.2,0.4,0.6,0.9,0.6,0.3]
      voice.level = 0.65
      root.voiceTrigger = "hold"
    }
    if (p.conversation) {
      demoSession.messages = p.conversation
      demoSession.draft = p.draft || ""
      root.activeProviderKey = "codex"
      providerView.sourceComponent = demoConversation
    }
  }
  function unusedProductionOpen(payloadJson) {''')
(DEST / 'Keystroke.qml').write_text(s)
(DEST / 'manifest.json').write_text(json.dumps({
    'schemaVersion': 1, 'id': 'local.keystroke-showcase', 'name': 'Keystroke capture fixture',
    'version': '1.0.0', 'author': 'Keystroke', 'description': 'Temporary private-data-free screenshot fixture',
    'kinds': ['overlay'], 'keepLoaded': True, 'entryPoints': {'overlay': 'Keystroke.qml'}
}, indent=2))
print(DEST)
