pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "core/Translate.js" as Translate

// Translate: Google Translate inside the Keystroke command palette, keyless.
//
// Keystroke creates this object inside omarchy-shell when the user turns the
// extension on, injects `shell`, `extension` and `omarchyPath`, reads
// `provider`, and destroys the object when the extension is turned off. The
// decisions (grammar, request, parsing, rows) are in core/Translate.js; this
// file owns what has side effects: curl processes, the debounce, the cache,
// the selection probe and the editor view's draft.
//
// One request per (text, source, target) after a 350 ms typing pause; the
// first answer names the detected language, and the other targets and the
// reverse translation are fetched from there. Responses are cached for the
// session, superseded requests are killed, and an HTTP 429 pauses requests
// for a minute rather than retrying.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var host: null            // the palette, captured from ctx on each query
  property var settings: Translate.defaults()
  readonly property string key: extension && extension.id ? String(extension.id) : Translate.DEFAULT_KEY
  readonly property string iconSource: String(Qt.resolvedUrl("assets/icon.svg"))
  readonly property var targets: Translate.targetList(settings.targets)

  readonly property var provider: ({
    apiVersion: 1,
    name: Translate.NAME,
    icon: Translate.ICON,
    iconSource: root.iconSource,
    color: Translate.COLOR,
    description: "Google Translate without an account: tr bonjour, bonjour to english, every target at once in an editor",
    prefix: "tr",
    patterns: Translate.PATTERNS,
    settings: Translate.SETTINGS,
    view: root.view,
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) },
    opened: function() { root.opened() },
    dismiss: function() { root.setSubject(null, false) }
  })
  readonly property Component view: Component { TranslateView { service: root } }

  // ------------------------------------------------------------------ cache
  // (text, source, target) → a parsed response or { error, at }. Errors expire
  // so a network hiccup is retried on the next keystroke; answers stay for
  // the session, oldest out first past CACHE_LIMIT.
  property var cache: ({})
  property var cacheOrder: []
  function lookup(text, from, to) {
    var v = cache[Translate.cacheKey(text, from, to)]
    if (v && v.error && v.at + 30000 < Date.now()) return undefined
    return v
  }
  function busy(text, from, to) { return !!inflight[Translate.cacheKey(text, from, to)] }
  function store(k, value) {
    if (cache[k] === undefined) {
      cacheOrder.push(k)
      while (cacheOrder.length > Translate.CACHE_LIMIT) delete cache[cacheOrder.shift()]
    }
    cache[k] = value
  }

  // ---------------------------------------------------------------- subject
  // What is being translated right now: the typed query or the editor draft.
  // Selection jobs (copy/paste the translated selection) run beside it and
  // finish after the palette has closed.
  property var subject: null          // { text, from, to } or null
  property var jobs: []
  property var inflight: ({})
  property double blockedUntil: 0
  property int fetches: 0
  signal translated()
  readonly property Timer debounce: Timer { interval: Translate.DEBOUNCE_MS; onTriggered: root.sync() }

  function needs(list) {
    for (var i = 0; i < list.length; i++) if (lookup(list[i].text, list[i].from, list[i].to) === undefined) return true
    return false
  }
  function setSubject(next, immediate) {
    var same = !!next === !!subject && (!next || (next.text === subject.text && next.from === subject.from && next.to === subject.to))
    subject = next
    if (!next) { debounce.stop(); sync(); return }
    if (same) return
    if (immediate) sync()
    else if (needs(Translate.needed(next, targets, settings, lookup, false))) debounce.restart()
    else sync()
  }

  // Start what the subject and the jobs need and are not cached or in flight;
  // kill what is in flight and no longer needed.
  function sync() {
    var wanted = {}, list = subject ? Translate.needed(subject, targets, settings, lookup, false) : [], i
    for (i = 0; i < jobs.length; i++) list = list.concat(Translate.needed(jobs[i], targets, settings, lookup, true))
    for (i = 0; i < list.length; i++) wanted[list[i].key] = list[i]
    var stale = Object.keys(inflight).filter(function(k) { return !wanted[k] })
    for (i = 0; i < stale.length; i++) { var p = inflight[stale[i]]; delete inflight[stale[i]]; p.cancelled = true; p.signal(15) }
    if (blockedUntil > Date.now()) return
    for (i = 0; i < list.length; i++) {
      var r = list[i]
      if (lookup(r.text, r.from, r.to) !== undefined || inflight[r.key]) continue
      var proc = fetcher.createObject(root, { key: r.key })
      proc.command = Translate.requestArgv(r.text, r.from, r.to, settings.proxy)
      inflight[r.key] = proc
      fetches++
      proc.running = true
    }
  }

  readonly property Component fetcher: Component {
    Process {
      id: proc
      property string key: ""
      property bool cancelled: false
      property bool done: false
      stdout: StdioCollector { onStreamFinished: root.finished(proc, text) }
      onExited: function(code) { root.exited(proc, code) }
    }
  }
  function finished(proc, output) {
    if (proc.cancelled || proc.done) return
    var parts = Translate.splitStatus(output)
    if (parts.status === 0) return                       // curl failed before answering; exited() reports the code
    proc.done = true
    delete inflight[proc.key]
    if (parts.status === 429) {
      blockedUntil = Date.now() + Translate.BACKOFF_MS       // the answer row says so; no retry loop
    } else if (parts.status >= 200 && parts.status < 300) {
      var parsed = Translate.parseResponse(parts.body)
      if (parsed) store(proc.key, parsed)
      else {
        console.log("translate: unparseable body: " + parts.body.slice(0, 200))
        store(proc.key, { error: "Translation unavailable", at: Date.now() })
        if (host) host.errorMessage = "Translate: Google's answer could not be read; the endpoint may have changed"
      }
    } else store(proc.key, { error: "Google answered HTTP " + parts.status, at: Date.now() })
    settle()
  }
  function exited(proc, code) {
    if (!proc.cancelled && !proc.done) {
      proc.done = true
      delete inflight[proc.key]
      if (code !== 0) {
        store(proc.key, { error: "Translation failed (curl exit " + code + ")", at: Date.now() })
        if (host) host.errorMessage = "Translate: curl exited with code " + code
      }
      settle()
    }
    Qt.callLater(function() { proc.destroy() })
  }
  function settle() {
    sync()
    deliverJobs()
    translated()
    if (host && host.opened) host.requery({ catalog: false, provider: key })
  }

  // ------------------------------------------------------------- selection
  // "Copy/Paste the translated selection" rows close the palette at once and
  // deliver when the answer lands, with a notification either way.
  function deliverJobs() {
    var keep = []
    for (var i = 0; i < jobs.length; i++) {
      var job = jobs[i], v = Translate.resolveSubject(job, targets, settings, lookup, busy)
      if (v.main.text) {
        Quickshell.execDetached(job.paste ? Translate.pasteArgv(v.main.text) : ["wl-copy", "--", v.main.text])
        notify(job.paste ? "Pasted the translation" : "Translation copied", Translate.ellipsis(v.main.text, 120))
      } else if (v.main.error) notify("Translation failed", v.main.error)
      else keep.push(job)
    }
    if (keep.length !== jobs.length) jobs = keep
  }
  function notify(headline, body) {
    Quickshell.execDetached([omarchyPath + "/bin/omarchy-notification-send", "-g", Translate.ICON, headline, body])
  }

  property string selection: ""
  readonly property Process selectionProbe: Process {
    // The primary selection first, the clipboard when there is none; text only.
    command: ["sh", "-c", "wl-paste -p -n -t text 2>/dev/null || wl-paste -n -t text 2>/dev/null || true"]
    stdout: StdioCollector { onStreamFinished: root.selectionRead(text) }
  }
  function selectionRead(text) {
    var next = Translate.clamp(text)
    if (next === selection) return
    selection = next
    if (host && host.opened) host.requery({ catalog: false, provider: key })
  }

  property bool canSpeak: false
  property bool speakProbed: false
  readonly property Process speakProbe: Process {
    command: ["sh", "-c", "command -v mpv"]
    onExited: function(code) { root.canSpeak = code === 0 }
  }

  function opened() {
    // A host with providerSettings() gives the saved values before the first query lands.
    if (host && typeof host.providerSettings === "function") { var fresh = host.providerSettings(key); if (fresh) settings = fresh }
    if (settings.selection !== false && !selectionProbe.running) selectionProbe.running = true
    if (settings.speak && !speakProbed) { speakProbed = true; speakProbe.running = true }
  }

  // ----------------------------------------------------------------- palette
  function query(ctx) {
    host = ctx.host
    settings = ctx.settings
    if (settings.speak && !speakProbed) { speakProbed = true; speakProbe.running = true }
    var scoped = ctx.scope === key
    if (ctx.scope && !scoped && ctx.scope !== key + "/targets") return []
    // The host recognises the declared prefix and hands over the rest (ctx.command);
    // the natural "bonjour to english" form arrives through the declared pattern.
    var command = ctx.command || null
    var matched = !!command || !!(ctx.patterns && ctx.patterns.matched && ctx.patterns.matched.length)
    var req = command ? Translate.parse(command.rest, false, true) : ctx.scope && !scoped ? null : Translate.parse(ctx.query, scoped)
    var now = Date.now()
    if (req && req.text.length >= Translate.MIN_CHARS && (scoped || matched)) {
      var next = { text: req.text, from: Translate.sourceCode(settings), to: req.to }
      setSubject(next, false)
      if (blockedUntil <= now && needs(Translate.needed(next, targets, settings, lookup, false))) ctx.pending()
    } else if (!scoped || !req || !req.text) setSubject(null, false)
    return Translate.rows({ query: ctx.query, scope: ctx.scope, key: key, iconSource: iconSource, settings: settings, targets: targets, matched: matched,
                            selection: selection, canSpeak: canSpeak, now: now, blockedUntil: blockedUntil, lookup: lookup, busy: busy,
                            req: ctx.scope && !scoped ? undefined : req, prefix: command ? command.prefix : "" })
  }

  function activate(row, ctx) {
    var effect = ctx.alternate && row.altAction ? row.altAction : row.action
    if (!effect) return effect
    if (effect.type === "translate-view") {
      draft = String(effect.text || "")
      draftTo = String(effect.to || "")
      setSubject(draft.length >= Translate.MIN_CHARS ? { text: draft, from: Translate.sourceCode(settings), to: draftTo } : null, true)
      return { type: "provider-view", provider: key }
    }
    if (effect.type === "translate-selection") {
      jobs = jobs.concat([{ text: String(effect.text || ""), from: Translate.sourceCode(settings), to: "", paste: effect.paste === true }])
      sync()
      deliverJobs()
      return { type: "close" }
    }
    if (effect.type === "translate-retry") {
      if (host && typeof host.setQuery === "function") { host.setQuery(effect.query); return { type: "noop" } }
      draft = String(effect.text || "")
      draftTo = ""
      setSubject({ text: draft, from: Translate.sourceCode(settings), to: "" }, true)
      return { type: "provider-view", provider: key }
    }
    return effect
  }

  // -------------------------------------------------------------------- view
  property string draft: ""
  property string draftTo: ""
  function setDraft(text) {
    draft = String(text || "")
    var t = Translate.clamp(draft)
    setSubject(t.length >= Translate.MIN_CHARS ? { text: t, from: Translate.sourceCode(settings), to: draftTo } : null, false)
  }
  function viewState() {
    var t = Translate.clamp(draft)
    if (t.length < Translate.MIN_CHARS) return null
    return Translate.resolveSubject({ text: t, from: Translate.sourceCode(settings), to: draftTo }, targets, settings, lookup, busy)
  }

  Component.onDestruction: {
    debounce.stop()
    var keys = Object.keys(inflight)
    for (var i = 0; i < keys.length; i++) { inflight[keys[i]].cancelled = true; inflight[keys[i]].signal(15) }
    inflight = ({})
  }
}
