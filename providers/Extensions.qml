import QtQuick
import Quickshell
import Quickshell.Io
import "../core/Match.js" as Match
import "../core/Settings.js" as Settings
import "../core/Extensions.js" as Extensions

// Community providers as installable Omarchy plugins, managed from inside the
// palette: discover them from the Keystroke index and the Omarchy marketplace,
// install from either or from any git URL, check for and apply updates, turn
// them on and off, remove them. Every change goes through Omarchy's own
// plugin scripts (omarchy-plugin-add/update/remove) run as one background job
// at a time, so the CLI and the palette can never disagree; loading and
// unloading use the shell's PluginRegistry directly. The two catalogs are
// cached under ~/.cache/keystroke and refreshed at most once an hour.
Item {
  id: root
  property var host: null
  readonly property string home: Quickshell.env("HOME")
  readonly property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  readonly property string cacheDir: home + "/.cache/keystroke"

  property var indexEntries: []
  property var catalogEntries: []
  property var gitState: ({})          // id → { head, remoteHead, remote }
  property string checkedAt: ""
  property var job: null               // { kind, id, name, label, detail, url, queue, startedAt }
  property string fetching: ""         // "index" | "catalog" | ""
  property string fetchError: ""
  property double indexFetched: 0
  property double catalogFetched: 0
  property bool autoChecked: false
  readonly property int freshMs: 60 * 60 * 1000

  readonly property var provider: ({
    apiVersion: 1,
    id: "extensions",
    name: "Extensions",
    icon: Extensions.ICON,
    color: "#8bceb4",
    description: "Install, update and manage community providers",
    settings: [
      { key: "marketplace", type: "boolean", label: "Search the Omarchy marketplace", "default": true,
        description: "Lists marketplace plugins that name Keystroke, next to the Keystroke index" },
      { key: "autoCheck", type: "boolean", label: "Check for updates when the Extensions screen opens", "default": true,
        description: "One git fetch per installed extension, at most once per palette session" },
      { key: "indexUrl", type: "string", label: "Extension index URL", "default": Extensions.INDEX_URL,
        description: "JSON list of known Keystroke extensions; point it at a fork to curate your own" }
    ],
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) },
    opened: function() { root.autoChecked = false }
  })

  // ------------------------------------------------------------- registry
  function registry() { return root.host ? root.host.pluginRegistry : null }
  function installedList() {
    var reg = registry()
    if (!reg || !reg.installedPlugins) return []
    var cfg = root.host ? root.host.config : null
    return Extensions.installed(reg.installedPlugins, function(id) { return reg.isEnabled(id) },
                                function(id) { return Settings.isEnabled(cfg, ["providers", id], false) }, root.gitState)
  }
  function find(id) {
    var list = installedList()
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i]
    return null
  }
  Connections {
    target: root.host ? root.host.pluginRegistry : null
    function onPluginsChanged() { if (root.host) root.host.requery() }
  }

  // ---------------------------------------------------------------- caches
  FileView { id: indexCache; printErrors: false; path: root.cacheDir + "/extensions-index.json"; onLoaded: root.readCache(indexCache, "index") ; onLoadFailed: {} }
  FileView { id: catalogCache; printErrors: false; path: root.cacheDir + "/marketplace-catalog.json"; onLoaded: root.readCache(catalogCache, "catalog"); onLoadFailed: {} }
  function readCache(view, kind) {
    var doc
    try { doc = JSON.parse(view.text()) } catch (e) { return }
    if (!doc || typeof doc !== "object") return
    if (kind === "index") { root.indexEntries = Extensions.parseIndex(doc.body || ""); root.indexFetched = Number(doc.fetchedAt || 0) }
    else { root.catalogEntries = Extensions.parseCatalog(doc.body || ""); root.catalogFetched = Number(doc.fetchedAt || 0) }
    if (root.host) root.host.requery()
  }
  function writeCache(view, body) {
    view.setText(JSON.stringify({ fetchedAt: Date.now(), body: body }))
  }

  Process {
    id: fetcher
    property string kind: ""
    property string url: ""
    stdout: StdioCollector {
      onStreamFinished: {
        var body = text
        if (fetcher.kind === "index") {
          var idx = Extensions.parseIndex(body)
          if (idx.length || body.indexOf('"extensions"') >= 0) { root.indexEntries = idx; root.indexFetched = Date.now(); root.writeCache(indexCache, body) }
          else root.fetchError = "Index unreadable: " + fetcher.url
        } else {
          root.catalogEntries = Extensions.parseCatalog(body); root.catalogFetched = Date.now(); root.writeCache(catalogCache, body)
        }
      }
    }
    onExited: function(code) {
      if (code !== 0) root.fetchError = "Could not fetch the " + fetcher.kind + " (curl exit " + code + ")"
      var next = fetcher.kind === "index" ? "catalog" : ""
      root.fetching = ""
      if (next) root.fetch(next); else if (root.host) root.host.requery()
    }
  }
  function fetch(kind) {
    if (fetcher.running) return
    var url = kind === "index" ? String(root.settings().indexUrl || Extensions.INDEX_URL) : Extensions.CATALOG_URL
    if (kind === "catalog" && !root.settings().marketplace) { root.fetching = ""; if (root.host) root.host.requery(); return }
    if (url.indexOf("https://") !== 0 && url.indexOf("file://") !== 0) { root.fetchError = "Index URL must be https"; return }
    root.fetching = kind
    root.fetchError = ""
    fetcher.kind = kind
    fetcher.url = url
    fetcher.command = Extensions.fetchArgv(url)
    fetcher.running = true
  }
  function refresh() { if (!fetcher.running) root.fetch("index") }
  function ensureFresh() {
    if (fetcher.running) return
    var now = Date.now()
    if (now - root.indexFetched > root.freshMs) root.fetch("index")
    else if (root.settings().marketplace && now - root.catalogFetched > root.freshMs) root.fetch("catalog")
  }
  function settings() {
    var entry = root.host ? root.host.registryEntry("extensions") : null
    return entry ? root.host.settingsFor(entry) : Settings.values(null, [], root.provider.settings)
  }

  // ------------------------------------------------------------------ jobs
  // One job at a time, run detached (see Extensions.jobArgv): the shell
  // rescans its plugins after an install or removal and recreates this
  // provider, so the job's state lives in files under the runtime dir and is
  // polled while it runs. A fresh instance picks up a job that is still
  // running or a result nobody has read yet.
  readonly property string jobDir: Quickshell.env("XDG_RUNTIME_DIR") + "/keystroke/extensions"
  FileView { id: jobFile; printErrors: false; path: root.jobDir + "/job.json"; onLoaded: root.readJob(); onLoadFailed: root.job = null }
  FileView { id: resultFile; printErrors: false; path: root.jobDir + "/result.json"; onLoaded: root.readResult() }
  Timer { id: poll; interval: 400; repeat: true; running: root.job !== null; onTriggered: { resultFile.reload(); jobFile.reload() } }
  function readJob() {
    var j
    try { j = JSON.parse(jobFile.text()) } catch (e) { return }
    if (j && typeof j === "object" && j.kind) root.job = j
  }
  function readResult() {
    var r = Extensions.parseResult(resultFile.text())
    if (!r) return
    if (root.job && root.job.startedAt === r.job.startedAt) root.job = null
    Quickshell.execDetached(["rm", "-f", root.jobDir + "/result.json"])
    root.finish(r.job, r.code, r.output)
  }
  function finish(j, code, output) {
    var tail = output.trim().split("\n").filter(Boolean).slice(-1)[0] || ""
    if (j.kind === "check") {
      var parsed = Extensions.parseCheck(output)
      var next = ({})
      for (var k in root.gitState) next[k] = root.gitState[k]
      for (var id in parsed) next[id] = parsed[id]
      root.gitState = next
      root.checkedAt = Qt.formatTime(new Date(), "HH:mm")
      var updates = 0
      for (var u in next) if (next[u].head && next[u].remoteHead && next[u].head !== next[u].remoteHead) updates++
      if (root.host) root.host.statusMessage = updates ? updates + " update" + (updates === 1 ? "" : "s") + " available" : "Extensions are up to date"
    } else if (code === 0) {
      if (j.kind === "install") root.afterInstall(j.id || Extensions.parseAdded(output), j.url)
      if (j.kind === "update") { var g = ({}); for (var gk in root.gitState) if (gk !== j.id) g[gk] = root.gitState[gk]; root.gitState = g; root.check([j.id]) }
      if (j.kind === "remove" && root.host && root.host.scope === Extensions.KEY + "/" + j.id) root.host.goBack()
      if (j.kind === "update" && j.queue && j.queue.length) root.updateQueue(j.queue)
      if (root.host) root.host.statusMessage = j.done || tail
    } else if (root.host) {
      root.host.errorMessage = (j.label + ": " + (tail || "exit " + code)).slice(0, 300)
    }
    if (root.host) root.host.requery()
  }
  function run(job, argv) {
    if (root.job) { if (root.host) root.host.errorMessage = "Another extension job is still running"; return false }
    job.startedAt = Date.now()
    root.job = job
    Quickshell.execDetached(Extensions.jobArgv(root.jobDir, job, root.omarchyPath, argv))
    if (root.host) root.host.requery()
    return true
  }
  function check(ids) {
    if (!ids.length) { root.checkedAt = Qt.formatTime(new Date(), "HH:mm"); return }
    root.run({ kind: "check", id: ids.length === 1 ? ids[0] : "", label: "Checking for updates", detail: ids.length + " extension" + (ids.length === 1 ? "" : "s") },
             Extensions.checkArgv(root.home, ids))
  }
  function gitManaged() {
    var reg = registry(), ids = []
    if (!reg || !reg.installedPlugins) return ids
    for (var id in reg.installedPlugins) if (reg.installedPlugins[id] && reg.installedPlugins[id][Extensions.MARKER]) ids.push(id)
    return ids
  }
  // Read once at creation and once more shortly after: a job launched a
  // moment before this instance existed may not have written job.json yet.
  Component.onCompleted: { jobFile.reload(); resultFile.reload() }
  Timer { interval: 700; running: true; onTriggered: { jobFile.reload(); resultFile.reload() } }

  // Keystroke's own switch lives in keystroke.json; turning an extension on
  // also loads it into the shell, since a provider that is not loaded has
  // nothing to show.
  function setEnabled(id, value) {
    var reg = registry()
    if (value && reg && !reg.isEnabled(id) && !reg.setEnabled(id, true, {})) { root.host.errorMessage = "Could not load " + id + ": " + (reg.lastEnableError || "unknown plugin"); return null }
    return { type: "setting", path: ["providers", id], key: "enabled", value: value, schema: { key: "enabled", type: "boolean" } }
  }

  function activate(row, ctx) {
    var effect = ctx.alternate && row.altAction ? row.altAction : row.action
    if (!effect || effect.type !== "ext") return effect
    var h = root.host, name = effect.name || effect.id
    switch (effect.op) {
    case "install":
      root.run({ kind: "install", id: effect.id, name: name, label: "Installing " + name, detail: effect.url, done: "Installed " + name, url: effect.url },
               Extensions.installArgv(root.omarchyPath, effect.url))
      return { type: "noop" }
    case "update":
      root.run({ kind: "update", id: effect.id, name: name, label: "Updating " + name, detail: effect.id, done: "Updated " + name }, Extensions.updateArgv(root.omarchyPath, effect.id))
      return { type: "noop" }
    case "update-all": {
      var ids = [], list = installedList()
      for (var i = 0; i < list.length; i++) if (list[i].updateAvailable) ids.push(list[i].id)
      root.updateQueue(ids)
      return { type: "noop" }
    }
    case "remove":
      root.run({ kind: "remove", id: effect.id, name: name, label: "Removing " + name, detail: effect.id, done: "Removed " + name }, Extensions.removeArgv(root.omarchyPath, effect.id))
      return { type: "noop" }
    case "check":
      root.check(effect.id ? [effect.id] : root.gitManaged())
      return { type: "noop" }
    case "refresh":
      root.indexFetched = 0; root.catalogFetched = 0
      root.refresh()
      return { type: "noop" }
    case "load": {
      var reg = registry()
      if (!reg || !reg.setEnabled(effect.id, !!effect.value, {})) { h.errorMessage = "Could not " + (effect.value ? "load " : "unload ") + effect.id + (reg && reg.lastEnableError ? ": " + reg.lastEnableError : ""); return { type: "noop" } }
      h.statusMessage = (effect.value ? "Loaded " : "Unloaded ") + name
      return { type: "noop" }
    }
    case "enable":
      return root.setEnabled(effect.id, !!effect.value) || { type: "noop" }
    }
    return { type: "noop" }
  }

  // Sequential updates: one omarchy-plugin-update per extension; the rest of
  // the queue rides in the job so a recreated instance can continue it.
  function updateQueue(ids) {
    if (!ids.length) return
    var id = ids[0], rest = ids.slice(1), e = find(id)
    root.run({ kind: "update", id: id, name: e ? e.name : id, label: "Updating " + (e ? e.name : id), detail: rest.length ? rest.length + " more queued" : id,
               done: "Updated " + (e ? e.name : id), queue: rest }, Extensions.updateArgv(root.omarchyPath, id))
  }

  // omarchy-plugin-add enabled the plugin in the shell; Keystroke's own
  // switch defaults to off for anything that appears out of band, but an
  // install the user asked for here is meant to be used.
  function afterInstall(id, url) {
    var h = root.host
    if (!h) return
    var target = id ? find(id) : null
    if (!target) {
      var list = installedList(), slug = Extensions.repoSlug(url)
      for (var i = 0; i < list.length; i++) if (Extensions.repoSlug(list[i].remote || list[i].homepage) === slug) { target = list[i]; break }
    }
    if (!target) {
      // The registry rescans asynchronously; try once more shortly.
      settle.id = id; settle.url = url; settle.restart()
      return
    }
    try { h.saveConfig(Settings.withValue(h.config, ["providers", target.id], "enabled", true, { key: "enabled", type: "boolean" })) }
    catch (e) { h.errorMessage = String(e.message || e) }
    root.check([target.id])
  }
  Timer {
    id: settle
    property string id: ""
    property string url: ""
    property int tries: 0
    interval: 400
    onTriggered: {
      var target = settle.id ? root.find(settle.id) : null
      if (!target) {
        var list = root.installedList(), slug = Extensions.repoSlug(settle.url)
        for (var i = 0; i < list.length; i++) if (Extensions.repoSlug(list[i].remote || list[i].homepage) === slug) { target = list[i]; break }
      }
      if (target) { settle.tries = 0; root.afterInstall(target.id, settle.url); return }
      if (++settle.tries < 10) settle.restart(); else settle.tries = 0
    }
  }

  // ----------------------------------------------------------------- query
  function query(ctx) {
    var id = Extensions.scopeId(ctx.scope)
    if (ctx.scope && id === null) return []
    if (!ctx.scope) {
      if (!ctx.query) return [Extensions.navRow(8)]
      var s = Match.match(ctx.query, "Extensions", "plugins store marketplace community install", "", "extensions plugins store marketplace community providers install update")
      return s ? [Extensions.navRow(s)] : []
    }
    root.ensureFresh()
    if (root.job || root.fetching) ctx.pending()
    var state = { installed: installedList(), discover: Extensions.discover(root.indexEntries, ctx.settings.marketplace ? root.catalogEntries : []),
                  job: root.job, fetching: !!root.fetching, checked: root.checkedAt, error: root.fetchError, marketplace: ctx.settings.marketplace }
    if (id === "") {
      if (ctx.settings.autoCheck && !root.autoChecked && !root.job) { root.autoChecked = true; root.check(root.gitManaged()) }
      return Extensions.screenRows(ctx.query, state)
    }
    var e = find(id)
    if (!e) return [{ id: "gone", title: "Extension not installed", subtitle: id, icon: Extensions.ICON, verb: "", tier: "item", score: 1, disabled: true, action: { type: "noop" } }]
    return Extensions.detailRows(ctx.query, e, state)
  }
}
