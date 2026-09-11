import QtQuick
import Quickshell
import Quickshell.Io
import "core/Parser.js" as Parser

// Keyboard Cleaner: block every keyboard and pointer for a while so they
// can be wiped without typing anything.
//
// Keystroke creates this object when the extension is turned on, injects
// `shell`, `extension` and `omarchyPath`, reads `provider`, and destroys it
// when the extension is turned off. A block runs bin/keyboard-cleaner,
// which asks Hyprland to switch each device off (`hl.device({ enabled =
// false })`, the call Omarchy's own touchpad toggle makes) and back on when
// the time is up, on a signal, or on any error. No device files, no group
// membership, and a Hyprland reload restores everything on its own.
//
// The helper is a child of this object: its first stdout line says how many
// devices went quiet (BlockView shows it), and turning the extension off
// while a block runs sends SIGTERM, which restores input at once.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var host: null            // the palette, captured from ctx on each query and activation
  property var settings: ({ defaultSeconds: 30, blockPointer: true })
  readonly property string key: extension && extension.id ? String(extension.id) : "keyboard-cleaner"
  readonly property string helper: String(Qt.resolvedUrl("bin/keyboard-cleaner")).replace(/^file:\/\//, "")

  // The block in progress, read by BlockView through `service`.
  property bool active: false        // the helper is running
  property double startedAt: 0
  property double until: 0           // when input comes back, ms since the epoch
  property int seconds: 0
  property string label: ""
  property int blocked: -1           // devices the helper switched off; -1 until it reports
  property string error: ""
  signal changed()

  readonly property var provider: ({
    apiVersion: 1,
    name: Parser.NAME,
    icon: Parser.ICON,
    color: Parser.COLOR,
    description: "Block every keyboard and pointer for a moment so you can wipe them",
    prefix: "wipe",
    patterns: Parser.PATTERNS,
    settings: [
      { key: "defaultSeconds", type: "number", label: "Default duration (seconds)", "default": 30, min: 1, max: 300, integer: true,
        description: "Used by `wipe` when no duration is typed; 5 minutes at most" },
      { key: "blockPointer", type: "boolean", label: "Also block mice and touchpads", "default": true,
        description: "Off keeps the pointer working while the keyboard is blocked" }
    ],
    view: root.view,
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) }
  })

  readonly property Component view: Component { BlockView { service: root } }

  function attach(ctx) {
    if (ctx && ctx.host) root.host = ctx.host
    if (ctx && ctx.settings) root.settings = ctx.settings
  }

  function query(ctx) {
    root.attach(ctx)
    var scoped = ctx.scope === root.key
    if (ctx.scope && !scoped) return []
    var matched = !!(ctx.patterns && ctx.patterns.matched && ctx.patterns.matched.length)
    var state = { key: root.key, blockPointer: root.settings.blockPointer !== false }
    // The host hands over the text after the declared prefix; the verbs in Parser.js still work without it.
    return Parser.rows(ctx.query, ctx.command ? ctx.command.rest : null, matched, root.settings, scoped, state)
  }

  function activate(row, ctx) {
    root.attach(ctx)
    var effect = ctx.alternate && row.altAction ? row.altAction : row.action
    if (!effect || effect.type !== "block") return effect
    // One block at a time: a second request while one runs shows the running one.
    if (!helperProcess.running) {
      root.seconds = Parser.clampSeconds(effect.seconds)
      root.label = String(effect.label || "")
      root.startedAt = Date.now()
      root.until = root.startedAt + (root.seconds + 0.5) * 1000   // the helper waits half a second before switching off
      root.blocked = -1
      root.error = ""
      root.active = true
      helperProcess.command = Parser.blockArgv(root.helper, root.seconds, root.settings.blockPointer !== false)
      helperProcess.running = true
    }
    root.changed()
    return { type: "provider-view", provider: root.key }
  }

  readonly property Process helperProcess: Process {
    stdout: SplitParser { onRead: function(line) { root.report(line) } }
    stderr: SplitParser { onRead: function(line) { console.log("keyboard-cleaner: " + line) } }
    onExited: function(code) { root.finished(code) }
  }

  function report(line) {
    var info = Parser.parseReport(line)
    if (!info) return
    if (info.error) root.error = info.error
    if (info.blocked !== undefined) {
      root.blocked = info.blocked
      if (info.until) root.until = info.until * 1000
    }
    root.changed()
  }

  function finished(code) {
    root.active = false
    if (code !== 0 && !root.error) root.error = "The helper exited with code " + code
    root.changed()
  }

  Component.onDestruction: { if (helperProcess.running) helperProcess.signal(15) }
}
