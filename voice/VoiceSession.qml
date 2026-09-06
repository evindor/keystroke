import QtQuick
import Quickshell
import Quickshell.Io

// Voice entry through the voxtype daemon Omarchy already ships. One recording
// at a time: `voxtype record start --file … --no-osd` (voxtype hides its own
// overlay for tools that draw their own), audio levels from voxtype's own
// bridge socket while listening, then `voxtype record stop --wait --json` to
// collect the transcript. Nothing runs while idle except the state watcher.
//
// phase: idle › starting › listening › transcribing › idle
Item {
  id: root
  property var host: null

  readonly property string runtimeDir: Quickshell.env("XDG_RUNTIME_DIR") || "/tmp"
  readonly property string transcriptPath: runtimeDir + "/keystroke-voice.txt"
  readonly property string statePath: runtimeDir + "/voxtype/state"

  property bool detected: false          // voxtype on PATH
  property string version: ""
  property string daemonState: ""        // idle | recording | streaming | transcribing | "" (no daemon)
  readonly property bool daemonRunning: daemonState !== ""
  property string phase: "idle"          // idle | starting | listening | transcribing
  readonly property bool active: phase !== "idle"
  property real level: 0                 // smoothed loudness, 0..1
  property real peak: 0
  property bool vad: false
  property var history: []               // recent loudness samples, newest last
  property bool stopWhenStarted: false
  property bool cancelWhenStarted: false
  property double detectedAt: 0

  signal transcribed(string text)
  signal nothingHeard()
  signal failed(string message)

  // ------------------------------------------------------------ detection
  function refresh() {
    if (detectProc.running) return
    var now = Date.now()
    if (root.detectedAt && now - root.detectedAt < 30000) return
    root.detectedAt = now
    detectProc.running = true
  }
  Process {
    id: detectProc
    command: ["sh", "-c", "command -v voxtype >/dev/null 2>&1 && exec voxtype --version"]
    stdout: StdioCollector { id: detectOut }
    onExited: function(code) {
      var line = String(detectOut.text || "").trim()
      root.detected = code === 0 && line.length > 0
      root.version = root.detected ? line.replace(/^voxtype\s+/i, "") : ""
    }
  }
  FileView {
    id: stateFile
    path: root.statePath
    watchChanges: true
    printErrors: false
    onLoaded: root.daemonState = String(text() || "idle").trim() || "idle"
    onLoadFailed: root.daemonState = ""
    onFileChanged: reload()
  }
  // The daemon stops on its own at its max duration; follow it instead of
  // listening to a recording that no longer exists.
  onDaemonStateChanged: { if (root.phase === "listening" && root.daemonState === "transcribing") root.stop() }

  // -------------------------------------------------------------- session
  function start() {
    if (root.phase !== "idle") return false
    root.stopWhenStarted = false
    root.cancelWhenStarted = false
    root.history = []
    root.level = 0
    root.peak = 0
    root.vad = false
    root.phase = "starting"
    startProc.running = true
    return true
  }
  Process {
    id: startProc
    command: ["sh", "-c", "rm -f \"$1\"; exec voxtype record start --file=\"$1\" --no-osd", "keystroke", root.transcriptPath]
    stdout: StdioCollector { id: startOut }
    stderr: StdioCollector { id: startErr }
    onExited: function(code) {
      if (root.phase !== "starting") return
      if (code !== 0) {
        root.phase = "idle"
        var why = String(startErr.text || startOut.text || "").trim().split("\n").pop() || ("voxtype record start exited " + code)
        root.failed(root.daemonRunning ? why : "Voxtype daemon is not running (systemctl --user start voxtype)")
        return
      }
      if (root.cancelWhenStarted) { root.phase = "listening"; root.cancel(); return }
      root.phase = "listening"
      if (root.stopWhenStarted) root.stop()
    }
  }

  function stop() {
    if (root.phase === "starting") { root.stopWhenStarted = true; return }
    if (root.phase !== "listening") return
    root.phase = "transcribing"
    stopProc.running = true
  }
  Process {
    id: stopProc
    command: ["voxtype", "record", "stop", "--wait", "--json", "--timeout", "90"]
    stdout: StdioCollector { id: stopOut }
    stderr: StdioCollector { id: stopErr }
    onExited: function(code) {
      if (root.phase !== "transcribing") return
      var result = root.parseOutcome(stopOut.text)
      if (result && result.status === "ok" && String(result.text || "").trim()) {
        root.finish()
        root.transcribed(String(result.text).trim())
        return
      }
      if (code === 0 || code === 3) { fallbackRead.running = true; return }
      root.finish()
      root.failed(code === 4 ? "Transcription timed out" : (result && result.message) || String(stopErr.text || "").trim().split("\n").pop() || ("voxtype record stop exited " + code))
    }
  }
  // The daemon may have finished before we asked (auto-stop): the transcript
  // file is the source of truth then.
  Process {
    id: fallbackRead
    command: ["cat", root.transcriptPath]
    stdout: StdioCollector { id: fallbackOut }
    onExited: function(code) {
      if (root.phase !== "transcribing") return
      root.finish()
      var text = code === 0 ? String(fallbackOut.text || "").trim() : ""
      if (text) root.transcribed(text); else root.nothingHeard()
    }
  }
  function parseOutcome(raw) {
    var lines = String(raw || "").trim().split("\n")
    for (var i = lines.length - 1; i >= 0; i--) {
      var line = lines[i].trim()
      if (line.charAt(0) !== "{") continue
      try { return JSON.parse(line) } catch (e) { }
    }
    return null
  }

  function cancel() {
    if (root.phase === "starting") { root.cancelWhenStarted = true; return }
    if (root.phase === "idle") return
    Quickshell.execDetached(["voxtype", "record", "cancel"])
    root.finish()
  }

  function finish() {
    root.phase = "idle"
    root.level = 0
    root.peak = 0
    root.vad = false
    Quickshell.execDetached(["rm", "-f", root.transcriptPath])
  }

  // ---------------------------------------------------------------- levels
  // voxtype's audio bridge prints one JSON frame per 10 ms while the daemon
  // records: {"peak":0.42,"rms":0.18,"vad":1,"ts_ms":…}. Only alive while listening.
  Process {
    id: bridge
    command: ["sh", "-c", "RUST_LOG=error exec voxtype-audio-bridge"]
    running: root.phase === "listening"
    stdout: SplitParser {
      onRead: function(line) {
        var frame = null
        try { frame = JSON.parse(String(line).trim()) } catch (e) { return }
        if (!frame || typeof frame.peak !== "number") return
        var loud = Math.min(1, frame.peak * 2.5)
        root.peak = loud
        root.vad = !!frame.vad
        root.level = Math.max(loud, root.level * 0.82)
        var next = root.history
        next.push(loud)
        if (next.length > 128) next.splice(0, next.length - 128)
        root.history = next
      }
    }
  }

  Component.onCompleted: root.refresh()
}
