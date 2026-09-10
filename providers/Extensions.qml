import QtQuick
import "../core/Match.js" as Match
import "../core/Settings.js" as Settings
import "../core/Extensions.js" as Extensions
import "../core/Patterns.js" as Patterns

// The Extensions screen: every extension Keystroke ships in extensions/ and
// every folder under ~/.local/share/keystroke/extensions, each with its
// switch. Turning one on asks for confirmation, then providers/Registry.qml
// loads its service at once; turning it off destroys the service. An
// extension that declares a setup script gets a "Run setup" row that opens a
// visible terminal. Nothing here touches the network or installs anything:
// extensions arrive with Keystroke's own updates.
Item {
  id: root
  property var host: null

  readonly property var provider: ({
    apiVersion: 1,
    id: "extensions",
    name: "Extensions",
    icon: Extensions.ICON,
    color: "#8bceb4",
    description: "Turn the extensions that ship with Keystroke on and off",
    settings: [],
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) }
  })

  function registry() { return root.host ? root.host.registry : null }
  function extensions() {
    var reg = registry()
    if (!reg) return []
    var cfg = root.host ? root.host.config : null
    var list = Extensions.list(reg.entries, function(id) { return Settings.isEnabled(cfg, ["providers", id], false) }, reg.problems)
    // A loaded provider adds the examples of the query shapes it declares.
    for (var i = 0; i < list.length; i++) {
      var entry = root.host ? root.host.registryEntry(list[i].id) : null
      if (entry && entry.loaded) list[i].examples = Patterns.examples(entry.patterns).slice(0, 6)
    }
    return list
  }
  function find(id) {
    var list = extensions()
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i]
    return null
  }
  Connections {
    target: root.host ? root.host.registry : null
    function onEntriesChanged() { if (root.host && root.host.opened) root.host.requery({ catalog: false, provider: root.provider.id }) }
    function onProblemsChanged() { if (root.host && root.host.opened) root.host.requery({ catalog: false, provider: root.provider.id }) }
  }

  function activate(row, ctx) {
    var effect = ctx.alternate && row.altAction ? row.altAction : row.action
    if (!effect || effect.type !== "extension-setup") return effect
    var e = find(effect.id)
    var argv = e ? Extensions.setupArgv(root.host ? root.host.omarchyPath : "", e) : null
    if (!argv) { if (root.host) root.host.errorMessage = "This extension has no setup script"; return { type: "noop" } }
    return { type: "exec", argv: argv }
  }

  function query(ctx) {
    var id = Extensions.scopeId(ctx.scope)
    if (ctx.scope && id === null) return []
    var list = extensions()
    if (!ctx.scope) {
      var counts = { total: list.length, on: list.filter(function(e) { return e.enabled }).length }
      if (!ctx.query) return [Extensions.navRow(8, counts)]
      var s = Match.match(ctx.query, "Extensions", "extensions plugins community", "", "extensions plugins community providers turn on off enable disable")
      return s ? [Extensions.navRow(s, counts)] : []
    }
    if (id === "") return Extensions.screenRows(ctx.query, list)
    var e = find(id)
    if (!e) return [{ id: "gone", title: "No such extension", subtitle: id, icon: Extensions.ICON, verb: "", tier: "item", score: 1, disabled: true, action: { type: "noop" } }]
    return Extensions.detailRows(ctx.query, e)
  }
}
