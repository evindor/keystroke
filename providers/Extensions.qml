import QtQuick
import "../core/Locale.js" as Locale
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
  function t(key, args) { return Locale.text(root.host, key, args) }

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
    var h = root.host
    var list = Extensions.list(reg.entries, function(id) { return Settings.isEnabled(cfg, ["providers", id], false) }, reg.problems,
                               function(id) { var en = h ? h.registryEntry(id) : null; return en ? h.settingsFor(en).prefix : "" })
    // A loaded provider adds the examples of the query shapes it declares.
    for (var i = 0; i < list.length; i++) {
      var entry = h ? h.registryEntry(list[i].id) : null
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

  function navRow(score, counts) {
    var row = Extensions.navRow(score, counts)
    row.title = root.t(row.title)
    row.verb = root.t(row.verb)
    row.subtitle = root.host && typeof root.host.tn === "function"
      ? root.host.tn("%1 extension", counts.total) + " · " + root.host.tn("%1 enabled", counts.on)
      : row.subtitle
    return row
  }

  function detailRows(query, entry) {
    var rows = Extensions.detailRows(query, entry)
    var consent = Locale.extensionConsent(entry, root.t)
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].confirm && rows[i].action && rows[i].action.type === "setting" && rows[i].action.key === "enabled" && rows[i].action.value === true) { rows[i].confirm = consent.message; rows[i].confirmDetail = consent.detail }
    }
    return rows
  }

  function query(ctx) {
    var id = Extensions.scopeId(ctx.scope)
    if (ctx.scope && id === null) return []
    var list = extensions()
    if (!ctx.scope) {
      var counts = { total: list.length, on: list.filter(function(e) { return e.enabled }).length }
      if (!ctx.query) return [root.navRow(8, counts)]
      var s = Match.match(ctx.query, root.t("Extensions"), "Extensions extensions plugins community", "", "extensions plugins community providers turn on off enable disable")
      return s ? [root.navRow(s, counts)] : []
    }
    if (id === "") return Extensions.screenRows(ctx.query, list)
    var e = find(id)
    if (!e) return [{ id: "gone", title: root.t("No such extension"), subtitle: id, icon: Extensions.ICON, verb: "", tier: "item", score: 1, disabled: true, action: { type: "noop" } }]
    return root.detailRows(ctx.query, e)
  }
}
