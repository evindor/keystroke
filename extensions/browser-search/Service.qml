import QtQuick
import Quickshell
import Quickshell.Io
import "core/Browser.js" as Browser

QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: ""
  property var host: null
  readonly property string key: extension && extension.id ? String(extension.id) : "browser-search"
  readonly property string helper: decodeURIComponent(String(Qt.resolvedUrl("bin/search.py")).replace(/^file:\/\//, ""))
  property var cache: ({})
  property string inflight: ""
  property bool superseded: false
  property string output: ""
  property bool outputDone: false
  property int exitCode: -1
  property string failure: ""

  readonly property var provider: ({
    apiVersion: 1, name: "Browser search", icon: Browser.ICON, color: "#61afef",
    description: "Search your default browser's history and bookmarks",
    settings: Browser.SETTINGS,
    query: function(ctx) { return root.query(ctx) },
    opened: function() { root.cache = ({}); root.cancel() }
  })

  function cancel() {
    if (worker.running && !root.superseded) { root.superseded = true; worker.signal(15) }
  }

  function query(ctx) {
    root.host = ctx.host || root.host
    var req = Browser.request(ctx, root.key)
    if (!req.allowed || (!req.history && !req.bookmarks) || req.query.length < 2) {
      root.cancel()
      if (!req.allowed || !req.explicit) return []
      return [!req.history && !req.bookmarks
        ? Browser.status("History and bookmark search are off", "Enable a source in Browser search settings")
        : Browser.status("Type a page title or URL", "At least two characters")]
    }
    var k = Browser.cacheKey(req), hit = root.cache[k]
    if (hit !== undefined) { if (root.inflight !== k) root.cancel(); return Browser.rows(hit, req) }
    if (worker.running) { if (root.inflight !== k) root.cancel() }
    else {
      root.inflight = k
      root.superseded = false
      root.output = ""
      root.outputDone = false
      root.exitCode = -1
      root.failure = ""
      worker.command = Browser.argv(root.helper, req)
      worker.running = true
      watchdog.restart()
    }
    if (ctx.pending) ctx.pending()
    return []
  }

  // The output and the exit code arrive in either order; the run is judged once both are in.
  readonly property Process worker: Process {
    stdout: StdioCollector { onStreamFinished: { root.output = text; root.outputDone = true; root.settle() } }
    onExited: function(code) { root.exitCode = code; root.settle() }
  }
  function settle() {
    if (!root.outputDone || root.exitCode < 0) return
    watchdog.stop()
    if (!root.superseded) {
      var result = root.failure || root.exitCode !== 0
        ? { browser: "", results: [], error: root.failure || "Browser search helper failed; check that Python 3 is installed" }
        : Browser.parse(root.output)
      var next = ({})
      for (var k in root.cache) next[k] = root.cache[k]
      next[root.inflight] = result
      var keys = Object.keys(next)
      while (keys.length > 16) delete next[keys.shift()]
      root.cache = next
    }
    root.inflight = ""
    root.superseded = false
    if (root.host) root.host.requery({ catalog: false, provider: root.key })
  }
  readonly property Timer watchdog: Timer {
    interval: 5000
    onTriggered: {
      root.failure = "Browser search timed out; try again after reopening the palette"
      if (worker.running) worker.signal(15)
    }
  }
  Component.onDestruction: { if (worker.running) worker.signal(15) }
}
