import QtQuick
import "../core/Match.js" as Match

// Installed applications through Omarchy's shared AppLibrary (hidden-entry
// filtering, icon index, launch feedback, uninstall).
Item {
  id: root
  property var host: null
  readonly property var library: host ? host.appLibrary : null

  readonly property var provider: ({
    apiVersion: 1,
    id: "applications",
    name: "Applications",
    icon: "󰀻",
    color: "#91adf4",
    description: "Launch installed desktop apps",
    settings: [],
    query: function(ctx) { return root.query(ctx) },
    opened: function() { if (root.library) root.library.refreshIcons() }
  })

  Connections {
    target: root.library
    function onAppsChanged() { if (root.host) root.host.requery() }
  }

  function keywords(entry) {
    var parts = [entry.genericName || "", entry.comment || ""]
    try { if (entry.keywords && typeof entry.keywords.join === "function") parts.push(entry.keywords.join(" ")) } catch (e) { }
    return parts.join(" ")
  }

  function rowFor(entry, score, order) {
    var name = root.library.entryName(entry)
    var subtitle = root.library.entrySubtext(entry) || String(entry.comment || "") || "Application"
    return {
      id: String(entry.id), title: name, subtitle: subtitle, icon: "󰀻", iconSource: root.library.iconSource(entry.icon),
      section: "Applications", verb: "Launch", tier: "item", score: score, order: order, remember: true,
      appId: String(entry.id), action: { type: "app", id: String(entry.id), name: name }, hint: "Del uninstall"
    }
  }

  function query(ctx) {
    if (ctx.scope && ctx.scope !== "applications") return []
    if (!ctx.scope && !ctx.query)
      return [{ id: "apps", title: "Applications", subtitle: "Every app, one shortcut away", icon: "󰀻", section: "Applications",
                verb: "Open", tier: "item", score: 30, order: 0, action: { type: "navigate", scope: "applications", title: "Applications" } }]
    if (!root.library) return []
    var rows = [], i
    if (!ctx.scope) {
      var all = root.library.sortedEntries("")
      for (i = 0; i < all.length; i++) {
        var entry = all[i].entry
        var s = Match.match(ctx.query, root.library.entryName(entry), root.keywords(entry))
        if (s) rows.push(root.rowFor(entry, s + (s >= 78 ? 45 : 8), i))
      }
      return rows
    }
    var scored = root.library.sortedEntries(ctx.query)
    for (i = 0; i < scored.length; i++) rows.push(root.rowFor(scored[i].entry, 1000 - i, i))
    return rows
  }
}
