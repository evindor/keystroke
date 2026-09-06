import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import "../omarchy/MenuModel.js" as MenuModel
import "../core/Match.js" as Match

// The complete Omarchy menu as a Keystroke provider. Parsing, merging, routes,
// guards and dynamic providers follow the stock plugin (Menu.qml/MenuModel.js
// in Omarchy 4.0.2) so behavior stays identical; only presentation changed.
Item {
  id: root
  property var host: null
  readonly property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  readonly property string defaultMenuPath: omarchyPath + "/default/omarchy/omarchy-menu.jsonc"
  readonly property string userMenuPath: Quickshell.env("HOME") + "/.config/omarchy/extensions/omarchy-menu.jsonc"

  property var defaultMenuItems: []
  property var userMenuItems: []
  property var items: ({})
  property var itemOrder: []
  property bool rowsLoaded: false
  property var whenResults: ({})
  property var checkedResults: ({})
  property bool guardsPending: false
  property var providersLoaded: ({})
  property var providerQueue: []
  property int providerRevision: 0
  property string lastEnteredMenu: ""
  property var pathCache: ({})

  readonly property var destructiveIds: ({ "system.shutdown": true, "system.reboot": true, "system.logout": true, "system.hibernate": true })

  // Same enumerations as the stock menu; `apps` is served by the Applications provider.
  readonly property var providers: ({
    "fonts": {
      script: "current=$(omarchy-font-current 2>/dev/null); omarchy-font-list 2>/dev/null | while read -r f; do [[ -z $f ]] && continue; printf '%s\\t%s\\t%s\\n' \"$f\" \"$f\" \"$current\"; done",
      icon: "",
      volatile: true,
      actionFor: function(value) { return "omarchy-font-set " + Util.shellQuote(value) }
    },
    "power-profiles": {
      script: "current=$(powerprofilesctl get 2>/dev/null); omarchy-powerprofiles-list 2>/dev/null | while read -r p; do [[ -z $p ]] && continue; printf '%s\\t%s\\t%s\\n' \"$p\" \"$p\" \"$current\"; done",
      icon: "\udb81\udc0b",
      actionFor: function(value) { return "omarchy-powerprofiles-set autodetect " + Util.shellQuote(value) }
    }
  })

  readonly property var provider: ({
    apiVersion: 1,
    id: "omarchy",
    name: "Omarchy",
    icon: "\udb82\udcc7",
    color: "#d4a774",
    description: "The complete, live Omarchy menu",
    settings: [
      { key: "confirmDestructive", type: "boolean", label: "Confirm destructive actions", "default": true,
        description: "Confirm shutdown, reboot, logout, removal and config resets" }
    ],
    query: function(ctx) { return root.query(ctx) },
    catalog: function(ctx) { return root.catalog(ctx) },
    opened: function() { root.evaluateGuards() }
  })

  // ---------------------------------------------------------------- model
  function item(id) { return root.items[id] || null }

  function rebuildItemsFromSources() {
    var merged = MenuModel.mergeMenuSources(root.defaultMenuItems, root.userMenuItems)
    root.providerRevision += 1
    root.providersLoaded = ({})
    root.providerQueue = []
    root.items = merged.items
    root.itemOrder = merged.itemOrder
    root.pathCache = ({})
    root.rowsLoaded = true
    root.lastEnteredMenu = ""
    root.evaluateGuards()
    if (root.host) root.host.requery()
  }

  function reload() {
    defaultMenuFile.reload()
    userMenuFile.reload()
  }

  FileView {
    id: defaultMenuFile
    path: root.defaultMenuPath
    watchChanges: true
    printErrors: false
    onLoaded: { root.defaultMenuItems = MenuModel.parseMenuJsonc(text()); root.rebuildItemsFromSources() }
    onFileChanged: reload()
  }

  FileView {
    id: userMenuFile
    path: root.userMenuPath
    watchChanges: true
    printErrors: false
    onLoaded: { root.userMenuItems = MenuModel.parseMenuJsonc(text()); root.rebuildItemsFromSources() }
    onLoadFailed: { root.userMenuItems = []; root.rebuildItemsFromSources() }
    onFileChanged: reload()
  }

  // ---------------------------------------------------------------- guards
  // One batch per (re)load and per open, never per query. The menu shows the
  // previous answers until the batch lands, exactly like the stock menu.
  function evaluateGuards() {
    if (guardProc.running) { root.guardsPending = true; return }
    root.guardsPending = false
    var script = MenuModel.guardScript(root.items)
    if (!script) { root.whenResults = ({}); root.checkedResults = ({}); return }
    guardProc.collected = ""
    guardProc.command = ["bash", "-lc", script]
    guardProc.running = true
  }

  Process {
    id: guardProc
    property string collected: ""
    stdout: SplitParser { onRead: function(data) { guardProc.collected += data + "\n" } }
    onExited: function(exitCode, exitStatus) {
      if (exitCode !== 0 || exitStatus !== 0) {
        if (root.guardsPending) Qt.callLater(function() { root.evaluateGuards() })
        return
      }
      var nextWhen = ({}), nextChecked = ({})
      var lines = guardProc.collected.split("\n")
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim()
        if (!line) continue
        var colon = line.lastIndexOf(":")
        if (colon < 0) continue
        var value = line.substring(colon + 1) === "1"
        var rest = line.substring(0, colon)
        var tagAt = rest.lastIndexOf(":")
        if (tagAt < 0) continue
        var id = rest.substring(0, tagAt), tag = rest.substring(tagAt + 1)
        if (tag === "w") nextWhen[id] = value
        else if (tag === "c") nextChecked[id] = value
      }
      root.whenResults = nextWhen
      root.checkedResults = nextChecked
      if (root.host) root.host.requery()
      if (root.guardsPending) Qt.callLater(function() { root.evaluateGuards() })
    }
  }

  // ------------------------------------------------------------- providers
  function startProviderForMenu(id) {
    var entry = root.item(id)
    if (!entry || !entry.provider || root.providersLoaded[id]) return
    var spec = root.providers[entry.provider]
    if (!spec) return
    var loaded = ({})
    for (var k in root.providersLoaded) loaded[k] = root.providersLoaded[k]
    loaded[id] = true
    root.providersLoaded = loaded
    providerProc.menuId = id
    providerProc.providerKey = entry.provider
    providerProc.revision = root.providerRevision
    providerProc.collected = ""
    providerProc.command = ["bash", "-lc", spec.script]
    providerProc.running = true
  }

  function mergeProviderRows(rows, menuId, providerKey) {
    var spec = root.providers[providerKey]
    if (!spec) return
    var lines = String(rows || "").split("\n")
    var providerRows = []
    var takenIds = ({})
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim()
      if (!line) continue
      var parts = line.split("\t")
      var label = parts[0] || ""
      var value = parts[1] || parts[0] || ""
      var current = parts[2] || ""
      if (!label) continue
      var rowId = menuId + "." + MenuModel.slugify(value)
      while (takenIds[rowId]) rowId += "-"
      takenIds[rowId] = true
      providerRows.push({ id: rowId, parent: menuId, kind: "action", icon: (value === current) ? "✓" : (spec.icon || ""),
        label: label, title: "", target: "", description: "", action: spec.actionFor(value), provider: "",
        aliases: [], when: "", checked: "", order: 0 })
    }
    var merged = MenuModel.swapProviderRows(root.items, root.itemOrder, menuId, providerRows)
    root.items = merged.items
    root.itemOrder = merged.itemOrder
    root.pathCache = ({})
  }

  function startNextProvider() {
    if (providerProc.running) return
    while (root.providerQueue.length > 0) {
      var id = root.providerQueue.shift()
      var entry = root.item(id)
      if (!entry || !entry.provider || root.providersLoaded[id]) continue
      root.startProviderForMenu(id)
      return
    }
  }

  function invalidateVolatileProvider(id) {
    var entry = root.item(id)
    var spec = entry && entry.provider ? root.providers[entry.provider] : null
    if (spec && spec.volatile && root.providersLoaded[id]) {
      var loaded = ({})
      for (var k in root.providersLoaded) if (k !== id) loaded[k] = root.providersLoaded[k]
      root.providersLoaded = loaded
    }
  }

  function loadProviderForMenu(id) {
    var entry = root.item(id)
    if (!entry || !entry.provider || root.providersLoaded[id] || !root.providers[entry.provider]) return
    if (providerProc.running) {
      if (root.providerQueue.indexOf(id) < 0) root.providerQueue = root.providerQueue.concat([id])
      return
    }
    root.startProviderForMenu(id)
  }

  function loadProvidersForSearch(active) {
    for (var i = 0; i < root.itemOrder.length; i++) {
      var entry = root.item(root.itemOrder[i])
      if (!entry || !entry.provider || root.providersLoaded[entry.id]) continue
      if (active !== "root" && entry.id !== active && !MenuModel.isDescendantOf(root.items, entry.id, active)) continue
      root.loadProviderForMenu(entry.id)
    }
  }

  Process {
    id: providerProc
    property string menuId: ""
    property string providerKey: ""
    property string collected: ""
    property int revision: 0
    stdout: SplitParser { onRead: function(data) { providerProc.collected += data + "\n" } }
    onExited: {
      if (providerProc.revision === root.providerRevision) {
        root.mergeProviderRows(providerProc.collected, providerProc.menuId, providerProc.providerKey)
        if (root.host) root.host.requery()
      }
      root.startNextProvider()
    }
  }

  // ---------------------------------------------------------------- routes
  function resolveRoute(input) { return MenuModel.resolveRoute(root.items, root.itemOrder, input) }

  // Mirrors the stock openRoute(): leaf actions run immediately, links are followed.
  function routeFor(input) {
    if (!root.rowsLoaded) return { kind: "menu", id: "root" }
    var id = root.resolveRoute(input)
    var entry = root.items[id]
    if (entry && entry.kind === "action" && entry.action) return { kind: "action", action: entry.action, label: entry.label }
    if (entry && entry.kind === "link" && entry.target) { id = entry.target; entry = root.items[id] }
    if (entry && entry.provider === "apps") return { kind: "apps" }
    return { kind: "menu", id: entry ? id : "root", label: entry ? (entry.title || entry.label) : "" }
  }

  function isVisible(entry) { return MenuModel.isVisible(root.items, root.itemOrder, root.whenResults, entry) }

  function isDestructive(id) {
    return root.destructiveIds[id] === true || id.indexOf("remove.") === 0 || id.indexOf("update.config.") === 0
  }

  // Breadcrumb labels and search tokens per entry, kept until the model
  // changes so every keystroke hands the matcher the same strings.
  function searchInfo(id) {
    var hit = root.pathCache[id]
    if (hit) return hit
    var labels = [], current = root.item(id), guard = 0
    while (current && current.id !== "root" && guard < 32) { labels.unshift(current.label); current = root.item(current.parent); guard++ }
    var entry = root.item(id)
    hit = { labels: labels, path: labels.join(" › "), relative: ({}),
            keywords: entry ? (entry.aliases.join(" ") + " " + MenuModel.searchableToken(MenuModel.leafIdFor(id))).trim() : "" }
    root.pathCache[id] = hit
    return hit
  }

  // Breadcrumb below the menu being searched: `path` ends in the entry's own
  // label, `parent` is what the row shows as its subtitle.
  function relativeTo(id, activeId) {
    var info = root.searchInfo(id)
    var hit = info.relative[activeId]
    if (hit) return hit
    var depth = activeId === "root" ? 0 : root.searchInfo(activeId).labels.length
    var rel = info.labels.slice(depth)
    hit = { path: rel.join(" › "), parent: rel.slice(0, -1).join(" › ") }
    info.relative[activeId] = hit
    return hit
  }

  function rowFor(entry, subtitle, score, confirmDestructive) {
    var action, verb
    if (entry.kind === "action") {
      action = { type: "shell", command: entry.action }
      verb = "Run"
    } else if (entry.provider === "apps") {
      action = { type: "navigate", scope: "applications", title: "Applications" }
      verb = "Open"
    } else {
      var target = entry.kind === "link" ? entry.target : entry.id
      action = { type: "navigate", scope: "omarchy/" + target, title: entry.title || entry.label }
      verb = "Open"
    }
    return {
      id: entry.id, title: entry.label, subtitle: subtitle || "", icon: entry.icon || "\udb82\udcc7", iconFont: entry.iconFont || "",
      section: "Omarchy", verb: verb, tier: "item", score: score, order: entry.order,
      accessory: entry.checked && root.checkedResults[entry.id] ? "✓" : "",
      remember: true, action: action, previewDetail: root.searchInfo(entry.id).path,
      confirm: entry.kind === "action" && confirmDestructive && root.isDestructive(entry.id) ? "Run “" + entry.label + "”?" : ""
    }
  }

  // Every visible entry of the whole menu, for the voice assistant's
  // catalog; `detail` is the breadcrumb above the entry ("System › Lock").
  function catalog(ctx) {
    if (!root.rowsLoaded) return []
    var confirmDestructive = !ctx || !ctx.settings || ctx.settings.confirmDestructive !== false
    var rows = []
    for (var i = 0; i < root.itemOrder.length; i++) {
      var entry = root.item(root.itemOrder[i])
      if (!entry || entry.id === "root" || !root.isVisible(entry)) continue
      var row = root.rowFor(entry, entry.description, 1, confirmDestructive)
      row.detail = root.searchInfo(entry.id).labels.slice(0, -1).join(" › ") || entry.description || ""
      rows.push(row)
    }
    return rows
  }

  function query(ctx) {
    if (ctx.scope && ctx.scope.split("/")[0] !== "omarchy") return []
    if (!root.rowsLoaded) { ctx.pending(); return [] }
    var confirmDestructive = ctx.settings.confirmDestructive !== false
    if (!ctx.scope && !ctx.query)
      return [{ id: "menu", title: "Omarchy Menu", subtitle: "Your entire desktop, at your fingertips", icon: "\udb82\udcc7",
                section: "Omarchy", verb: "Open", tier: "item", score: 28, order: 1,
                action: { type: "navigate", scope: "omarchy/root", title: "Omarchy" } }]
    var active = ctx.sub && root.item(ctx.sub) ? ctx.sub : "root"
    var rows = [], i, entry
    if (!ctx.query) {
      if (root.lastEnteredMenu !== active) {
        root.lastEnteredMenu = active
        root.invalidateVolatileProvider(active)
        root.loadProviderForMenu(active)
      }
      var activeEntry = root.item(active)
      if (activeEntry.provider && !root.providersLoaded[active] && root.providers[activeEntry.provider]) ctx.pending()
      for (i = 0; i < root.itemOrder.length; i++) {
        entry = root.item(root.itemOrder[i])
        if (!entry || entry.parent !== active || !root.isVisible(entry)) continue
        rows.push(root.rowFor(entry, entry.description, 1, confirmDestructive))
      }
      return rows
    }
    root.loadProvidersForSearch(active)
    for (i = 0; i < root.itemOrder.length; i++) {
      entry = root.item(root.itemOrder[i])
      if (!entry || entry.id === "root") continue
      if (active !== "root" && !MenuModel.isDescendantOf(root.items, entry.id, active)) continue
      if (!root.isVisible(entry)) continue
      // Fuzzy over the label, the breadcrumb below this menu ("sysshut" →
      // System › Shutdown) and the aliases; the description by whole word.
      var rel = root.relativeTo(entry.id, active)
      var s = Match.match(ctx.query, entry.label, root.searchInfo(entry.id).keywords, rel.parent ? rel.path : "", entry.description)
      if (!s) continue
      rows.push(root.rowFor(entry, rel.parent || entry.description, s + (entry.kind === "action" ? 3 : 0), confirmDestructive))
    }
    return rows
  }
}
