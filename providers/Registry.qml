import QtQuick
import Quickshell
import Quickshell.Io
import "../core/Patterns.js" as Patterns
import "../core/Commands.js" as Commands
import "../core/Settings.js" as Settings
import "../core/Extensions.js" as ExtensionsModel

// Instantiates the bundled providers and hosts the extensions. An extension
// is a folder with an extension.json and a Service.qml whose root object
// exposes `readonly property var provider`; the folders ship in Keystroke's
// own extensions/ directory, and ~/.local/share/keystroke/extensions holds
// the ones the user is writing. Every extension is off until switched on in
// keystroke.json (providers.<id>.enabled), and one that is off is never
// compiled or instantiated: the registry lists it from its extension.json
// alone. Switching one on creates its service here, injecting `shell`,
// `extension` and `omarchyPath`; switching it off destroys the service.
Item {
  id: root
  property var host: null
  property var entries: []     // [{ key, provider, source, extensionId, name, patterns, commands, settingsSchema, manifest, loaded }]
  property var problems: []    // [{ id, message }]
  property var manifests: ({}) // extension id → manifest (extension.json plus id, dir, source)
  readonly property string home: Quickshell.env("HOME")
  readonly property string builtinDir: ExtensionsModel.pathOf(Qt.resolvedUrl("../extensions"))
  readonly property string localDir: ExtensionsModel.localDir(home)

  OmarchyMenu { id: omarchyMenu; host: root.host }
  Applications { id: applications; host: root.host }
  Calculator { id: calculator; host: root.host }
  Converter { id: converter; host: root.host }
  Colors { id: colors; host: root.host }
  Emoji { id: emoji; host: root.host }
  Dictation { id: dictation; host: root.host }
  Clipboard { id: clipboard; host: root.host }
  Files { id: files; host: root.host }
  Hotkeys { id: hotkeys; host: root.host }
  AiWeb { id: aiWeb; host: root.host }
  Codex { id: codex; host: root.host }
  Extensions { id: extensions; host: root.host }
  CommandsProvider { id: commandsProvider; host: root.host }
  SettingsProvider { id: settingsProvider; host: root.host }

  readonly property var bundled: [omarchyMenu, applications, calculator, converter, colors, emoji, clipboard, dictation, files, hotkeys, codex, aiWeb, extensions, commandsProvider, settingsProvider]
  readonly property var reserved: bundled.map(function(b) { return b.provider.id }).concat(["palette", "dmenu", "matching", "voice"])

  // Declared patterns and commands are compiled here, once per rebuild, never
  // per keystroke. One that does not compile is reported and skipped; the
  // provider loads. An extension's commands come from its extension.json, so
  // its usage is known while it is off; a bundled provider declares them on
  // the provider object. A provider with commands gets the reserved `prefix`
  // setting in front of its own, so the user can rename the trigger.
  function entry(key, provider, source, extensionId, name, issues, manifest, loaded) {
    var compiled = Patterns.compile(provider.patterns)
    for (var e = 0; e < compiled.errors.length; e++) issues.push({ id: extensionId || key, message: "Pattern " + compiled.errors[e] })
    var declared = manifest && manifest.commands !== undefined ? manifest.commands : provider.commands
    var commands = Commands.compile(declared)
    for (var c = 0; c < commands.errors.length; c++) issues.push({ id: extensionId || key, message: "Command " + commands.errors[c] })
    var settings = Array.isArray(provider.settings) ? provider.settings : []
    var schema = commands.commands.length ? [Commands.prefixSchema(commands.commands)].concat(settings) : settings
    return { key: key, provider: provider, source: source, extensionId: extensionId, name: name, patterns: compiled.patterns,
             commands: commands.commands, settingsSchema: schema, manifest: manifest || null, loaded: loaded !== false }
  }

  function rebuild() {
    var out = [], issues = []
    for (var b = 0; b < bundled.length; b++)
      out.push(entry(bundled[b].provider.id, bundled[b].provider, "bundled", "", bundled[b].provider.name, issues))

    var ids = Object.keys(root.manifests).sort()
    for (var i = 0; i < ids.length; i++) {
      var id = ids[i], manifest = root.manifests[id], service = root.services[id]
      var p = service && service.instance ? service.instance.provider : null
      if (service && service.problem) issues.push({ id: id, message: service.problem })
      else if (service && (!p || typeof p !== "object")) issues.push({ id: id, message: manifest.entry + " does not expose a provider object" })
      else if (service && p.apiVersion !== 1) issues.push({ id: id, message: "Needs Keystroke provider API 1, provider declares " + p.apiVersion })
      else if (service && (typeof p.query !== "function" || !p.name)) issues.push({ id: id, message: "Provider must define name and query(ctx)" })
      else if (service) { out.push(entry(id, p, "extension", id, p.name, issues, manifest, true)); continue }
      out.push(entry(id, ExtensionsModel.placeholder(manifest), "extension", id, manifest.name, issues, manifest, false))
    }
    root.entries = out
    root.problems = root.scanProblems.concat(issues)
  }

  // ------------------------------------------------------------ extensions
  // One scan when the registry is created and one per palette open, so a
  // folder that appeared in the local directory is picked up without a
  // shell restart. A scan that finds the same manifests changes nothing; a
  // manifest that changed recreates a running service, a folder that
  // disappeared destroys it.
  property var services: ({})      // extension id → { instance, stamp, problem }
  property var scanProblems: []
  property string scanStamp: ""

  Process {
    id: scanner
    command: ExtensionsModel.scanArgv(root.builtinDir, root.localDir)
    stdout: StdioCollector { onStreamFinished: root.applyScan(text) }
  }
  function scan() { if (!scanner.running) scanner.running = true }
  function applyScan(text) {
    var found = ExtensionsModel.parseScan(text, root.reserved), stamp = JSON.stringify(found)
    if (stamp === root.scanStamp) return
    root.scanStamp = stamp
    root.scanProblems = found.problems
    root.manifests = found.manifests
    root.sync(true)
  }
  function switchedOn(id) { return Settings.isEnabled(root.host ? root.host.config : null, ["providers", id], false) }

  // Reconcile the services with the manifests and the switches: create what
  // is on and not running, destroy what is off or gone, keep the rest.
  function sync(force) {
    var next = ({}), changed = !!force
    for (var id in root.manifests) {
      var manifest = root.manifests[id], stamp = JSON.stringify(manifest), current = root.services[id]
      if (!root.switchedOn(id)) { if (current && current.instance) current.instance.destroy(); continue }
      if (current && current.stamp === stamp) { next[id] = current; continue }
      if (current && current.instance) current.instance.destroy()
      next[id] = root.createService(manifest)
      next[id].stamp = stamp
      changed = true
    }
    for (var gone in root.services) if (!next[gone]) { changed = true; if (root.services[gone].instance) root.services[gone].instance.destroy() }
    if (!changed) return
    root.services = next
    root.rebuild()
  }
  // { instance, problem }: the instance, or the reason there is none.
  function createService(manifest) {
    var url = ExtensionsModel.serviceUrl(manifest)
    if (!url) return { instance: null, problem: "entry must be a .qml file inside the extension folder" }
    var component = Qt.createComponent(url, Component.PreferSynchronous)
    if (component.status !== Component.Ready) return { instance: null, problem: String(component.errorString() || manifest.entry + " failed to load").trim() }
    var instance = component.createObject(root)
    if (!instance) return { instance: null, problem: manifest.entry + " could not be instantiated" }
    if ("omarchyPath" in instance) instance.omarchyPath = root.host ? root.host.omarchyPath : Quickshell.env("OMARCHY_PATH")
    if ("shell" in instance) instance.shell = root.host ? root.host.shell : null
    if ("extension" in instance) instance.extension = JSON.parse(JSON.stringify(manifest))
    return { instance: instance, problem: "" }
  }
  // The shell injects Keystroke's `shell` after creating the palette; pass it
  // on. The switches live in the config: every change reconciles.
  Connections {
    target: root.host
    function onShellChanged() {
      for (var id in root.services) { var s = root.services[id].instance; if (s && "shell" in s) s.shell = root.host.shell }
    }
    function onConfigChanged() { root.sync() }
  }

  onHostChanged: rebuild()
  Component.onCompleted: { rebuild(); scan() }
}
