import QtQuick
import Quickshell
import Quickshell.Io
import "core/Raycast.js" as Raycast

// Raycast store extensions. Off until the user turns it on. Search hits
// backend.raycast.com only after `ray` or this screen is open, and an
// extension's code runs only after they install it and open a command.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  readonly property string home: Quickshell.env("HOME")
  readonly property string xdg: Quickshell.env("XDG_DATA_HOME")
  readonly property string key: extension && extension.id ? String(extension.id) : "raycast"
  readonly property string extDir: Raycast.extensionsDir(home, xdg)
  readonly property string hostBin: (extension && extension.dir ? String(extension.dir) : "") + "/bin/host"
  readonly property string pasteBin: (extension && extension.dir ? String(extension.dir) : "") + "/bin/paste-after"

  property var ui: null
  property var installed: []
  property var storeHits: []
  property bool runtime: false
  property bool nodeOk: false
  property bool statusDone: false
  property bool searching: false
  property string searchError: ""
  property string banner: ""
  property var wanted: null
  property bool searchAgain: false
  property var launch: null
  property var screen: null
  property bool saw: false
  property var confirmReq: null
  property string searchBody: ""
  property string searchErr: ""
  property string statusBody: ""
  property string taskBody: ""
  property string taskErr: ""
  property string readBody: ""
  property int readId: -1
  property string copyText: ""
  property bool copyPaste: false
  property string runnerErr: ""

  readonly property var provider: ({
    apiVersion: 1,
    name: "Raycast",
    icon: Raycast.ICON,
    color: "#f36b4a",
    description: "Extensions from the Raycast store",
    view: view,
    settings: [],
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) }
  })
  readonly property Component view: Component { RaycastView { service: root } }

  readonly property Timer debounce: Timer { interval: 250; onTriggered: root.runSearch() }

  function query(ctx) {
    if (ctx && ctx.host) root.ui = ctx.host
    root.note(ctx)
    if ((root.searching || !root.statusDone) && ctx && ctx.pending) ctx.pending()
    var command = ctx && ctx.command
    return Raycast.rows({
      scope: ctx ? ctx.scope : "",
      query: ctx ? ctx.query : "",
      commandRest: command ? command.rest : "",
      inCommand: !!command,
      installed: root.installed,
      store: root.storeHits,
      searching: root.searching,
      searchError: root.searchError,
      runtime: root.runtime,
      nodeOk: root.nodeOk,
      ready: root.statusDone
    })
  }

  function activate(row, ctx) {
    if (ctx && ctx.host) root.ui = ctx.host
    var action = ctx && ctx.alternate && row.altAction ? row.altAction : row.action
    if (!action) return { type: "noop" }
    if (action.type === "raycast-run") {
      root.launch = {
        dir: action.dir,
        command: action.command,
        mode: action.mode || "view",
        title: action.title || row.title
      }
      root.screen = null
      root.saw = false
      root.banner = ""
      root.confirmReq = null
      return { type: "provider-view", provider: root.key }
    }
    if (action.type === "raycast-install") {
      root.beginTask(["install", action.handle, action.name, root.extDir], "Installing " + action.name + "…")
      return { type: "noop" }
    }
    if (action.type === "raycast-remove") {
      root.beginTask(["remove", action.id, root.extDir], "Removing " + (row.title || "extension") + "…")
      return { type: "noop" }
    }
    return action
  }

  function note(ctx) {
    var scoped = ctx && (ctx.scope === root.key || String(ctx.scope || "").indexOf(root.key + "/") === 0)
    var prompted = scoped || !!(ctx && ctx.command)
    if (!prompted || !root.runtime || !root.nodeOk) return
    var text = scoped ? String(ctx.query || "").trim() : String(ctx.command && ctx.command.rest || "").trim()
    if (text === root.wanted) return
    root.wanted = text
    root.storeHits = []
    root.searchError = ""
    root.debounce.restart()
  }

  function requery() {
    var ui = root.ui
    if (ui && ui.opened && ui.requery) ui.requery()
  }

  function refreshStatus() {
    if (!root.hostBin || statusProc.running) return
    root.statusBody = ""
    statusProc.command = [root.hostBin, "status", root.extDir]
    statusProc.running = true
  }

  function applyStatus() {
    var parsed = root.parse(root.statusBody)
    root.statusDone = true
    if (!parsed || parsed.ok === false) {
      root.nodeOk = false
      root.runtime = false
      root.banner = (parsed && parsed.error) || "Could not start the Raycast host"
      return
    }
    root.nodeOk = true
    root.runtime = !!parsed.runtime
    root.installed = parsed.extensions || []
  }

  function runSearch() {
    if (!root.runtime || !root.nodeOk) return
    if (searchProc.running) { root.searchAgain = true; return }
    root.searching = true
    root.searchBody = ""
    root.searchErr = ""
    searchProc.q = root.wanted || ""
    searchProc.command = [root.hostBin, "search", searchProc.q, root.extDir]
    searchProc.running = true
  }

  function applySearch(code) {
    if (searchProc.q !== (root.wanted || "")) return
    var parsed = root.parse(root.searchBody)
    if (!parsed || parsed.ok === false) {
      root.storeHits = []
      root.searchError = (parsed && parsed.error) || String(root.searchErr || "").trim() || ("Store search failed (" + code + ")")
      return
    }
    root.searchError = ""
    root.storeHits = parsed.extensions || []
  }

  function beginTask(args, label) {
    if (taskProc.running) { root.banner = "Wait for the current install to finish"; return }
    root.banner = label
    root.taskBody = ""
    root.taskErr = ""
    var command = [root.hostBin]
    for (var i = 0; i < args.length; i++) command.push(args[i])
    taskProc.command = command
    taskProc.running = true
  }

  function applyTask(code) {
    var parsed = root.parse(root.taskBody)
    if (!parsed || parsed.ok === false) {
      root.banner = (parsed && parsed.error) || String(root.taskErr || "").trim() || ("Failed (" + code + ")")
      return
    }
    root.banner = parsed.title ? ("Installed " + parsed.title) : "Updated"
    root.wanted = null
    root.refreshStatus()
  }

  function parse(text) {
    try { return JSON.parse(String(text || "")) } catch (e) { return null }
  }

  function start() {
    root.stop()
    if (!root.launch || !root.launch.dir || !root.launch.command) {
      root.banner = "That command is not installed"
      return
    }
    root.screen = null
    root.saw = false
    root.runnerErr = ""
    root.confirmReq = null
    runner.command = [root.hostBin, "run", root.launch.dir, root.launch.command]
    runner.stdinEnabled = true
    runner.running = true
  }

  function stop() {
    if (runner.running) runner.running = false
  }

  function send(msg) {
    if (!runner.running) return
    runner.write(JSON.stringify(msg) + "\n")
  }

  function onHostLine(line) {
    var msg = root.parse(line)
    if (!msg || !msg.type) return
    if (msg.type === "render") { root.screen = msg.view; root.saw = true; return }
    if (msg.type === "toast" || msg.type === "hud") {
      root.banner = [msg.title, msg.message].filter(function(part) { return part }).join(" — ")
      if (msg.type === "hud" && root.launch && root.launch.mode === "no-view") root.leave(root.banner)
      return
    }
    if (msg.type === "error") { root.banner = msg.message || "Error"; return }
    if (msg.type === "open") { root.openTarget(msg.target); return }
    if (msg.type === "copy") { root.copy(msg.text, false); return }
    if (msg.type === "paste") { root.copy(msg.text, true); return }
    if (msg.type === "close") { if (root.ui) root.ui.cancel(); return }
    if (msg.type === "pop_to_root") { root.leave(root.banner); return }
    if (msg.type === "exit") {
      if (root.launch && root.launch.mode === "no-view") root.leave(root.banner)
      else if (!root.saw) root.banner = root.banner || "The command ended"
      return
    }
    if (msg.type === "request") root.answer(msg)
  }

  function leave(message) {
    if (!root.ui) return
    if (message) root.ui.statusMessage = message
    root.ui.goBack()
  }

  function openTarget(target) {
    var value = String(target || "")
    if (!value) return
    Quickshell.execDetached(["xdg-open", value])
    root.banner = "Opened"
  }

  function copy(text, paste) {
    root.copyText = text == null ? "" : String(text)
    root.copyPaste = !!paste
    if (copyProc.running) return
    copyProc.stdinEnabled = true
    copyProc.running = true
  }

  function answer(msg) {
    if (msg.method === "clipboard.readText") {
      root.readId = msg.id
      root.readBody = ""
      if (!readProc.running) readProc.running = true
      return
    }
    if (msg.method === "confirm") {
      var params = msg.params || ({})
      root.confirmReq = {
        id: msg.id,
        title: params.title || "Confirm",
        message: params.message || "",
        ok: params.primaryAction || "OK",
        cancel: params.dismissAction || "Cancel"
      }
      return
    }
    root.send({ type: "reply", id: msg.id, result: null })
  }

  function decide(confirmed) {
    var req = root.confirmReq
    root.confirmReq = null
    if (req) root.send({ type: "reply", id: req.id, result: !!confirmed })
  }

  function dismiss() { root.stop() }

  Process {
    id: statusProc
    stdout: StdioCollector { onStreamFinished: root.statusBody = text }
    onExited: function(code) {
      if (code !== 0 && !root.statusBody) root.statusBody = ""
      root.applyStatus()
      root.requery()
    }
  }
  Process {
    id: searchProc
    property string q: ""
    stdout: StdioCollector { onStreamFinished: root.searchBody = text }
    stderr: StdioCollector { onStreamFinished: root.searchErr = text }
    onExited: function(code) {
      root.searching = false
      root.applySearch(code)
      var again = root.searchAgain
      root.searchAgain = false
      root.requery()
      if (again) root.runSearch()
    }
  }
  Process {
    id: taskProc
    stdout: StdioCollector { onStreamFinished: root.taskBody = text }
    stderr: StdioCollector { onStreamFinished: root.taskErr = text }
    onExited: function(code) { root.applyTask(code); root.requery() }
  }
  Process {
    id: runner
    stdout: SplitParser { onRead: function(line) { root.onHostLine(line) } }
    stderr: SplitParser { onRead: function(line) { root.runnerErr += line + "\n" } }
    onExited: function(code) {
      if (!root.saw && code !== 0) root.banner = String(root.runnerErr || "").trim() || ("Extension exited (" + code + ")")
    }
  }
  Process {
    id: copyProc
    command: ["wl-copy"]
    onStarted: { write(root.copyText); root.copyText = ""; stdinEnabled = false }
    onExited: function(code) {
      if (code !== 0) { root.banner = "Could not copy to the clipboard"; return }
      if (root.copyPaste) {
        root.banner = "Pasting…"
        Quickshell.execDetached([root.pasteBin])
        if (root.ui) root.ui.cancel()
      } else root.banner = "Copied"
    }
  }
  Process {
    id: readProc
    command: ["wl-paste", "-n"]
    stdout: StdioCollector { onStreamFinished: root.readBody = text }
    onExited: function(code) {
      root.send({ type: "reply", id: root.readId, result: code === 0 ? root.readBody : "" })
      root.readBody = ""
    }
  }

  onExtensionChanged: if (root.extension && root.extension.dir) root.refreshStatus()
  Component.onDestruction: root.stop()
}
