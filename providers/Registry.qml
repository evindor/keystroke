import QtQuick
import "../core/Patterns.js" as Patterns

// Instantiates the bundled providers and discovers community ones. A
// community provider is an Omarchy plugin of kind "service" whose manifest
// carries a top-level `"x-keystroke": {"apiVersion": 1}` marker and whose
// Service.qml exposes `readonly property var provider`. Omarchy loads,
// injects, reloads and destroys that service; we only look it up through
// shell.serviceFor(id), so enable/disable/remove need no code here.
Item {
  id: root
  property var host: null
  property var entries: []     // [{ key, provider, source, pluginId, name }]
  property var problems: []    // [{ pluginId, message }]

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
  SettingsProvider { id: settingsProvider; host: root.host }

  readonly property var bundled: [omarchyMenu, applications, calculator, converter, colors, emoji, clipboard, dictation, files, hotkeys, codex, aiWeb, extensions, settingsProvider]

  // Declared patterns are compiled here, once per rebuild, never per keystroke.
  // A pattern that does not compile is reported and skipped; the provider loads.
  function entry(key, provider, source, pluginId, name, issues) {
    var compiled = Patterns.compile(provider.patterns)
    for (var e = 0; e < compiled.errors.length; e++) issues.push({ pluginId: pluginId || key, message: "Pattern " + compiled.errors[e] })
    return { key: key, provider: provider, source: source, pluginId: pluginId, name: name, patterns: compiled.patterns }
  }

  function rebuild() {
    var out = [], issues = []
    for (var b = 0; b < bundled.length; b++)
      out.push(entry(bundled[b].provider.id, bundled[b].provider, "bundled", "", bundled[b].provider.name, issues))

    var shell = host ? host.shell : null
    var registry = host ? host.pluginRegistry : null
    if (shell && registry && registry.installedPlugins && typeof shell.serviceFor === "function") {
      for (var id in registry.installedPlugins) {
        var manifest = registry.installedPlugins[id]
        var marker = manifest ? manifest["x-keystroke"] : null
        if (!marker || typeof marker !== "object") continue
        if (!registry.isEnabled(id)) continue
        var instance = shell.serviceFor(id)
        if (!instance && typeof shell.ensureService === "function") instance = shell.ensureService(id)
        if (!instance) { issues.push({ pluginId: id, message: "Service not loaded: the plugin needs kind \"service\" and entryPoints.service" }); continue }
        var p = instance.provider
        if (!p || typeof p !== "object") { issues.push({ pluginId: id, message: "Service.qml does not expose a provider object" }); continue }
        if (p.apiVersion !== 1) { issues.push({ pluginId: id, message: "Needs Keystroke provider API 1, plugin declares " + p.apiVersion }); continue }
        if (typeof p.query !== "function" || !p.name) { issues.push({ pluginId: id, message: "Provider must define name and query(ctx)" }); continue }
        out.push(entry(id, p, "community", id, manifest.name || id, issues))
      }
    }
    root.entries = out
    root.problems = issues
  }

  Connections {
    target: root.host ? root.host.pluginRegistry : null
    function onPluginsChanged() { root.rebuild(); if (root.host) root.host.requery() }
  }
  // The shell injects pluginRegistry after creating the palette, and it
  // recreates the palette on every plugin rescan: rebuild when the registry
  // arrives, and again on every summon so a service that finished loading
  // after the last rebuild is picked up.
  Connections {
    target: root.host
    function onPluginRegistryChanged() { root.rebuild() }
  }

  onHostChanged: rebuild()
  Component.onCompleted: rebuild()
}
