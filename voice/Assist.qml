import QtQuick
import "../core/Intent.js" as Intent

// Client for a local llama-server (OpenAI-compatible HTTP) that maps a
// spoken command to one catalog row. Nothing runs while idle: a health
// probe when the palette opens, one warm-up request when the catalog
// changed, one request per transcript. Requests are XMLHttpRequest from the
// QML engine, so no helper process is involved.
Item {
  id: root
  property string endpoint: "http://127.0.0.1:18781"
  property bool enabled: false
  property bool available: false      // /health answered ok since the last probe
  property string modelName: ""
  property int lastMs: 0               // duration of the last answered request
  property string warmedStamp: ""
  property double checkedAt: 0
  property var inflight: null
  property var warming: null
  readonly property bool ready: enabled && available

  signal answered(int index, bool none, string transcript, int ms)
  signal failed(string message, string transcript)

  function base() { return String(endpoint || "").replace(/\/+$/, "") }

  // At most one probe every 10 s: opening the palette must stay cheap.
  function check(force) {
    if (!root.enabled) { root.available = false; return }
    var now = Date.now()
    if (!force && root.checkedAt && now - root.checkedAt < 10000) return
    root.checkedAt = now
    var xhr = new XMLHttpRequest()
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== XMLHttpRequest.DONE) return
      var ok = xhr.status === 200 && /"ok"/.test(String(xhr.responseText || ""))
      if (ok !== root.available) root.available = ok
      if (!ok) { root.warmedStamp = ""; root.modelName = "" }
      else if (!root.modelName) root.readModel()
    }
    try { xhr.open("GET", root.base() + "/health"); xhr.send() } catch (e) { root.available = false }
  }

  function readModel() {
    var xhr = new XMLHttpRequest()
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== XMLHttpRequest.DONE || xhr.status !== 200) return
      try {
        var data = JSON.parse(xhr.responseText)
        var path = String(data.model_path || (data.default_generation_settings && data.default_generation_settings.model) || "")
        root.modelName = path.split("/").pop().replace(/\.gguf$/, "")
      } catch (e) { }
    }
    try { xhr.open("GET", root.base() + "/props"); xhr.send() } catch (e) { }
  }

  // Put the catalog in the server's prefix cache. Fire-and-forget; a warm-up
  // still in flight is dropped when the catalog changes again.
  function warm(items) {
    if (!root.ready || !items || !items.length) return
    var s = Intent.stamp(items)
    if (s === root.warmedStamp) return
    if (root.warming) { try { root.warming.abort() } catch (e) { } root.warming = null }
    var xhr = new XMLHttpRequest()
    root.warming = xhr
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== XMLHttpRequest.DONE) return
      if (root.warming === xhr) root.warming = null
      if (xhr.status === 200) root.warmedStamp = s
      else if (xhr.status === 0) root.check(true)
    }
    root.post(xhr, Intent.warmBody(items))
  }

  function ask(items, transcript) {
    root.cancel()
    if (!root.ready) { root.failed("Assistant is not available", transcript); return false }
    if (!items || !items.length) { root.failed("Nothing to match against", transcript); return false }
    var started = Date.now()
    var xhr = new XMLHttpRequest()
    root.inflight = xhr
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== XMLHttpRequest.DONE) return
      if (root.inflight !== xhr) return           // superseded or cancelled
      root.inflight = null
      timeout.stop()
      var ms = Date.now() - started
      if (xhr.status !== 200) {
        if (xhr.status === 0) root.check(true)
        root.failed("llama-server answered " + (xhr.status || "nothing") + (xhr.responseText ? ": " + String(xhr.responseText).slice(0, 120) : ""), transcript)
        return
      }
      root.lastMs = ms
      var a = Intent.parseAnswer(xhr.responseText, items.length)
      root.answered(a.index, a.none, transcript, ms)
    }
    timeout.transcript = transcript
    timeout.restart()
    root.post(xhr, Intent.requestBody(items, transcript))
    return true
  }

  function post(xhr, body) {
    try {
      xhr.open("POST", root.base() + "/v1/chat/completions")
      xhr.setRequestHeader("Content-Type", "application/json")
      xhr.send(JSON.stringify(body))
    } catch (e) {
      root.available = false
      if (root.inflight === xhr) { root.inflight = null; root.failed(String(e), timeout.transcript) }
    }
  }

  function cancel() {
    timeout.stop()
    if (root.inflight) { var x = root.inflight; root.inflight = null; try { x.abort() } catch (e) { } }
  }

  // A stalled server must not hold a keypress hostage: the fuzzy results
  // are already on screen, the assistant only reorders them.
  Timer {
    id: timeout
    interval: 4000
    property string transcript: ""
    onTriggered: { if (root.inflight) { var x = root.inflight; root.inflight = null; try { x.abort() } catch (e) { } root.failed("llama-server took longer than 4 s", transcript) } }
  }

  onEnabledChanged: { if (enabled) root.check(true); else { root.cancel(); root.available = false } }
  onEndpointChanged: { root.warmedStamp = ""; root.checkedAt = 0; root.check(true) }
}
