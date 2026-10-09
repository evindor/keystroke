import QtQuick
import Quickshell
import Quickshell.Io
import "core/Herdr.js" as Herdr

// Herdr: jump to an agent, workspace, tab or pane of any running Herdr
// session. bin/herdr.py reads every session's snapshot once per palette open;
// queries only filter it. Activation runs the same helper to focus the target
// and raise the terminal that shows it.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: ""
  property var host: null
  readonly property string key: extension && extension.id ? String(extension.id) : "herdr"
  readonly property string home: Quickshell.env("HOME")
  readonly property string helper: decodeURIComponent(String(Qt.resolvedUrl("bin/herdr.py")).replace(/^file:\/\//, ""))
  property var data: null            // last parsed scan; kept while a rescan runs
  property string output: ""
  property bool outputDone: false
  property int exitCode: -1
  property string failure: ""

  readonly property var provider: ({
    apiVersion: 1, name: "Herdr", icon: Herdr.ICON, color: "#c678dd",
    description: "Jump to a Herdr agent, workspace, tab or pane",
    settings: Herdr.SETTINGS,
    query: function(ctx) { return root.query(ctx) },
    opened: function() { root.scan() }
  })

  function scan() {
    if (worker.running) return
    root.output = ""
    root.outputDone = false
    root.exitCode = -1
    root.failure = ""
    worker.command = Herdr.argv(root.helper, ["list"])
    worker.running = true
    watchdog.restart()
  }

  function query(ctx) {
    root.host = ctx.host || root.host
    var req = Herdr.request(ctx, root.key)
    if (!req.allowed) return []
    if (!root.data) {
      if (!worker.running) root.scan()
      if (ctx.pending) ctx.pending()
      return []
    }
    return Herdr.rows(root.data, req, root.helper, root.home)
  }

  // The output and the exit code arrive in either order; the scan is judged once both are in.
  readonly property Process worker: Process {
    stdout: StdioCollector { onStreamFinished: { root.output = text; root.outputDone = true; root.settle() } }
    onExited: function(code) { root.exitCode = code; root.settle() }
  }
  function settle() {
    if (!root.outputDone || root.exitCode < 0) return
    watchdog.stop()
    root.data = root.failure || root.exitCode !== 0
      ? { sessions: [], error: root.failure || "Herdr helper failed; check that Python 3 is installed" }
      : Herdr.parse(root.output)
    if (root.host && root.host.opened) root.host.requery({ catalog: false, provider: root.key })
  }
  readonly property Timer watchdog: Timer {
    interval: 5000
    onTriggered: {
      root.failure = "Herdr did not answer in time; reopen the palette to retry"
      if (worker.running) worker.signal(15)
    }
  }
  Component.onDestruction: { if (worker.running) worker.signal(15) }
}
