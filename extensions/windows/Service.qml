import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "core/Windows.js" as Windows

// Windows: switch to any open Hyprland window. The client list is read once
// per palette open with `hyprctl clients -j` and kept in memory; queries only
// filter it.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: ""
  property var host: null
  readonly property string key: extension && extension.id ? String(extension.id) : "windows"
  property var list: null            // last parsed client list; kept while a rescan runs
  property string output: ""
  property bool outputDone: false
  property int exitCode: -1
  property string pending: ""        // address to focus once the palette has let go of the keyboard

  readonly property var provider: ({
    apiVersion: 1, name: "Windows", icon: Windows.ICON, color: "#98c379",
    description: "Switch to any open window",
    settings: Windows.SETTINGS,
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) },
    opened: function() { root.scan() }
  })

  function scan() {
    if (worker.running) return
    root.output = ""
    root.outputDone = false
    root.exitCode = -1
    worker.running = true
    watchdog.restart()
  }

  function iconFor(cls) {
    var lib = root.host && root.host.appLibrary
    if (!cls || !lib || typeof lib.iconSource !== "function") return ""
    var entry = null
    try { entry = DesktopEntries.heuristicLookup(cls) } catch (_) { entry = null }
    try { return String(lib.iconSource(entry && entry.icon ? entry.icon : cls) || "") } catch (_) { return "" }
  }

  function query(ctx) {
    root.host = ctx.host || root.host
    var req = Windows.request(ctx, root.key)
    if (!req.allowed) return []
    if (!root.list) {
      if (!worker.running) root.scan()
      if (ctx.pending) ctx.pending()
      return []
    }
    return Windows.rows(Windows.filter(root.list, req), req, root.iconFor)
  }

  // The palette holds an exclusive keyboard grab; focusing another window
  // before it is gone loses the race when the compositor restores focus to
  // the window the palette came from. Close first, then focus.
  function activate(row, ctx) {
    var effect = row.action
    if (!effect || effect.type !== "window-focus") return effect
    root.pending = Windows.address(effect.address)
    focusLater.restart()
    return { type: "close" }
  }

  readonly property Timer focusLater: Timer {
    interval: 80
    onTriggered: {
      var command = Windows.focusCommand(root.pending, Hyprland.usingLua === true)
      root.pending = ""
      if (command) Hyprland.dispatch(command)
    }
  }

  // The workspace you are on, so an empty one does not hide the window you used last.
  function here() {
    var ws = Hyprland.focusedWorkspace
    return ws && typeof ws.id === "number" ? ws.id : null
  }

  readonly property Process worker: Process {
    command: ["hyprctl", "clients", "-j"]
    stdout: StdioCollector { onStreamFinished: { root.output = text; root.outputDone = true; root.settle() } }
    onExited: function(code) { root.exitCode = code; root.settle() }
  }
  function settle() {
    if (!root.outputDone || root.exitCode < 0) return
    watchdog.stop()
    var parsed = null
    if (root.exitCode === 0) { try { parsed = JSON.parse(root.output) } catch (_) { parsed = null } }
    if (Array.isArray(parsed)) root.list = Windows.windows(parsed, root.here())
    else if (!root.list) root.list = []
    if (root.host && root.host.opened) root.host.requery({ catalog: false, provider: root.key })
  }
  readonly property Timer watchdog: Timer {
    interval: 3000
    onTriggered: if (worker.running) worker.signal(15)
  }
  Component.onDestruction: { if (worker.running) worker.signal(15) }
}
