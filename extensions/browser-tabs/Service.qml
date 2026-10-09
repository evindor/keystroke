import QtQuick
import Quickshell
import Quickshell.Io
import "core/Tabs.js" as Tabs

// Browser tabs: switch to an open browser tab. Tabs are read through AT-SPI
// by the vendored Everything backend (everything/, MIT), which runs as one
// JSON-lines helper while the palette is open and for a short while after,
// rescanning every two seconds because browsers publish their tab strips late.
// Activation runs the tab's native accessibility action, then focuses its
// exact Hyprland window.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var host: null
  readonly property string key: extension && extension.id ? String(extension.id) : "browser-tabs"
  readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("bin/tabs-helper.py")).replace(/^file:\/\//, ""))
  property var list: []
  property bool ready: false
  property bool scanning: false
  property bool scanned: false
  property bool unavailable: false
  property string scanId: ""
  property int serial: 0
  property var queue: []
  property var pendingTab: null      // tab to activate once the palette has let go of the keyboard
  property int activations: 0
  property bool stopping: false

  readonly property var provider: ({
    apiVersion: 1, name: "Browser tabs", icon: Tabs.ICON, color: "#61afef",
    description: "Switch to an open browser tab",
    settings: Tabs.SETTINGS,
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) },
    opened: function() { idle.stop(); root.scan() }
  })

  function nextId(prefix) { root.serial += 1; return prefix + "-" + root.serial }

  function send(request) {
    if (!helper.running) {
      root.stopping = false
      root.ready = false
      helper.command = Tabs.argv(root.helperPath)
      helper.running = true
    }
    if (!root.ready) { root.queue = root.queue.concat([request]); return }
    helper.write(JSON.stringify(request) + "\n")
  }

  function scan() {
    if (root.scanning && root.scanId) return
    root.scanId = root.nextId("scan")
    root.scanning = true
    root.send(Tabs.scanRequest(root.scanId))
  }

  function iconFor(name) {
    var lib = root.host && root.host.appLibrary
    if (!name || !lib || typeof lib.iconSource !== "function") return ""
    try { return String(lib.iconSource(String(name).toLowerCase()) || "") } catch (_) { return "" }
  }

  function query(ctx) {
    root.host = ctx.host || root.host
    var req = Tabs.request(ctx, root.key)
    if (!req.allowed) return []
    if (!root.scanned && ctx.pending) ctx.pending()
    return Tabs.rows(Tabs.filter(root.list, req), req, root, root.iconFor)
  }

  // The palette holds an exclusive keyboard grab; focusing a browser before
  // it is gone loses the race when the compositor restores focus. Close
  // first, then activate.
  function activate(row, ctx) {
    var effect = row.action
    if (!effect || effect.type !== "tab-focus") return effect
    var tab = null
    for (var i = 0; i < root.list.length; i++) if (root.list[i].id === effect.tab) tab = root.list[i]
    if (!tab) return { type: "close" }
    root.pendingTab = tab
    activateLater.restart()
    return { type: "close" }
  }

  function notify(text) {
    if (!root.omarchyPath) return
    Quickshell.execDetached([root.omarchyPath + "/bin/omarchy-notification-send", "-g", Tabs.ICON, "Browser tabs", text])
  }

  function handle(line) {
    var m = Tabs.message(line, root.scanId)
    if (m.type === "ready") {
      root.ready = true
      root.unavailable = !m.atspi
      var queued = root.queue
      root.queue = []
      for (var i = 0; i < queued.length; i++) helper.write(JSON.stringify(queued[i]) + "\n")
    } else if (m.type === "partial" || m.type === "full") {
      if (m.type === "full") { root.scanning = false; root.scanned = true; root.scanId = "" }
      var changed = Tabs.signature(m.tabs) !== Tabs.signature(root.list)
      root.list = m.tabs
      if ((changed || m.type === "full") && root.host && root.host.opened) root.host.requery({ catalog: false, provider: root.key })
    } else if (m.type === "activation") {
      root.activations = Math.max(0, root.activations - 1)
      if (!m.ok) root.notify(m.message || "That tab closed before it could be focused")
    }
  }

  readonly property Timer activateLater: Timer {
    interval: 80
    onTriggered: {
      var tab = root.pendingTab
      root.pendingTab = null
      if (!tab) return
      root.activations += 1
      root.send(Tabs.activateRequest(root.nextId("activate"), tab))
    }
  }

  // Rescan while the palette is open; once it closes, keep the helper for
  // thirty seconds (a quick reopen finds tabs at once), then stop it.
  readonly property Timer poll: Timer {
    interval: 2000
    repeat: true
    running: helper.running && !root.stopping
    onTriggered: {
      if (root.host && root.host.opened) { idle.stop(); if (!root.scanning) root.scan() }
      else if (!idle.running) idle.restart()
    }
  }
  readonly property Timer idle: Timer {
    interval: 30000
    onTriggered: if (root.activations === 0 && !(root.host && root.host.opened)) root.stop()
  }
  readonly property Timer forceStop: Timer {
    interval: 1500
    onTriggered: if (helper.running) helper.signal(15)
  }

  function stop() {
    if (!helper.running) return
    root.stopping = true
    if (root.ready) { helper.write(JSON.stringify(Tabs.shutdownRequest(root.nextId("shutdown"))) + "\n"); forceStop.restart() }
    else helper.signal(15)
  }

  readonly property Process helper: Process {
    stdinEnabled: true
    stdout: SplitParser { onRead: function(line) { root.handle(line) } }
    onExited: function(code) {
      forceStop.stop()
      root.ready = false
      root.scanning = false
      root.scanId = ""
      root.queue = []
      if (root.activations > 0) root.notify("The tab helper stopped before it could focus the tab")
      root.activations = 0
      if (!root.stopping) { root.scanned = true; if (root.host && root.host.opened) root.host.requery({ catalog: false, provider: root.key }) }
      root.stopping = false
    }
  }

  Component.onDestruction: {
    if (helper.running) {
      if (root.ready) helper.write(JSON.stringify(Tabs.shutdownRequest("destruction")) + "\n")
      helper.signal(15)
    }
  }
}
