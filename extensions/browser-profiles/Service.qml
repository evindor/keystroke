import QtQuick
import Quickshell
import Quickshell.Io
import "core/Profiles.js" as Profiles

// Browser profiles: open a new window in any profile of any installed
// Chromium- or Firefox-family browser. The profile list is read once per
// palette open by bin/profiles.py and kept in memory; queries only filter it.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: ""
  property var host: null
  readonly property string key: extension && extension.id ? String(extension.id) : "browser-profiles"
  readonly property string helper: decodeURIComponent(String(Qt.resolvedUrl("bin/profiles.py")).replace(/^file:\/\//, ""))
  property var data: null            // last parsed scan; kept while a rescan runs
  property string output: ""
  property bool outputDone: false
  property int exitCode: -1
  property string failure: ""

  readonly property var provider: ({
    apiVersion: 1, name: "Browser profiles", icon: Profiles.ICON, color: "#56b6c2",
    description: "Open a new window in a browser profile",
    settings: Profiles.SETTINGS,
    query: function(ctx) { return root.query(ctx) },
    // The list barely changes between opens: rescan at most once a minute.
    opened: function() { if (!root.data || Date.now() - root.scannedAt > 60000) root.scan() }
  })

  property real scannedAt: 0
  function scan() {
    if (worker.running) return
    root.scannedAt = Date.now()
    root.output = ""
    root.outputDone = false
    root.exitCode = -1
    root.failure = ""
    worker.command = Profiles.argv(root.helper)
    worker.running = true
    watchdog.restart()
  }

  function iconFor(name) {
    var lib = root.host && root.host.appLibrary
    if (!name || !lib || typeof lib.iconSource !== "function") return ""
    try { return lib.iconSource(name) } catch (_) { return "" }
  }

  function query(ctx) {
    root.host = ctx.host || root.host
    var req = Profiles.request(ctx, root.key)
    if (!req.allowed) return []
    if (!root.data) {
      if (!worker.running) root.scan()
      if (ctx.pending) ctx.pending()
      return []
    }
    return Profiles.rows(root.data, req, root.iconFor)
  }

  // The output and the exit code arrive in either order; the scan is judged once both are in.
  readonly property Process worker: Process {
    stdout: StdioCollector { onStreamFinished: { root.output = text; root.outputDone = true; root.settle() } }
    onExited: function(code) { root.exitCode = code; root.settle() }
  }
  function settle() {
    if (!root.outputDone || root.exitCode < 0) return
    watchdog.stop()
    var next = root.failure || root.exitCode !== 0
      ? { browsers: [], error: root.failure || "Browser profile scan failed; check that Python 3 is installed" }
      : Profiles.parse(root.output)
    root.data = Profiles.merge(root.data, next)
    if (root.host && root.host.opened) root.host.requery({ catalog: false, provider: root.key })
  }
  readonly property Timer watchdog: Timer {
    interval: 5000
    onTriggered: {
      root.failure = "Browser profile scan timed out; reopen the palette to retry"
      if (worker.running) worker.signal(15)
    }
  }
  Component.onDestruction: { if (worker.running) worker.signal(15) }
}
