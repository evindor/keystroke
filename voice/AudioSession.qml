import QtQuick
import Quickshell.Io
import "../core/AudioIntent.js" as AudioIntent

// One bounded capture process per interaction; the model stays in a user service.
Item {
  id: root
  property var host: null
  enabled: false
  property bool watching: false
  property string endpoint: "http://127.0.0.1:18782"
  property string helperPath: decodeURIComponent(Qt.resolvedUrl("../helpers/audio_record.py").toString().replace(/^file:\/\//, ""))
  property var catalog: []
  property bool detected: false
  property bool available: false
  readonly property string version: "Gemma 4 E2B INT4 · vLLM"
  readonly property string daemonState: root.available ? (root.active ? root.phase : "idle") : ""
  readonly property bool daemonRunning: root.available
  readonly property string command: "pw-record → vLLM"
  property string phase: "idle"
  readonly property bool active: root.phase !== "idle"
  property string liveText: ""
  property bool hasRevision: false
  property real level: 0
  property real peak: 0
  property bool vad: false
  property var history: []
  property int lastMs: 0
  property var healthRequest: null
  property var warmRequest: null
  property string warmedPrompt: ""
  property string sessionConfig: ""
  property int sessionCount: 0
  property bool started: false
  property string pendingControl: ""
  signal partial(string text)
  signal transcribed(string text)
  signal recognized(int index, string text, int ms)
  signal nothingHeard()
  signal failed(string message)

  function refresh() {
    if (!probe.running) probe.running = true
    if (!root.enabled || root.healthRequest) return
    var req = new XMLHttpRequest()
    root.healthRequest = req
    req.onreadystatechange = function() {
      if (req.readyState !== XMLHttpRequest.DONE || root.healthRequest !== req) return
      healthTimeout.stop()
      root.healthRequest = null
      root.available = req.status === 200
      if (!root.available) root.warmedPrompt = ""
    }
    req.open("GET", root.endpoint + "/health")
    req.send()
    healthTimeout.restart()
  }
  Process {
    id: probe
    command: ["python3", root.helperPath, "--probe"]
    stdout: StdioCollector { id: probeOut }
    onExited: function(code) {
      try { root.detected = code === 0 && JSON.parse(probeOut.text).detected === true }
      catch (e) { root.detected = false }
    }
  }
  Timer { interval: 2000; repeat: true; running: root.enabled && (root.watching || !root.available); onTriggered: root.refresh() }
  Timer {
    id: healthTimeout; interval: 1800
    onTriggered: {
      var req = root.healthRequest; root.healthRequest = null
      if (req) req.abort()
      root.available = false; root.warmedPrompt = ""
    }
  }
  function warm(items) {
    if (!root.enabled || !root.available || root.active || root.warmRequest) return
    var body = AudioIntent.warmBody(items)
    var prompt = body.messages[0].content
    if (prompt === root.warmedPrompt) return
    var req = new XMLHttpRequest()
    root.warmRequest = req
    req.onreadystatechange = function() {
      if (req.readyState !== XMLHttpRequest.DONE || root.warmRequest !== req) return
      warmTimeout.stop(); root.warmRequest = null
      if (req.status === 200) root.warmedPrompt = prompt
    }
    req.open("POST", root.endpoint + "/v1/chat/completions")
    req.setRequestHeader("Content-Type", "application/json")
    req.send(JSON.stringify(body))
    warmTimeout.restart()
  }
  Timer {
    id: warmTimeout; interval: 30000
    onTriggered: { var req = root.warmRequest; root.warmRequest = null; if (req) req.abort() }
  }
  function start() {
    if (root.active || capture.running) { root.failed("Voice is finishing the previous recording; try again"); return false }
    if (!root.enabled || !root.detected || !root.available) { root.refresh(); root.failed("Gemma is starting; try again when the voice server is ready"); return false }
    root.history = []; root.level = 0; root.peak = 0; root.vad = false; root.liveText = ""; root.hasRevision = false
    root.started = false; root.pendingControl = ""
    root.sessionCount = root.catalog.length
    root.sessionConfig = JSON.stringify({ endpoint: root.endpoint, prompt: AudioIntent.prompt(root.catalog), count: root.sessionCount })
    root.phase = "starting"
    capture.running = true
    return true
  }
  function control(action) {
    if (root.started) capture.write(JSON.stringify({action: action}) + "\n")
    else root.pendingControl = action
  }
  function stop() {
    if (root.phase !== "starting" && root.phase !== "listening") return
    root.phase = "transcribing"
    root.control("stop")
  }
  function finish() {
    root.phase = "idle"; root.level = 0; root.peak = 0; root.vad = false; root.liveText = ""
  }
  function cancel() {
    if (!capture.running) { root.finish(); return }
    root.finish()
    root.control("cancel")
    cancelTimeout.restart()
  }
  Timer { id: cancelTimeout; interval: 1000; onTriggered: { if (capture.running) capture.signal(9) } }
  function receive(line) {
    if (!root.active) return
    var value
    try { value = JSON.parse(line) } catch (e) { return }
    if (value.event === "listening") {
      if (root.phase === "starting") root.phase = "listening"
    } else if (value.event === "level") {
      var loud = Math.min(1, Number(value.peak || 0) * 2.5)
      root.peak = loud; root.level = Math.max(loud, root.level * .82); root.vad = Number(value.rms || 0) > .002
      root.history = root.history.slice(-47).concat([root.level])
    } else if (value.event === "stopping") root.phase = "transcribing"
    else if (value.event === "preview") {
      // Stream the first words; keep a completed revision visible until its
      // replacement is complete instead of clearing/retyping it token by token.
      if (!root.hasRevision && String(value.text || "")) {
        root.liveText = String(value.text)
        root.partial(root.liveText)
      }
    } else if (value.event === "result") {
      root.hasRevision = true
      var text = String(value.text || "")
      var index = AudioIntent.validIndex(value.index, root.sessionCount) ? value.index : 0
      root.lastMs = Number(value.ms || 0)
      if (value.final) {
        root.finish()
        if (text) { root.transcribed(text); root.recognized(index, text, root.lastMs) }
        else root.nothingHeard()
      } else {
        root.liveText = text; root.partial(text); root.recognized(index, text, root.lastMs)
      }
    } else if (value.event === "empty") { root.finish(); root.nothingHeard() }
    else if (value.event === "error") { root.finish(); root.failed(String(value.message || "Audio transcription failed")) }
  }
  Process {
    id: capture
    command: ["python3", root.helperPath]
    stdinEnabled: true
    stdout: SplitParser { onRead: function(line) { root.receive(String(line)) } }
    stderr: StdioCollector {}
    onStarted: {
      root.started = true
      write(root.sessionConfig + "\n")
      root.sessionConfig = ""
      if (root.pendingControl) { root.control(root.pendingControl); root.pendingControl = "" }
    }
    onExited: function(code) {
      cancelTimeout.stop(); root.started = false; root.sessionConfig = ""
      if (root.active) { root.finish(); root.failed("Audio capture ended before transcription completed (" + code + ")") }
    }
  }
  onEnabledChanged: { if (root.enabled) root.refresh(); else root.cancel() }
  onEndpointChanged: { root.available = false; root.warmedPrompt = ""; if (root.enabled) root.refresh() }
  Component.onDestruction: { if (root.healthRequest) root.healthRequest.abort(); if (root.warmRequest) root.warmRequest.abort() }
}
