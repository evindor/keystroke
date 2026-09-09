import QtQuick
import Quickshell
import Quickshell.Io
import "../core/Match.js" as Match
import "../core/Hotkeys.js" as Hotkeys

// Omarchy's keybindings at the root of the palette: type what you want to
// do ("flcrn"), see "Full screen" with Super + F next to it, press Enter or,
// next time, the keys. The list and the dispatch both come from
// omarchy-menu-keybindings, the script behind Super+K, so the rows are the
// same binds that menu shows and running one does what pressing it does.
Item {
  id: root
  property var host: null
  property var binds: []
  property bool loaded: false
  property real loadedAt: 0
  readonly property string omarchyPath: Quickshell.env("OMARCHY_PATH")

  readonly property var provider: ({
    apiVersion: 1,
    id: "hotkeys",
    name: "Hotkeys",
    icon: "",
    color: "#c4a7e7",
    description: "Omarchy's keybindings, searchable by what they do, with the keys shown next to each",
    settings: [
      { key: "limit", type: "number", label: "Results at the root", "default": 10, min: 1, max: 50, integer: true,
        description: "The Hotkeys screen lists every bind; this caps what mixes into the global search." },
      { key: "keyboardOnly", type: "boolean", label: "Show keyboard-only binds", "default": true,
        description: "Binds Omarchy cannot run from a menu (Lua closures such as Close window) still appear, greyed, so the keys can be learned." }
    ],
    query: function(ctx) { return root.query(ctx) },
    catalog: function(ctx) { return root.catalog(ctx) },
    activate: function(row, ctx) { return root.activate(row) },
    opened: function() { root.refresh(false) }
  })

  // The script keeps its own cache keyed on `hyprctl binds`, so a reload is
  // a hash and a cat; still, once a summon is often enough.
  function refresh(force) {
    if (loader.running) return
    if (!force && root.loaded && Date.now() - root.loadedAt < 30000) return
    loader.command = Hotkeys.loadArgv(root.omarchyPath)
    loader.running = true
  }

  Process {
    id: loader
    stdout: StdioCollector {
      onStreamFinished: {
        var parsed = Hotkeys.parse(text)
        // A failed hyprctl prints nothing: keep the previous list rather than an empty screen.
        if (parsed.length || !root.loaded) root.binds = parsed
      }
    }
    onExited: {
      root.loaded = true
      root.loadedAt = Date.now()
      if (root.host) root.host.requery()
    }
  }

  function activate(row) {
    if (!row.action || row.action.type !== "hotkey") return row.action
    return { type: "exec", argv: Hotkeys.dispatchArgv(root.omarchyPath, row.action.dispatcher, row.action.arg) }
  }

  function catalog(ctx) {
    var rows = []
    for (var i = 0; i < root.binds.length; i++) {
      var bind = root.binds[i]
      if (!Hotkeys.runnable(bind)) continue
      var row = Hotkeys.row(bind, 1)
      row.keywords = Hotkeys.keywords(bind)
      row.descriptionKey = bind.dispatcher + "\u001f" + bind.arg
      rows.push(row)
    }
    return rows
  }

  function query(ctx) {
    if (ctx.scope && ctx.scope !== "hotkeys") return []
    var rows = []
    if (!ctx.scope) {
      if (!ctx.query) return [Hotkeys.navRow(18)]
      var s = Match.match(ctx.query, "Hotkeys", "keybindings keys shortcuts bindings hyprland")
      if (s) rows.push(Hotkeys.navRow(s))
    }
    if (!root.loaded) { root.refresh(true); ctx.pending(); return rows }
    return rows.concat(Hotkeys.rows(ctx.query, root.binds, ctx.settings, !!ctx.scope))
  }
}
