import QtQuick
import Quickshell
import Quickshell.Io
import "../core/Match.js" as Match

// Reads the history Omarchy's clipboard overlay already maintains. No second
// watcher, no duplicate capture. Never included in the global search.
Item {
  id: root
  property var host: null
  property var entries: []
  readonly property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  readonly property string historyPath: Quickshell.env("HOME") + "/.local/state/omarchy/clipboard-history.json"

  readonly property var provider: ({
    apiVersion: 1,
    id: "clipboard",
    name: "Clipboard History",
    icon: "󰅌",
    color: "#8dbaec",
    description: "Uses Omarchy's existing history",
    settings: [{ key: "limit", type: "number", label: "Maximum entries", "default": 100, min: 1, max: 300, integer: true }],
    query: function(ctx) { return root.query(ctx) }
  })

  FileView {
    id: historyFile
    path: root.historyPath
    watchChanges: true
    printErrors: false
    onLoaded: root.parse(text())
    onLoadFailed: root.entries = []
    onFileChanged: reload()
  }

  function parse(raw) {
    var out = []
    try {
      var parsed = JSON.parse(String(raw || "[]"))
      for (var i = 0; Array.isArray(parsed) && i < parsed.length; i++) {
        var v = parsed[i]
        if (typeof v === "string") { if (v.trim()) out.push({ type: "text", text: v, search: v.slice(0, 4000) }); continue }
        if (!v || typeof v !== "object") continue
        var type = String(v.type || v.kind || "")
        if (type === "text" && String(v.text || "").trim()) out.push({ type: "text", text: String(v.text), search: String(v.text).slice(0, 4000) })
        else if (type === "image" && v.path) out.push({ type: "image", path: String(v.path), mime: String(v.mime || "image/png"), capturedAt: v.capturedAt === undefined ? "" : String(v.capturedAt) })
      }
    } catch (e) { out = [] }
    root.entries = out
    if (root.host) root.host.requery()
  }

  function query(ctx) {
    if (ctx.scope && ctx.scope !== "clipboard") return []
    if (!ctx.scope) {
      var s = ctx.query ? Match.match(ctx.query, "Clipboard History", "paste copied text images") : 26
      return s ? [{ id: "clipboard", title: "Clipboard History", subtitle: "Text & images, ready to use again", icon: "󰅌", section: "Clipboard",
                    verb: "Open", tier: "item", score: s, order: 2, action: { type: "navigate", scope: "clipboard", title: "Clipboard" } }] : []
    }
    var rows = []
    var limit = ctx.settings.limit
    for (var i = 0; i < root.entries.length && i < limit; i++) {
      var e = root.entries[i]
      var image = e.type === "image"
      var text = image ? "" : e.text
      var title = image ? "Image · " + (e.capturedAt || "Clipboard") : text.replace(/\s+/g, " ").slice(0, 120)
      // The title (first line) is fuzzy; the body is prose, matched by word.
      var score = Match.match(ctx.query, title, "", "", image ? "" : e.search)
      if (!score) continue
      rows.push({
        id: Qt.md5(image ? e.path : text), title: title, subtitle: image ? "Image" : text.length + " characters", icon: "󰅌",
        section: "Clipboard", verb: "Copy", tier: "item", score: score, order: i,
        action: image ? { type: "exec", argv: [root.omarchyPath + "/bin/omarchy-clipboard-paste-file", "--copy-only", e.mime, e.path] }
                      : { type: "copy", text: text },
        preview: text.slice(0, 12000), previewImage: image ? e.path : "", previewLabel: "CLIPBOARD",
        previewDetail: "Copied locally · never included in global search"
      })
    }
    return rows
  }
}
