import QtQuick
import "../core/Intent.js" as Intent

// One server slot, one request at a time. Partials replace the queued request
// instead of repeatedly aborting inference. Every callback checks ownership.
Item {
  id: root
  property string endpoint: "http://127.0.0.1:18781"
  enabled: false
  property bool watching: false
  property bool available: false
  property string modelName: ""
  property int lastMs: 0
  property string warmedStamp: ""
  property string warmingStamp: ""
  property double checkedAt: 0
  property var inflight: null
  property var warming: null
  property var probe: null
  property var modelProbe: null
  property var queued: null
  property int requestTimeout: 4000
  property int warmTimeout: 30000
  property int healthTimeout: 2000
  property var createRequest: function() { return new XMLHttpRequest() }
  readonly property bool ready: enabled && available
  readonly property bool busy: !!(inflight || warming || queued)

  signal answered(int index, bool none, string transcript, int ms, var context)
  signal failed(string message, string transcript)

  function base() { return String(endpoint || "").replace(/\/+$/, "") }
  function abortRequest(key) {
    var xhr = root[key]
    root[key] = null
    if (xhr) { try { xhr.abort() } catch (e) { } }
  }
  function check(force) {
    if (!root.enabled) return
    var now = Date.now()
    if (root.probe || (!force && root.checkedAt && now - root.checkedAt < 10000)) return
    root.checkedAt = now
    var xhr = root.createRequest()
    root.probe = xhr
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== 4 || root.probe !== xhr) return
      root.probe = null
      healthTimer.stop()
      var ok = false
      try { ok = xhr.status === 200 && JSON.parse(xhr.responseText).status === "ok" } catch (e) { }
      if (!ok) { root.warmedStamp = ""; root.modelName = "" }
      root.available = ok
      if (ok && !root.modelName) root.readModel()
    }
    healthTimer.restart()
    try { xhr.open("GET", root.base() + "/health"); xhr.send() }
    catch (e) { root.abortRequest("probe"); healthTimer.stop(); root.available = false }
  }
  function readModel() {
    if (root.modelProbe) return
    var xhr = root.createRequest()
    root.modelProbe = xhr
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== 4 || root.modelProbe !== xhr) return
      root.modelProbe = null
      modelTimer.stop()
      if (xhr.status !== 200) return
      try {
        var data = JSON.parse(xhr.responseText)
        var path = String(data.model_path || (data.default_generation_settings && data.default_generation_settings.model) || "")
        root.modelName = path.split("/").pop().replace(/\.gguf$/, "")
      } catch (e) { }
    }
    modelTimer.restart()
    try { xhr.open("GET", root.base() + "/props"); xhr.send() }
    catch (e) { root.abortRequest("modelProbe"); modelTimer.stop() }
  }
  function post(xhr, body) {
    try {
      xhr.open("POST", root.base() + "/v1/chat/completions")
      xhr.setRequestHeader("Content-Type", "application/json")
      xhr.send(JSON.stringify(body))
      return true
    } catch (e) { return false }
  }
  function warm(items) {
    if (!root.ready || !items || !items.length || root.inflight || root.queued) return
    var stamp = Intent.stamp(items)
    if (stamp === root.warmedStamp || root.warming) return
    var xhr = root.createRequest()
    root.warming = xhr
    root.warmingStamp = stamp
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== 4 || root.warming !== xhr) return
      root.warming = null
      root.warmingStamp = ""
      warmTimer.stop()
      if (xhr.status === 200) root.warmedStamp = stamp
      root.drain()
    }
    warmTimer.restart()
    if (!root.post(xhr, Intent.warmBody(items))) {
      root.abortRequest("warming"); root.warmingStamp = ""; warmTimer.stop()
    }
  }
  function ask(items, transcript, context) {
    if (!root.ready || !items || !items.length) return false
    root.queued = { items: items.slice(), transcript: transcript, context: context,
                    stamp: Intent.stamp(items), started: Date.now() }
    root.drain()
    return true
  }
  function drain() {
    if (root.inflight || root.warming || !root.queued) return
    var request = root.queued
    root.queued = null
    if (!root.ready) { root.failed("Assistant is not available", request.transcript); return }
    var xhr = root.createRequest()
    root.inflight = xhr
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== 4 || root.inflight !== xhr) return
      root.inflight = null
      requestTimer.stop()
      if (xhr.status === 200) {
        root.warmedStamp = request.stamp
        root.lastMs = Date.now() - request.started
        var a = Intent.parseAnswer(xhr.responseText, request.items.length)
        root.answered(a.index, a.none, request.transcript, root.lastMs, request.context)
      } else {
        root.failed("Assistant request failed (" + (xhr.status || "connection") + ")", request.transcript)
        if (xhr.status === 0) root.check(true)
      }
      root.drain()
    }
    requestTimer.transcript = request.transcript
    requestTimer.restart()
    if (!root.post(xhr, Intent.requestBody(request.items, request.transcript))) {
      root.abortRequest("inflight"); requestTimer.stop()
      root.failed("Could not contact the assistant", request.transcript)
      root.drain()
    }
  }
  function cancel(keepWarm) {
    root.queued = null
    requestTimer.stop()
    root.abortRequest("inflight")
    if (!keepWarm) {
      warmTimer.stop(); root.abortRequest("warming"); root.warmingStamp = ""
    }
  }
  function resetConnection() {
    root.cancel()
    healthTimer.stop(); modelTimer.stop()
    root.abortRequest("probe"); root.abortRequest("modelProbe")
    root.available = false; root.modelName = ""; root.warmedStamp = ""; root.checkedAt = 0
    if (root.enabled) root.check(true)
  }
  Timer {
    id: requestTimer
    interval: root.requestTimeout
    property string transcript: ""
    onTriggered: {
      root.abortRequest("inflight")
      root.failed("Assistant timed out; search results are ready", transcript)
      root.drain()
    }
  }
  Timer {
    id: warmTimer
    interval: root.warmTimeout
    onTriggered: { root.abortRequest("warming"); root.warmingStamp = ""; root.drain() }
  }
  Timer {
    id: healthTimer
    interval: root.healthTimeout
    onTriggered: { root.abortRequest("probe"); root.available = false; root.warmedStamp = "" }
  }
  Timer { id: modelTimer; interval: root.healthTimeout; onTriggered: root.abortRequest("modelProbe") }
  Timer {
    interval: 750
    repeat: true
    running: root.enabled && root.watching && !root.available
    onTriggered: root.check(true)
  }
  onWatchingChanged: { if (root.watching) root.check(true) }
  onEnabledChanged: root.resetConnection()
  onEndpointChanged: root.resetConnection()
  Component.onDestruction: root.cancel()
}
