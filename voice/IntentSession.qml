import QtQuick
import "../core/Intent.js" as Intent

// The session owns a catalog snapshot and the latest spoken query. It can
// suggest a row, never execute it. Late answers cannot overwrite a newer edit.
Item {
  id: root
  property var assistant: null
  property var catalog: ({ items: [], rows: [] })
  property bool active: false
  property string transcript: ""
  property string key: ""
  property string requestedKey: ""
  property string answeredKey: ""
  property var pick: null
  property string status: ""
  property int partialInterval: 300
  readonly property string query: Intent.normalize(root.transcript)

  function begin(snapshot) {
    root.cancel(true)
    root.catalog = snapshot
    root.active = true
  }
  function update(raw, final) {
    if (!root.active) return
    var next = Intent.transcriptKey(raw)
    root.transcript = String(raw || "").trim()
    if (next !== root.key) {
      root.key = next
      root.pick = null
      root.answeredKey = ""
      root.status = ""
    }
    if (!next || next === root.answeredKey) { partialTimer.stop(); return }
    if (final) { partialTimer.stop(); root.flush() }
    else if (!partialTimer.running) partialTimer.start()
  }
  function flush() {
    if (!root.active || !root.key || root.key === root.requestedKey || root.key === root.answeredKey) return
    if (!root.assistant || !root.assistant.ready) return
    root.requestedKey = root.key
    if (root.assistant.ask(root.catalog.items, root.transcript, root.catalog.rows)) {
      root.status = root.assistant.warming ? "Preparing assistant…" : "Finding your command…"
    } else root.requestedKey = ""
  }
  function cancel(keepWarm) {
    partialTimer.stop()
    root.active = false
    root.transcript = ""; root.key = ""; root.requestedKey = ""; root.answeredKey = ""
    root.pick = null; root.status = ""
    if (root.assistant) root.assistant.cancel(keepWarm)
  }
  Connections {
    target: root.assistant
    function onAnswered(index, none, transcript, ms, context) {
      var answerKey = Intent.transcriptKey(transcript)
      if (answerKey === root.requestedKey) root.requestedKey = ""
      if (!root.active || answerKey !== root.key) return
      root.answeredKey = root.key
      root.requestedKey = ""
      root.pick = index >= 1 && context && index <= context.length ? context[index - 1] : null
      root.status = root.pick ? "Suggested: " + root.pick.title + " · " + ms + " ms"
                              : "No assistant match · search results are ready"
    }
    function onFailed(message, transcript) {
      var answerKey = Intent.transcriptKey(transcript)
      if (answerKey === root.requestedKey) root.requestedKey = ""
      if (!root.active || answerKey !== root.key) return
      root.status = message
    }
    function onReadyChanged() {
      if (root.assistant.ready && root.active) {
        root.assistant.warm(root.catalog.items)
        root.flush()
      } else if (!root.assistant.ready) {
        root.pick = null
        root.answeredKey = ""; root.requestedKey = ""
      }
    }
  }
  Timer { id: partialTimer; interval: root.partialInterval; onTriggered: root.flush() }
}
