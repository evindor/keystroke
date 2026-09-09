pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "ui"
import "providers"
import "voice"
import "core"
import "core/Match.js" as Match
import "core/Frecency.js" as Frecency
import "core/Settings.js" as Settings
import "core/VoiceBindings.js" as VoiceBindings
import "core/Intent.js" as Intent
import "core/Patterns.js" as Patterns

// Keystroke: an extension-first command palette that replaces the Omarchy
// menu. Hosted by omarchy-shell as a `menu` plugin (see manifest.json).
Item {
  id: root

  // Injected by omarchy-shell when the plugin loads.
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null
  property var pluginRegistry: null
  property var barWidgetRegistry: null
  readonly property var appLibrary: applicationLibrary.library
  ApplicationLibrary { id: applicationLibrary; hostShell: root.shell; omarchyPath: root.omarchyPath }
  readonly property string home: Quickshell.env("HOME")
  readonly property string configPath: home + "/.config/omarchy/keystroke.json"
  readonly property string usagePath: home + "/.local/state/keystroke/usage.json"

  // ------------------------------------------------------------ lifecycle
  function open(payloadJson) {
    var payload = ({})
    try { payload = JSON.parse(payloadJson || "{}") } catch (e) { payload = ({}) }
    if (payload.fontFamily) root.fontFamily = payload.fontFamily
    if (payload.mode === "select" || payload.mode === "input") root.openDmenu(payload)
    else root.openRoute(payload.initialMenu || payload.menu || "root", payload)
  }
  // The hotkey's second tap reaches us as the shell's close(): with the voice
  // integration on, that tap starts dictation and a third one stops it; Esc
  // and the scrim still close. (An explicit `omarchy menu close` takes the
  // same path; nothing in Omarchy calls it.)
  function close() {
    if (root.opened && !root.dmenuActive && root.voiceEnabled && !root.confirmPending) {
      if (voice.phase === "starting" || voice.phase === "listening") { root.voiceStop(); return }
      if (voice.phase === "transcribing") return
      if (root.voiceSettings.secondTap === "voice" && root.voiceBegin("tap")) return
    }
    root.cancel()
  }
  function refresh() { providerRegistry.bundled[0].reload(); root.requery(); return "ok" }
  function ping() { return "ok" }
  // Hyprland long-press bind on the hotkey: the key is still down 250 ms
  // after the palette opened, so this is a hold, not a tap.
  function voiceHold(arg) {
    if (!root.opened || root.dmenuActive) return "ignored"
    if (voice.active) { root.voiceTrigger = "hold"; return "listening" }
    return root.voiceBegin("hold") ? "listening" : "ignored"
  }
  // Hyprland release bind on the hotkey (fires while the modifier is still
  // held; the modifier's own release is caught in the search field).
  function voiceRelease(arg) {
    if (!voice.active || root.voiceTrigger !== "hold") return "ignored"
    root.voiceStop()
    return "stopping"
  }

  // Optional provider views share the palette window, focus and voice lifecycle.
  property string activeProviderKey: ""
  property string providerViewRawQuery: ""
  readonly property bool providerViewActive: activeProviderKey.length > 0
  function closeProviderView() {
    if (providerView.item && typeof providerView.item.dismiss === "function") providerView.item.dismiss()
    root.activeProviderKey = ""
    root.providerViewRawQuery = ""
    providerView.sourceComponent = null
  }
  function showProviderView(key) {
    var entry = root.registryEntry(key)
    if (!entry || !root.providerEnabled(entry) || !entry.provider.view) { root.errorMessage = "Provider view is unavailable"; return }
    root.providerViewRawQuery = root.voiceRawText
    root.activeProviderKey = key
    providerView.sourceComponent = entry.provider.view
  }
  // A view whose provider was removed, unloaded or turned off while it was
  // showing (a community plugin disabled from the CLI, say) must not linger
  // over the palette with a destroyed context behind it.
  function dropOrphanedView() {
    if (!root.providerViewActive) return
    var entry = root.registryEntry(root.activeProviderKey)
    if (entry && root.providerEnabled(entry)) return
    root.closeProviderView()
    if (root.opened) { root.runQuery(); search.forceActiveFocus() }
  }
  Connections {
    target: providerRegistry
    function onEntriesChanged() { root.dropOrphanedView() }
  }
  onConfigChanged: root.dropOrphanedView()

  // -------------------------------------------------------------- settings
  property var config: Settings.empty()
  property string configError: ""
  readonly property var paletteSchema: [
    { key: "density", type: "enum", label: "Layout density", "default": "compact", options: ["compact", "comfortable"], description: "Compact uses a narrower window and shorter rows" },
    { key: "accent", type: "enum", label: "Accent color", "default": "theme", options: ["theme", "ember", "violet", "mint"], description: "Theme follows the active Omarchy theme" },
    { key: "showPreview", type: "boolean", label: "Show result previews", "default": true }
  ]
  property var paletteSettings: Settings.values(config, ["palette"], paletteSchema)
  function paletteValues() { return root.paletteSettings }
  function settingsFor(entry) { return Settings.values(root.config, ["providers", entry.key], entry.provider.settings || []) }
  function providerEnabled(entry) { return Settings.isEnabled(root.config, ["providers", entry.key], entry.source === "bundled") }
  function registryEntry(key) {
    for (var i = 0; i < providerRegistry.entries.length; i++) if (providerRegistry.entries[i].key === key) return providerRegistry.entries[i]
    return null
  }
  function applyConfigText(text) {
    var parsed = Settings.parse(text)
    root.configError = parsed.error
    if (parsed.config) root.config = parsed.config
    root.paletteSettings = Settings.values(root.config, ["palette"], root.paletteSchema)
  }
  function saveConfig(next) {
    if (root.configError) throw new Error(root.configError)
    root.config = next
    root.paletteSettings = Settings.values(next, ["palette"], root.paletteSchema)
    configFile.setText(Settings.serialize(next))
  }
  FileView {
    id: configFile
    path: root.configPath
    watchChanges: true
    atomicWrites: true
    printErrors: false
    onLoaded: root.applyConfigText(text())
    onLoadFailed: root.applyConfigText("")
    onFileChanged: reload()
  }

  // ----------------------------------------------------------------- voice
  // Dictation through the voxtype daemon Omarchy ships. Two ways in: hold the
  // palette hotkey (Hyprland long-press bind → voiceHold; its release bind or
  // the modifier's own release → stop), or tap the hotkey again while the
  // palette is open (a further tap stops). Enter finishes recording; a fresh
  // Enter after transcription runs the visible selection. Replies never execute.
  VoiceSession {
    id: voxtypeVoice
    host: root
    onPartial: function(text) { root.voiceLive(text) }
    onTranscribed: function(text) { root.voiceTranscribed(text) }
    onNothingHeard: { root.dictationPending = ""; if (root.opened) root.statusMessage = "Nothing heard" }
    onFailed: function(message) { root.dictationPending = ""; if (root.opened) root.errorMessage = message }
  }
  readonly property var voice: voxtypeVoice
  readonly property var voiceSchema: [
    { key: "enabled", type: "boolean", label: "Voice command integration", "default": true,
      description: "Hold the palette hotkey, or tap it again while the palette is open, to dictate the query" },
    { key: "secondTap", type: "enum", label: "Second tap of the hotkey", "default": "voice", options: ["voice", "close"],
      description: "Voice starts dictation and a third tap stops it (Esc closes); Close is the stock toggle" },
    { key: "keys", type: "string", label: "Hotkeys to hold", "default": "SUPER + SPACE",
      description: "Hyprland combos for the long-press bindings, comma-separated, e.g. SUPER + SPACE, SUPER + SHIFT + code:201" }
  ]
  property var voiceSettings: Settings.values(root.config, ["voice"], root.voiceSchema)
  readonly property bool voiceEnabled: voice.detected && voiceSettings.enabled === true
  property string voiceTrigger: "tap"      // hold | tap
  property bool voiceDiscard: false        // the user typed while transcribing: the transcript loses
  readonly property string bindingsPath: home + "/.config/hypr/bindings.lua"
  property string bindingsText: ""
  property bool bindingsKnown: false       // read, or confirmed absent: safe to rewrite
  FileView {
    id: bindingsFile
    path: root.bindingsPath
    watchChanges: true
    atomicWrites: true
    printErrors: false
    onLoaded: { root.bindingsText = text(); root.bindingsKnown = true }
    onLoadFailed: function(error) { root.bindingsText = ""; root.bindingsKnown = error === FileViewError.FileNotFound }
    onFileChanged: reload()
  }
  readonly property string voiceBindingsStatus: root.bindingsKnown ? VoiceBindings.status(root.bindingsText, root.voiceSettings.keys) : "missing"
  readonly property string voiceStamp: [voice.detected, voice.version, voice.daemonState, root.voiceBindingsStatus, root.bindingsKnown].join("|")
  function voiceModel() {
    return { schemas: root.voiceSchema, values: root.voiceSettings, detected: voice.detected, version: voice.version, daemonState: voice.daemonState,
             bindings: root.voiceBindingsStatus, bindingsPath: "~/.config/hypr/bindings.lua" }
  }
  readonly property bool dictationMode: !root.dmenuActive && root.scope === "dictation"
  property string dictationPending: ""   // explicit Enter intent: copy | paste
  ClipboardTransfer {
    id: clipboardTransfer
    onCopied: root.cancel(true)
    onFailed: function(message) {
      if (root.opened) root.errorMessage = message
      else Quickshell.execDetached(["notify-send", "Keystroke dictation", message])
    }
  }
  function dictationAccept(alternate) {
    if (clipboardTransfer.busy) return
    if (voice.active) {
      if (!root.dictationPending) root.dictationPending = alternate ? "paste" : "copy"
      root.voiceStop()
    } else clipboardTransfer.submit(search.text, alternate)
  }
  property string voiceRawText: ""
  readonly property bool liveText: voice.active && search.text.length > 0
  function voiceLive(text) {
    if (!root.opened || voice.phase !== "listening" || root.voiceDiscard) return
    if (root.providerViewActive && providerView.item) { if (typeof providerView.item.transcript === "function") providerView.item.transcript(text, false); return }
    root.voiceRawText = String(text || "")
    var t = root.dictationMode ? String(text || "") : String(text || "").replace(/\s+/g, " ").trim()
    if (t === search.text) return
    search.text = t
    search.cursorPosition = t.length
    root.edited()
  }
  function installVoiceBindings() {
    if (!root.bindingsKnown) { root.errorMessage = "Could not read " + root.bindingsPath; return }
    var next = VoiceBindings.apply(root.bindingsText, root.voiceSettings.keys)
    root.bindingsText = next
    bindingsFile.setText(next)
    Quickshell.execDetached(["hyprctl", "reload"])
    root.statusMessage = "Bindings written · Hyprland reloaded"
    root.requery()
  }
  function voiceBegin(trigger) {
    if (!root.voiceEnabled || !root.opened || root.dmenuActive || root.confirmPending || voice.active) return false
    root.voiceTrigger = trigger
    root.voiceDiscard = false
    root.voiceRawText = ""
    root.dictationPending = ""
    if (root.providerViewActive && providerView.item && typeof providerView.item.beginVoice === "function") providerView.item.beginVoice()
    else { search.text = ""; root.edited() }
    root.errorMessage = ""
    root.statusMessage = ""
    var started = voice.start()
    return started
  }
  function voiceStop() { if (voice.phase === "starting" || voice.phase === "listening") voice.stop() }
  function voiceCancel() {
    root.voiceRawText = ""
    root.dictationPending = ""
    root.voiceDiscard = true
    if (voice.active) voice.cancel()
  }
  function voiceTranscribed(raw) {
    if (!root.opened || root.voiceDiscard) return
    if (root.providerViewActive && providerView.item) { if (typeof providerView.item.transcript === "function") providerView.item.transcript(raw, true); return }
    root.voiceRawText = String(raw || "")
    var text = root.dictationMode ? String(raw) : Intent.normalize(raw)
    search.text = text
    search.cursorPosition = text.length
    root.edited()
    if (root.dictationMode) {
      var pendingCopy = root.dictationPending
      root.dictationPending = ""
      root.statusMessage = "Enter copies · Ctrl+Enter pastes"
      if (pendingCopy) clipboardTransfer.submit(text, pendingCopy === "paste")
    } else root.statusMessage = "Transcribed · press ↵ to run"
  }
  function isSuperKey(key) { return key === Qt.Key_Super_L || key === Qt.Key_Super_R || key === Qt.Key_Meta || key === Qt.Key_Hyper_L || key === Qt.Key_Hyper_R }
  function isModifierKey(key) {
    return root.isSuperKey(key) || key === Qt.Key_Shift || key === Qt.Key_Control || key === Qt.Key_Alt || key === Qt.Key_AltGr || key === Qt.Key_CapsLock
  }

  // -------------------------------------------------------------- frecency
  property var usage: ({})
  FileView {
    id: usageFile
    path: root.usagePath
    printErrors: false
    onLoaded: root.usage = Frecency.parse(text())
    onLoadFailed: root.usage = ({})
  }
  Process { id: stateDir; command: ["mkdir", "-p", root.home + "/.local/state/keystroke"]; running: true }
  function remember(row) {
    if (!row.remember) return
    root.usage = Frecency.record(root.usage, Frecency.key(row.providerKey, row.id), Date.now() / 1000)
    usageFile.setText(Frecency.serialize(root.usage))
  }
  function bonusFor(row) {
    return row.remember ? Frecency.bonus(root.usage, Frecency.key(row.providerKey, row.id), Date.now() / 1000) : 0
  }

  // ----------------------------------------------------------------- state
  property bool opened: false
  property string mode: "palette"           // palette | select | input
  readonly property bool dmenuActive: mode === "select" || mode === "input"
  property string dmenuPrompt: ""
  property var dmenuOptions: []
  property string selectionFile: ""
  property string doneFile: ""
  property int dmenuWidth: 300
  property int dmenuMaxHeight: 0
  property bool requestActive: false
  property string fontFamily: Style.font.menuFamily
  property string scope: ""
  property string scopeTitle: ""
  property var history: []
  property var rows: []
  property var uids: []
  property int selected: 0
  property bool selectionTouched: false
  property int generation: 0
  property bool pending: false
  property bool showLoading: false
  property string errorMessage: ""
  property string statusMessage: ""
  property var confirmPending: null       // { message, confirmText, run }
  readonly property var current: rows.length && selected >= 0 && selected < rows.length ? rows[selected] : ({})
  readonly property bool compact: paletteSettings.density !== "comfortable"
  readonly property color accent: paletteSettings.accent === "ember" ? "#ee987e" : paletteSettings.accent === "violet" ? "#b5a0ef" : paletteSettings.accent === "mint" ? "#8bceb4" : Color.accent
  readonly property bool clipboardChoice: root.dictationMode || !!(root.current.action && root.current.action.type === "dictation-copy")
  readonly property bool previewVisible: !dmenuActive && paletteSettings.showPreview !== false && !!(current.preview || current.previewImage || current.swatch)

  // Theme surfaces, same tokens as the stock menu.
  readonly property color background: Color.menu.background
  readonly property color foreground: Color.menu.text
  readonly property color scrim: Color.menu.scrim
  readonly property color selectedBackground: Color.menu.selectedBackground
  readonly property color selectedText: Color.menu.selectedText
  readonly property var borderSpec: Border.surfaceSpec("menu", "border", Color.menu.border, Math.max(1, Style.space(2)))
  readonly property var selectedBorderSpec: Border.surfaceSpec("menu", "selected-border", Color.menu.selectedBorder, 0)
  readonly property color hairline: Util.alpha(foreground, 0.12)
  readonly property color muted: Util.alpha(foreground, 0.55)

  // Type scale for provider views. A view covers the whole card, so it has to
  // carry the palette's own sizes -- including the density bump -- or it reads
  // a step smaller than the results it replaced. Ladder: fontInput is the
  // search field, fontTitle a row title, fontBody a preview body, fontLabel a
  // row subtitle or footer, fontCaption a keycap or the breadcrumb brand.
  readonly property int fontInput: compact ? Style.font.heading : Style.font.heading + 2
  readonly property int fontTitle: compact ? Style.font.title : Style.font.title + 1
  readonly property int fontBody: Style.font.body
  readonly property int fontLabel: Style.font.bodySmall
  readonly property int fontCaption: Style.font.caption
  // Tells a provider view it need not paint its own backdrop; an older
  // host leaves this undefined, so a view can still fall back.
  readonly property bool paintsViewBackdrop: true

  onPendingChanged: { if (pending) loadingDelay.restart(); else { loadingDelay.stop(); showLoading = false } }
  Timer { id: loadingDelay; interval: 180; onTriggered: root.showLoading = root.pending }
  Timer { id: debounce; interval: 16; onTriggered: root.runQuery() }

  Registry { id: providerRegistry; host: root }
  readonly property var registry: providerRegistry
  ListModel { id: resultModel }
  PointerMoveGate { id: pointerGate; referenceItem: card }

  // ---------------------------------------------------------------- opening
  function resetSelection() {
    root.selected = 0
    root.selectionTouched = false
    pointerGate.reset()
  }

  function openRoute(input, payload) {
    root.closeProviderView()
    clipboardTransfer.cancel()
    if (root.dmenuActive && root.requestActive) root.finishRequest(null)
    var route = providerRegistry.bundled[0].routeFor(input)
    if (route.kind === "action") {
      root.cancel()
      Util.execDetached(route.action)
      return
    }
    root.voiceCancel()
    root.mode = "palette"
    root.requestActive = false
    root.history = []
    root.confirmPending = null
    root.errorMessage = ""
    root.statusMessage = ""
    if (payload && payload.scope !== undefined) {
      root.scope = String(payload.scope)
      root.scopeTitle = String(payload.title || "")
    } else if (route.kind === "apps") {
      root.scope = "applications"; root.scopeTitle = "Applications"
    } else if (route.id && route.id !== "root") {
      root.scope = "omarchy/" + route.id; root.scopeTitle = route.label || "Omarchy"
    } else {
      root.scope = ""; root.scopeTitle = ""
    }
    search.text = payload && payload.query ? String(payload.query) : ""
    root.resetSelection()
    root.applyRows([])
    root.opened = true
    root.notifyOpened()
    root.runQuery()
    Qt.callLater(function() {
      search.forceActiveFocus()
      if (root.opened && root.dictationMode && payload && payload.dictate === true) root.voiceBegin("tap")
    })
  }

  function notifyOpened() {
    providerRegistry.rebuild()
    for (var i = 0; i < providerRegistry.entries.length; i++) {
      var p = providerRegistry.entries[i].provider
      if (typeof p.opened === "function") { try { p.opened() } catch (e) { console.warn("keystroke: provider opened() threw", e) } }
    }
    voice.refresh()
  }

  function openDmenu(payload) {
    root.closeProviderView()
    clipboardTransfer.cancel()
    if (root.dmenuActive && root.requestActive) root.finishRequest(null)   // a new caller cancels the previous one
    root.voiceCancel()
    root.mode = payload.mode === "input" ? "input" : "select"
    root.dmenuPrompt = String(payload.prompt || (root.mode === "input" ? "Input" : "Select"))
    root.dmenuOptions = Array.isArray(payload.options) ? payload.options : []
    root.selectionFile = String(payload.selectionFile || "")
    root.doneFile = String(payload.doneFile || "")
    root.requestActive = !!root.doneFile
    root.dmenuWidth = Math.max(1, Number(payload.width || 300))
    root.dmenuMaxHeight = Math.max(0, Number(payload.maxHeight || 0))
    root.scope = ""; root.scopeTitle = root.dmenuPrompt; root.history = []
    root.confirmPending = null
    search.text = ""
    root.resetSelection()
    root.applyRows([])
    root.opened = true
    root.runQuery()
    Qt.callLater(function() { search.forceActiveFocus() })
  }

  function finishRequest(selection) {
    if (!root.requestActive || !root.doneFile) return
    var selectionPath = root.selectionFile, donePath = root.doneFile
    root.requestActive = false
    root.selectionFile = ""
    root.doneFile = ""
    if (selection === null || selection === undefined)
      Quickshell.execDetached(["bash", "-c", ": > " + Util.shellQuote(donePath)])
    else
      Quickshell.execDetached(["bash", "-c", "printf '%s\\n' " + Util.shellQuote(selection) + " > " + Util.shellQuote(selectionPath) + "; : > " + Util.shellQuote(donePath)])
  }

  function cancel(preserveTransfer) {
    root.closeProviderView()
    if (preserveTransfer !== true) clipboardTransfer.cancel()
    if (root.dmenuActive) root.finishRequest(null)
    root.voiceCancel()
    root.opened = false
    root.confirmPending = null
    root.pending = false
    debounce.stop()
  }

  // ---------------------------------------------------------------- queries
  function edited() {
    root.confirmPending = null
    root.resetSelection()
    debounce.restart()
  }
  function setQuery(text) { clipboardTransfer.cancel(); root.voiceCancel(); search.text = String(text || ""); root.edited(); return "ok" }

  // Providers call this when asynchronous results land; the selection is kept.
  function requery() {
    if (!root.opened) return
    debounce.stop()
    root.runQuery()
  }

  function runQuery() {
    if (!root.opened || root.providerViewActive) return
    if (root.dmenuActive) { root.applyRows(root.dmenuRows()); root.pending = false; root.afterRows(); return }
    root.generation++
    var q = root.voiceRawText && !root.dictationMode ? Intent.normalize(root.voiceRawText) : search.text, sc = root.scope
    var owner = sc.split("/")[0]
    var sub = sc.indexOf("/") >= 0 ? sc.slice(owner.length + 1) : ""
    var collected = [], errors = [], pend = false, matchedPatterns = ({})
    var mark = function() { pend = true }
    for (var i = 0; i < providerRegistry.entries.length; i++) {
      var entry = providerRegistry.entries[i]
      if (!root.providerEnabled(entry)) continue
      if (sc && owner !== entry.key) continue
      // Declared patterns run before query(): the provider learns which shapes
      // matched, and the largest boost lifts every row it returns this time.
      var patterns = Patterns.evaluate(entry.patterns, q)
      if (patterns.matched.length) matchedPatterns[entry.key] = patterns.matched
      var ctx = { query: q, rawQuery: root.voiceRawText || search.text, scope: sc, sub: sc ? sub : "", generation: root.generation, settings: root.settingsFor(entry),
                  patterns: patterns, pending: mark, host: root, shell: root.shell, appLibrary: root.appLibrary, omarchyPath: root.omarchyPath }
      try {
        var out = entry.provider.query(ctx) || []
        for (var r = 0; r < out.length && r < 400; r++) {
          var row = root.normalize(out[r], entry, q, patterns.boost)
          if (row) collected.push(row)
        }
      } catch (e) {
        errors.push(entry.provider.name + ": " + e)
        console.warn("keystroke: provider", entry.key, "failed:", e)
      }
    }
    if (root.configError) errors.push(root.configError)
    var ranked = Match.rank(collected, root.bonusFor)
    root.applyRows(ranked.slice(0, 120))
    root.lastPatterns = matchedPatterns
    root.pending = pend
    root.errorMessage = errors.join(" · ")
    root.afterRows()
  }

  property var lastPatterns: ({})           // provider key → matched pattern ids, for inspect()
  function normalize(row, entry, q, boost) {
    if (!row || typeof row !== "object" || typeof row.title !== "string") return null
    var out = {}
    for (var k in row) out[k] = row[k]
    out.id = String(row.id === undefined ? row.title : row.id)
    out.providerKey = entry.key
    out.providerName = entry.provider.name
    out.source = entry.source
    out.uid = entry.key + "/" + out.id
    out.subtitle = String(row.subtitle || "")
    out.icon = String(row.icon || "⌘")
    out.iconFont = String(row.iconFont || "")
    out.iconSource = String(row.iconSource || "")
    out.tint = String(row.tint || "")
    out.section = String(row.section || entry.provider.name)
    out.verb = String(row.verb || (row.action && row.action.type === "navigate" ? "Open" : "Run"))
    out.tier = row.tier === "answer" || row.tier === "fallback" ? row.tier : "item"
    var base = typeof row.score === "number" ? row.score : Match.match(q, row.title, row.keywords || "", row.path || "", row.description || "")
    // A matched provider pattern lifts rows that already match; it never revives a row the matcher dropped.
    out.score = q && base > 0 && boost > 0 ? base + boost : base
    out.accessory = String(row.accessory || "")
    out.badge = String(row.badge || (entry.source === "community" ? "plugin" : ""))
    out.hint = String(row.hint || "")
    out.disabled = row.disabled === true
    out.remember = row.remember === true
    out.confirm = String(row.confirm || "")
    if (q && !(base > 0)) return null
    return out
  }

  function dmenuRows() {
    if (root.mode === "input") return []
    var q = search.text.trim().toLowerCase(), rows = []
    for (var i = 0; i < root.dmenuOptions.length; i++) {
      var parts = String(root.dmenuOptions[i] || "").split("\t")
      var icon = parts.length > 1 ? parts.shift() : ""
      var label = parts.shift() || ""
      var detail = parts.join("\t")
      if (q && label.toLowerCase().indexOf(q) < 0 && detail.toLowerCase().indexOf(q) < 0) continue
      rows.push({ id: String(i), uid: "dmenu/" + i, title: label, subtitle: detail, icon: icon, iconFont: "", iconSource: "", tint: "",
                  section: "", verb: "Select", tier: "item", score: 1, order: i, accessory: "", badge: "", hint: "", disabled: false,
                  remember: false, confirm: "", providerKey: "dmenu", value: detail ? label + "\t" + detail : label })
    }
    return rows
  }

  function display(row, index, previousSection) {
    return { uid: row.uid, title: row.title, subtitle: row.subtitle, icon: row.icon, iconFont: row.iconFont, iconSource: row.iconSource,
             tint: row.tint, section: row.section, sectionStart: row.section !== previousSection, verb: row.verb, accessory: row.accessory,
             disabled: row.disabled, badge: row.badge, answer: row.tier === "answer", hint: row.hint }
  }

  // Reconcile by uid so delegates update in place while typing.
  function applyRows(next) {
    var wanted = ({})
    for (var n = 0; n < next.length; n++) wanted[next[n].uid] = true
    var order = root.uids.slice()
    for (var j = order.length - 1; j >= 0; j--) {
      if (!wanted[order[j]]) { resultModel.remove(j); order.splice(j, 1) }
    }
    var previous = ""
    for (var i = 0; i < next.length; i++) {
      var uid = next[i].uid
      var d = root.display(next[i], i, previous)
      previous = next[i].section
      var at = order.indexOf(uid, i)
      if (at < 0) { resultModel.insert(i, d); order.splice(i, 0, uid) }
      else {
        if (at !== i) { resultModel.move(at, i, 1); order.splice(i, 0, order.splice(at, 1)[0]) }
        resultModel.set(i, d)
      }
    }
    root.uids = order
    root.rows = next
  }

  function afterRows() {
    if (root.selectionTouched) {
      var keep = root.current && root.current.uid
      var found = -1
      for (var i = 0; i < root.rows.length && keep; i++) if (root.rows[i].uid === keep) { found = i; break }
      root.selected = found >= 0 ? found : Math.max(0, Math.min(root.selected, root.rows.length - 1))
    } else {
      root.selected = 0
      resultList.positionViewAtBeginning()
    }
  }

  // ------------------------------------------------------------- navigation
  function navigate(nextScope, title) {
    clipboardTransfer.cancel()
    root.voiceCancel()
    root.history = root.history.concat([{ scope: root.scope, title: root.scopeTitle, query: search.text }])
    root.scope = nextScope
    root.scopeTitle = title || ""
    search.text = ""
    root.resetSelection()
    root.applyRows([])
    root.runQuery()
    resultList.positionViewAtBeginning()
  }

  function goBack() {
    clipboardTransfer.cancel()
    if (root.confirmPending) { root.confirmPending = null; return true }
    if (root.dmenuActive) return false
    var priorRawQuery = root.providerViewRawQuery
    root.voiceCancel()
    if (root.providerViewActive) {
      root.closeProviderView()
      root.voiceRawText = priorRawQuery
      root.runQuery()
      search.forceActiveFocus()
      return true
    }
    if (root.history.length) {
      var prior = root.history[root.history.length - 1]
      root.history = root.history.slice(0, -1)
      root.scope = prior.scope; root.scopeTitle = prior.title; search.text = prior.query
    } else if (root.scope) {
      root.scope = ""; root.scopeTitle = ""; search.text = ""
    } else return false
    root.resetSelection()
    root.applyRows([])
    root.runQuery()
    resultList.positionViewAtBeginning()
    return true
  }

  function select(delta) {
    if (!root.rows.length) return
    root.selectionTouched = true
    pointerGate.reset()
    root.selected = (root.selected + Number(delta) + root.rows.length) % root.rows.length
    resultList.positionViewAtIndex(root.selected, ListView.Contain)
  }

  function selectPage(delta) {
    if (!root.rows.length) return
    root.selectionTouched = true
    pointerGate.reset()
    root.selected = Math.max(0, Math.min(root.rows.length - 1, root.selected + Number(delta)))
    resultList.positionViewAtIndex(root.selected, ListView.Contain)
  }

  function selectFromPointer(index, item, mouse) {
    if (!pointerGate.moved(item, mouse)) return
    root.selectionTouched = true
    root.selected = index
  }

  // --------------------------------------------------------------- actions
  // Ctrl+↵ is the alternate activation: a row's altAction when it has one,
  // otherwise its action; the provider's activate() sees ctx.alternate.
  function activate(alternate) {
    if (root.confirmPending) return
    if (root.dictationMode) { root.dictationAccept(alternate); return }
    if (debounce.running) { debounce.stop(); root.runQuery() }
    if (root.dmenuActive) {
      if (root.mode === "input") { root.applyDmenuSelection(search.text); return }
      if (root.rows.length) root.applyDmenuSelection(root.current.value)
      return
    }
    var row = root.current
    if (!row || !row.uid || row.disabled) return
    var entry = root.registryEntry(row.providerKey)
    if (!entry) return
    var effect = alternate && row.altAction ? row.altAction : row.action
    if (typeof entry.provider.activate === "function") {
      try { effect = entry.provider.activate(row, { host: root, settings: root.settingsFor(entry), alternate: alternate === true }) || effect } catch (e) { root.errorMessage = entry.provider.name + ": " + e; return }
    }
    if (!effect) return
    var run = function() { root.remember(row); root.perform(effect, row) }
    if (row.confirm) root.confirmPending = { message: row.confirm, confirmText: "Confirm", run: run }
    else run()
  }

  function applyDmenuSelection(value) {
    root.opened = false
    root.finishRequest(value)
  }

  function requestUninstall() {
    var row = root.current
    if (!row || !row.appId || !root.appLibrary) return
    var id = row.appId, name = row.title
    root.confirmPending = { message: "Do you want to uninstall " + name + "?", confirmText: "Uninstall",
                            run: function() { root.cancel(); root.appLibrary.remove(id, name) } }
  }

  function perform(effect, row) {
    var type = effect.type
    if (type === "noop") return
    if (type === "provider-view") { root.showProviderView(effect.provider); return }
    if (type === "dictate") {
      root.navigate("dictation", "Dictate to Clipboard")
      if (!root.voiceBegin("tap")) root.errorMessage = "Voice is unavailable; check Settings › Voice"
      return
    }
    if (type === "dictation-copy") { clipboardTransfer.submit(effect.text, effect.paste); return }
    if (type === "navigate") { root.navigate(effect.scope, effect.title || row.title); return }
    if (type === "setting") {
      try {
        root.saveConfig(Settings.withValue(root.config, effect.path, effect.key, effect.value, effect.schema))
        root.statusMessage = "Saved"
        if (root.scope.split("/").length > 2 && effect.schema && effect.schema.type === "enum") root.goBack()
        else root.requery()
      } catch (e) { root.errorMessage = String(e.message || e) }
      return
    }
    if (type === "compound") {
      for (var i = 0; i < effect.actions.length; i++) root.perform(effect.actions[i], row)
      return
    }
    if (type === "notify") { Quickshell.execDetached([root.omarchyPath + "/bin/omarchy-notification-send", "-g", String(effect.glyph || "󰵅"), String(effect.headline || ""), String(effect.body || "")]); return }
    if (type === "voice-bindings") { root.installVoiceBindings(); return }
    if (type === "close") { root.cancel(); return }
    // Everything below leaves the palette: drop the keyboard-grabbing layer first, like the stock menu.
    root.cancel()
    if (type === "shell") Util.execDetached(String(effect.command || ""))
    else if (type === "exec") Util.execArgv((effect.argv || []).map(String))
    else if (type === "url") Util.execArgv(["xdg-open", String(effect.url || "")])
    else if (type === "copy") Quickshell.execDetached(["wl-copy", "--", String(effect.text === undefined ? "" : effect.text)])
    else if (type === "app" && root.appLibrary) root.appLibrary.launch(effect.id, effect.name)
    else if (type === "edit") {
      if (!root.configError) configFile.setText(Settings.serialize(root.config))
      Util.execArgv(["xdg-open", root.configPath])
    }
  }


  function inspectConversation() {
    var c = providerRegistry.bundled.find(x => x.provider.id === "codex").session
    return JSON.stringify({ threadId: c.threadId, phase: c.phase, ready: c.server.ready, error: c.error, activity: c.activity, messages: c.messages, draft: c.draft, firstTextMs: c.firstTextMs, lastMs: c.lastMs })
  }
  function inspectApplications() {
    var entries = root.appLibrary ? root.appLibrary.sortedEntries("") : []
    return JSON.stringify({ shell: !!root.shell, shellPluginId: root.shell ? root.shell.pluginId : "",
      manifestId: root.manifest ? root.manifest.id : "", manifestKinds: root.manifest ? root.manifest.kinds : [],
      library: !!root.appLibrary, sharedLibrary: !!applicationLibrary.sharedLibrary, entries: entries.length,
      providerLibrary: !!providerRegistry.bundled[1].library,
      providerEntries: providerRegistry.bundled[1].library ? providerRegistry.bundled[1].library.sortedEntries("").length : -1 })
  }
  function inspect() {
    var appEntries = root.appLibrary ? root.appLibrary.sortedEntries("") : []
    return JSON.stringify({ opened: root.opened, mode: root.mode, view: root.activeProviderKey, scope: root.scope, query: search.text, count: root.rows.length,
      titles: root.rows.map(function(r) { return r.title }), selected: root.selected, pending: root.pending, patterns: root.lastPatterns,
      current: { uid: root.current.uid || "", icon: root.current.icon || "", iconSource: root.current.iconSource || "", badge: root.current.badge || "", tier: root.current.tier || "" },
      modelCount: resultModel.count, providers: providerRegistry.entries.map(function(e) { return e.key }), problems: providerRegistry.problems,
      applications: { library: !!root.appLibrary, entries: appEntries.length },
      error: root.errorMessage, configError: root.configError, status: root.statusMessage,
      voice: { backend: "voxtype", state: voice.phase, trigger: root.voiceTrigger, enabled: root.voiceEnabled, detected: voice.detected, version: voice.version,
               command: voice.command, daemon: voice.daemonState, bindings: root.voiceBindingsStatus, frames: voice.history.length, live: voice.liveText } })
  }

  // ------------------------------------------------------------------ view
  readonly property int headerHeight: Style.space(compact ? 66 : 78)
  readonly property int crumbHeight: Style.space(30)
  readonly property int footerHeight: Style.space(46)
  readonly property int rowHeight: Style.space(compact ? 46 : 56)
  readonly property int rowSpacing: Style.space(3)
  readonly property int dmenuRowsHeight: {
    var count = Math.max(1, resultModel.count)
    var maxRows = root.dmenuMaxHeight > 0 ? Math.max(1, Math.floor(Style.space(root.dmenuMaxHeight) / (rowHeight + rowSpacing))) : 12
    return Math.min(count, maxRows) * (rowHeight + rowSpacing)
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "omarchy-menu"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    Rectangle { anchors.fill: parent; color: root.scrim; MouseArea { anchors.fill: parent; onClicked: root.cancel() } }

    BorderSurface {
      id: card
      width: Math.min(root.dmenuActive ? Style.space(root.dmenuWidth) : Style.space(root.compact ? 640 : 760), panel.width - Style.gapsOut * 2)
      height: root.dmenuActive
        ? Math.min(root.headerHeight + (root.mode === "input" ? Style.space(12) : root.dmenuRowsHeight + Style.space(20)), panel.height - Style.gapsOut * 2)
        : Math.min(Style.space(root.compact ? 540 : 580), panel.height - Style.gapsOut * 2)
      anchors.horizontalCenter: parent.horizontalCenter
      y: root.dmenuActive ? Math.max(Style.gapsOut, Math.round((panel.height - height) / 2)) : Math.max(Style.gapsOut, Math.round((panel.height - height) * 0.38))
      radius: Style.cornerRadius
      color: root.background
      borderSpec: root.borderSpec
      clip: true
      Accessible.role: Accessible.Dialog
      Accessible.name: "Keystroke command palette"
      MouseArea { anchors.fill: parent; onClicked: {} }

      // A provider view covers the palette, so the host paints the backdrop
      // it needs and keeps both inside the card's border. Filling the card
      // outright would paint over the border ring, which BorderSurface draws
      // as the surface itself (or as an overlay child below this z).
      Rectangle {
        id: viewBackdrop
        visible: !!providerView.item
        z: 4
        anchors.fill: parent
        anchors.topMargin: card.borderTop; anchors.rightMargin: card.borderRight
        anchors.bottomMargin: card.borderBottom; anchors.leftMargin: card.borderLeft
        radius: Math.max(0, card.radius - Math.max(card.borderTop, card.borderLeft))
        color: root.background
      }

      Loader {
        id: providerView
        anchors.fill: viewBackdrop
        z: 5
        onLoaded: { item.host = root; if (typeof item.focusInput === "function") Qt.callLater(item.focusInput) }
      }

      // Header: search field
      Item {
        id: header
        visible: !root.providerViewActive
        x: Style.space(root.compact ? 20 : 24); y: 0
        width: parent.width - x * 2
        height: root.headerHeight
        Item {
          id: glyph
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          width: Style.space(22); height: width
          Rectangle { visible: !voice.active; x: 1; y: 1; width: Style.space(15); height: width; radius: width / 2; color: "transparent"; border.color: root.accent; border.width: 1.8 }
          Rectangle { visible: !voice.active; x: Style.space(13); y: Style.space(13); width: Style.space(9); height: 1.8; radius: 0.9; rotation: 45; transformOrigin: Item.Left; color: root.accent }
          // Recording dot, swelling with the microphone.
          Rectangle {
            visible: voice.active
            anchors.centerIn: parent
            width: Style.space(10); height: width; radius: width / 2
            color: voice.phase === "listening" ? root.accent : Util.alpha(root.accent, 0.55)
            scale: voice.phase === "listening" ? 1 + 0.6 * voice.level : 1
            Behavior on scale { NumberAnimation { duration: 60 } }
          }
        }
        VoiceWave {
          id: wave
          visible: voice.active
          anchors.right: escCap.left
          anchors.rightMargin: Style.space(12)
          anchors.verticalCenter: parent.verticalCenter
          // Switching away from two horizontal anchors does not restore a
          // constant width. Keep one anchor and bind both widths explicitly.
          width: root.liveText ? Math.min(Style.space(96), fieldWidth * 0.22) : fieldWidth
          readonly property real fieldWidth: Math.max(0, escCap.x - Style.space(12) - glyph.x - glyph.width - Style.space(14))
          height: Style.space(40)
          mode: voice.phase
          level: voice.level
          history: voice.history
          accent: root.accent
          foreground: root.foreground
        }
        TextInput {
          id: search
          anchors.left: glyph.right
          anchors.leftMargin: Style.space(14)
          anchors.right: root.liveText ? wave.left : escCap.left
          anchors.rightMargin: Style.space(12)
          anchors.verticalCenter: parent.verticalCenter
          height: Style.space(40)
          verticalAlignment: TextInput.AlignVCenter
          color: root.foreground
          selectionColor: Util.alpha(root.accent, 0.45)
          selectedTextColor: root.foreground
          font.family: root.fontFamily
          font.pixelSize: root.fontInput
          selectByMouse: true
          clip: true
          focus: true
          opacity: voice.active && !root.liveText ? 0 : 1   // the string takes the field until words arrive; focus and keys stay here
          Accessible.name: root.dmenuActive ? root.dmenuPrompt : "Search commands, apps and extensions"
          Text {
            anchors.fill: parent
            verticalAlignment: Text.AlignVCenter
            text: root.dictationMode ? "Speak or edit your dictation…" : root.dmenuActive ? root.dmenuPrompt + "…" : root.scope ? "Search " + root.scopeTitle.toLowerCase() + "…" : "What would you like to do?"
            color: Util.alpha(root.foreground, 0.42)
            font: parent.font
            visible: !parent.text && !parent.preeditText && !voice.active
            elide: Text.ElideRight
          }
          onTextEdited: { clipboardTransfer.cancel(); root.voiceCancel(); root.edited() }
          Keys.priority: Keys.BeforeItem
          Keys.onReleased: function(event) {
            // Hold mode ends when the modifier comes up (Hyprland swallows the
            // hotkey's own release, and its release bind only fires while the
            // modifier is still down). A tap's release must not end anything.
            if (voice.active && root.voiceTrigger === "hold" && root.isSuperKey(event.key)) { root.voiceStop(); event.accepted = true }
          }
          Keys.onPressed: function(event) {
            if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && event.isAutoRepeat) { event.accepted = true; return }
            if (root.confirmPending) { confirmDialog.handleKey(event); event.accepted = true; return }
            if (voice.active) {
              if (event.key === Qt.Key_Escape) { root.cancel(); event.accepted = true; return }
              if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                if (root.dictationMode) root.dictationAccept(!!(event.modifiers & Qt.ControlModifier))
                else root.voiceStop()
                event.accepted = true; return
              }
              if (root.isModifierKey(event.key)) { event.accepted = true; return }
              root.voiceCancel() // typing and navigation supersede speech immediately
            }
            var ctrl = event.modifiers & Qt.ControlModifier
            var atEnd = cursorPosition === text.length
            if (event.key === Qt.Key_Escape) { root.cancel(); event.accepted = true }
            else if (ctrl && event.key === Qt.Key_U) { text = ""; root.edited(); event.accepted = true }
            else if (event.key === Qt.Key_Down || (ctrl && event.key === Qt.Key_N)) { root.select(1); event.accepted = true }
            else if (event.key === Qt.Key_Up || (ctrl && event.key === Qt.Key_P)) { root.select(-1); event.accepted = true }
            else if (event.key === Qt.Key_PageDown) { root.selectPage(6); event.accepted = true }
            else if (event.key === Qt.Key_PageUp) { root.selectPage(-6); event.accepted = true }
            else if (ctrl && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) { root.activate(true); event.accepted = true }
            else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { root.activate(); event.accepted = true }
            else if (event.key === Qt.Key_Right && (atEnd || !text) && !root.dmenuActive && root.rows.length) { root.activate(); event.accepted = true }
            else if ((event.key === Qt.Key_Left || event.key === Qt.Key_Backspace) && !text && !preeditText && (root.scope || root.history.length)) { root.goBack(); event.accepted = true }
            else if (event.key === Qt.Key_Delete && !text && root.current.appId) { root.requestUninstall(); event.accepted = true }
            else if (ctrl && event.key === Qt.Key_Comma && !root.dmenuActive) { root.navigate("settings", "Settings"); event.accepted = true }
            else if (ctrl && event.key === Qt.Key_K && !root.dmenuActive) {
              var key = root.current.providerKey && root.current.providerKey !== "settings" ? "settings/" + root.current.providerKey : "settings"
              root.navigate(key, root.current.providerName || "Settings")
              event.accepted = true
            }
          }
        }
        Keycap { id: escCap; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; label: "esc"; foreground: root.foreground }
      }
      Rectangle { x: 0; y: root.headerHeight; width: parent.width; height: 1; color: root.hairline }

      // Breadcrumb line (palette mode)
      Row {
        id: crumbs
        visible: !root.dmenuActive
        x: Style.space(root.compact ? 22 : 26); y: root.headerHeight + Style.space(8)
        height: root.crumbHeight
        spacing: Style.space(10)
        Text { id: brand; anchors.verticalCenter: parent.verticalCenter; text: "OMARCHY"; textFormat: Text.PlainText; color: root.accent; font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.letterSpacing: 2; font.weight: Font.Bold }
        Text { anchors.baseline: brand.baseline; text: root.scope ? "›" : "/"; textFormat: Text.PlainText; color: Util.alpha(root.foreground, 0.35); font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall }
        Text {
          anchors.baseline: brand.baseline
          text: root.scope ? root.scopeTitle : search.text ? "Search results" : "Apps, commands, answers"
          textFormat: Text.PlainText
          color: root.muted; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall
        }
      }

      // Results and preview
      Item {
        id: content
        x: Style.space(12)
        y: root.dmenuActive ? root.headerHeight + Style.space(10) : root.headerHeight + root.crumbHeight + Style.space(10)
        width: parent.width - Style.space(24)
        height: parent.height - y - (root.dmenuActive ? Style.space(10) : root.footerHeight + Style.space(10))

        ListView {
          id: resultList
          anchors.left: parent.left
          anchors.top: parent.top
          anchors.bottom: parent.bottom
          width: root.previewVisible ? Math.round(parent.width * 0.55) : parent.width
          model: resultModel
          clip: true
          spacing: root.rowSpacing
          boundsBehavior: Flickable.StopAtBounds
          currentIndex: root.selected
          cacheBuffer: root.rowHeight * 4
          delegate: Column {
            id: delegateRoot
            required property int index
            required property string uid
            required property string title
            required property string subtitle
            required property string icon
            required property string iconFont
            required property string iconSource
            required property string tint
            required property string section
            required property bool sectionStart
            required property string verb
            required property string accessory
            required property bool disabled
            required property string badge
            required property bool answer
            required property string hint
            width: resultList.width
            // The idle root lists one row per provider, so headers would label single items there;
            // they return as soon as a query or a scope groups real sets.
            readonly property bool showHeader: !root.dmenuActive && (!!root.scope || !!search.text) && sectionStart && !!section
            Item {
              width: parent.width
              height: delegateRoot.showHeader ? Style.space(root.compact ? 22 : 26) : 0
              visible: delegateRoot.showHeader
              Text {
                x: Style.space(14); anchors.bottom: parent.bottom; anchors.bottomMargin: Style.space(3)
                text: delegateRoot.section
                textFormat: Text.PlainText
                color: Util.alpha(root.foreground, 0.5)
                font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.weight: Font.Medium; font.letterSpacing: 0.5
              }
            }
            ResultRow {
              width: parent.width
              title: delegateRoot.title; subtitle: delegateRoot.subtitle; icon: delegateRoot.icon; iconFont: delegateRoot.iconFont
              iconSource: delegateRoot.iconSource; tint: delegateRoot.tint; verb: delegateRoot.verb; accessory: delegateRoot.accessory
              badge: delegateRoot.badge; hint: delegateRoot.hint; disabled: delegateRoot.disabled; answer: delegateRoot.answer
              compact: root.compact
              selected: root.selected === delegateRoot.index
              accent: root.accent; foreground: root.foreground
              selectedBackground: root.selectedBackground; selectedText: root.selectedText; selectedBorderSpec: root.selectedBorderSpec
              onHovered: function(item, mouse) { root.selectFromPointer(delegateRoot.index, item, mouse) }
              onActivated: { root.selectionTouched = true; root.selected = delegateRoot.index; root.activate() }
            }
          }
        }
        Rectangle { visible: root.previewVisible; x: resultList.width + Style.space(12); width: 1; height: parent.height - Style.space(12); color: root.hairline }
        PreviewPane {
          visible: root.previewVisible
          x: resultList.width + Style.space(30)
          width: parent.width - x - Style.space(10)
          height: parent.height
          row: root.current
          compact: root.compact
          accent: root.accent
          foreground: root.foreground
        }
        Column {
          visible: root.rows.length === 0 && root.mode !== "input" && (!root.pending || root.showLoading)
          anchors.centerIn: parent
          spacing: Style.space(12)
          Text { anchors.horizontalCenter: parent.horizontalCenter; text: "✳"; color: root.accent; font.pixelSize: Style.space(40) }
          Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.pending ? "Finding your next move…" : search.text ? "No matches for “" + search.text + "”" : root.scope === "clipboard" ? "Your clipboard is empty" : root.scope === "files" ? "Type to search your home folder" : "Nothing here yet"
            textFormat: Text.PlainText; color: root.foreground; opacity: 0.8; font.family: root.fontFamily; font.pixelSize: Style.font.title
          }
          Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.scope === "converter" ? "Try 2m in feet or 10 am in London" : root.scope === "calculator" ? "Try sqrt(144) + 15% of 80" : root.dmenuActive ? "" : "Search by name. Follow your curiosity."
            textFormat: Text.PlainText; color: root.muted; font.family: root.fontFamily; font.pixelSize: Style.font.body
          }
        }
      }

      // Footer (palette mode)
      Rectangle { visible: !root.dmenuActive; x: 0; y: parent.height - root.footerHeight; width: parent.width; height: 1; color: root.hairline }
      Item {
        visible: !root.dmenuActive
        x: Style.space(22); y: parent.height - root.footerHeight; width: parent.width - Style.space(44); height: root.footerHeight
        Row {
          anchors.verticalCenter: parent.verticalCenter; spacing: Style.space(8)
          Text {
            text: voice.phase === "listening" ? (root.voiceTrigger === "hold" ? "Listening… release to finish" : "Listening… tap the hotkey again or press ↵ to finish")
                : voice.phase === "transcribing" ? "Finishing transcript…" : voice.phase === "starting" ? "Starting voxtype…"
                : root.pending && root.showLoading ? "Searching…" : root.errorMessage ? "Needs attention: " + root.errorMessage : root.statusMessage || (root.current.providerName ? root.current.providerName : "Keystroke")
            textFormat: Text.PlainText; elide: Text.ElideRight; width: Math.min(implicitWidth, card.width * 0.5)
            color: root.errorMessage ? Color.urgent : root.muted; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall
            anchors.verticalCenter: parent.verticalCenter
          }
        }
        Row {
          anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: Style.space(8)
          Text { text: root.dictationMode ? "Copy" : voice.active ? "Finish" : root.current.verb || "Select"; textFormat: Text.PlainText; color: Util.alpha(root.foreground, 0.8); font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall; anchors.verticalCenter: parent.verticalCenter }
          Keycap { label: "↵"; bright: true; foreground: root.foreground }
          Item { width: Style.space(8); height: 1 }
          Text { text: root.clipboardChoice ? "Paste" : root.compact ? "Settings" : "Provider settings"; textFormat: Text.PlainText; color: root.muted; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall; anchors.verticalCenter: parent.verticalCenter }
          Keycap { label: root.clipboardChoice ? "ctrl ↵" : "ctrl K"; foreground: root.foreground }
        }
      }

      ConfirmDialog {
        id: confirmDialog
        anchors.fill: parent
        z: 10
        opened: root.confirmPending !== null
        message: root.confirmPending ? root.confirmPending.message : ""
        confirmText: root.confirmPending ? root.confirmPending.confirmText : "Confirm"
        background: root.background
        foreground: root.foreground
        scrim: root.scrim
        selectedBackground: root.selectedBackground
        selectedText: root.selectedText
        fontFamily: root.fontFamily
        cornerRadius: Style.cornerRadius
        onCanceled: { root.confirmPending = null; Qt.callLater(function() { search.forceActiveFocus() }) }
        onConfirmed: { var run = root.confirmPending ? root.confirmPending.run : null; root.confirmPending = null; if (run) run() }
      }
    }
  }
}
