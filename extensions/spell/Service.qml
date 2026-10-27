pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "core/Spell.js" as Spell

// Spell: check the spelling of one English word from the palette.
//
// Keystroke creates this object when the user turns the extension on,
// injects `shell`, `extension` and `omarchyPath`, reads `provider`, and
// destroys it when the extension is turned off. The bundled frequency list
// (SymSpell's, see README.md) is parsed once when its file loads and
// answers synchronously from then on. A word that is in it gets its one
// checked row and no network. Anything else asks api.datamuse.com, one
// curl per word, answers cached for the session; a failed word retries
// after thirty seconds, and three failures in a row hold the service off
// for a minute. The offline suggestions answer at once through every one
// of those states, so the rows stand while the request is on its way.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var host: null            // the palette, captured from ctx on each query
  property var settings: ({ online: true })

  readonly property string key: extension && extension.id ? String(extension.id) : "spell"
  readonly property string dictionaryPath: extension && extension.dir ? extension.dir + "/assets/" + Spell.DICTIONARY_FILE : ""
  readonly property bool online: settings && settings.online !== false

  property var state: null           // the parsed dictionary
  property var cache: ({})           // word -> { words, at }; answers last the session, oldest out past the cap
  property var cacheOrder: []
  property var errors: ({})          // word -> { at }; a failed word retries after ERROR_MS
  property var inflight: ({})        // word -> its curl Process
  property int failures: 0
  property double blockedUntil: 0
  property string pendingWord: ""
  readonly property Timer debounce: Timer { interval: Spell.DEBOUNCE_MS; onTriggered: root.start(root.pendingWord) }

  readonly property var provider: ({
    apiVersion: 1,
    name: Spell.NAME,
    icon: Spell.ICON,
    color: Spell.COLOR,
    description: "Check the spelling of one English word: spell tresspass",
    prefix: "spell",
    settings: [
      { key: "online", type: "boolean", label: "Use the online suggestions", "default": true,
        description: "Suggestions beyond the bundled word list come from api.datamuse.com; the word itself is the only data sent. Off keeps the extension offline" }
    ],
    query: function(ctx) { return root.query(ctx) }
  })

  readonly property FileView dictionary: FileView {
    path: root.dictionaryPath
    printErrors: false
    onLoaded: {
      var t0 = Date.now()
      root.state = Spell.parseDictionary(text())
      console.info("spell: dictionary ready, " + root.state.words.length + " words in " + (Date.now() - t0) + "ms")
      if (root.host && root.host.opened) root.host.requery({ catalog: false, provider: root.key })
    }
    onLoadFailed: function(error) {
      if (!root.dictionaryPath) return
      if (root.host) root.host.errorMessage = "Spell: the bundled dictionary could not be read (" + error + ")"
    }
  }

  // ---------------------------------------------------------------- palette
  function query(ctx) {
    root.host = ctx.host
    if (ctx && ctx.settings) root.settings = ctx.settings
    var asked = parseAsk(ctx)
    if (!asked) return []              // only the prefix and this screen; never every query
    var word = Spell.parse(asked.rest)
    if (!word) return Spell.rows({ key: key, prefix: asked.prefix })
    if (!root.state) return [Spell.loadingRow(key)]
    if (Spell.isKnown(root.state, word.word)) return Spell.rows({ key: key, word: word.word, exact: true })
    return Spell.rows({ key: key, word: word.word, raw: word.raw, prefix: asked.prefix,
                        local: Spell.suggest(root.state, word.word, Spell.MAX_RESULTS),
                        net: root.ensureOnline(word.word, ctx) })
  }

  // The host strips a declared prefix and hands it over as ctx.command, and
  // the user may have renamed the prefix, so it is read, never re-parsed,
  // there. Older hosts and this extension's own screen arrive without it:
  // the literal prefix is the fallback for the first, the raw query is the
  // word for the second.
  function parseAsk(ctx) {
    if (ctx.command) return { rest: String(ctx.command.rest || ""), prefix: String(ctx.command.prefix || Spell.PREFIX) }
    var q = String(ctx.query || "").trim()
    if (ctx.scope === key) return { rest: q, prefix: "" }
    var lower = q.toLowerCase()
    if (lower.indexOf("spell ") === 0) return { rest: q.slice(6).trim(), prefix: "spell" }
    if (lower === "spell") return { rest: "", prefix: "spell" }
    return null
  }

  // --------------------------------------------------------------- online
  // null when the setting keeps it offline, or otherwise the state of the
  // request for this word: a cached answer, a recent failure, a held-off
  // service, or a request on its way.
  function ensureOnline(word, ctx) {
    if (!root.online) return null
    var now = Date.now()
    if (root.blockedUntil > now) return { blocked: true }
    var v = root.cache[word]
    if (v) return { words: v.words }
    var e = root.errors[word]
    if (e && e.at + Spell.ERROR_MS > now) return { failed: true }
    if (root.inflight[word]) {
      if (ctx) ctx.pending()
      return { pending: true }
    }
    root.pendingWord = word
    root.debounce.restart()
    if (ctx) ctx.pending()
    return { pending: true }
  }

  function start(word) {
    if (!word || root.inflight[word]) return
    var p = root.fetcher.createObject(root, { word: word })
    p.command = Spell.requestArgv(word)
    root.inflight[word] = p
    p.running = true
  }

  readonly property Component fetcher: Component {
    Process {
      id: proc
      property string word: ""
      property bool cancelled: false
      property bool done: false
      property bool bodyDone: false
      property int code: -1
      property string body: ""
      stdout: StdioCollector { onStreamFinished: { if (proc.cancelled) return; proc.body = text; proc.bodyDone = true; root.settled(proc) } }
      onExited: function(code) { if (proc.cancelled) return; proc.code = code; root.settled(proc) }
    }
  }

  // stdout and the exit code arrive in either order; the fetch is judged
  // once both are in. Words are the cache's keys, so a late answer for a
  // word the user has already left only fills the cache: the rows are
  // always derived from the word the palette is asking about now.
  function settled(proc) {
    if (proc.cancelled || proc.done) return
    if (!proc.bodyDone || proc.code < 0) return
    proc.done = true
    delete root.inflight[proc.word]
    var now = Date.now()
    var parts = Spell.splitStatus(proc.body)
    var words = parts.status === 200 ? Spell.parseSuggestions(parts.body, Spell.MAX_RESULTS) : null
    if (words) {
      root.cacheOrder.push(proc.word)
      while (root.cacheOrder.length > Spell.CACHE_LIMIT) delete root.cache[root.cacheOrder.shift()]
      root.cache[proc.word] = { words: words, at: now }
      delete root.errors[proc.word]
      root.failures = 0
    } else {
      root.errors[proc.word] = { at: now }
      root.failures++
      if (root.failures >= Spell.FAIL_LIMIT) {
        root.blockedUntil = now + Spell.BACKOFF_MS
        root.failures = 0
        if (root.host) root.host.statusMessage = "Spell: the online service is unreachable; the offline dictionary is answering"
      }
    }
    Qt.callLater(function() { proc.destroy() })
    if (root.host && root.host.opened) root.host.requery({ catalog: false, provider: root.key })
  }

  Component.onDestruction: {
    root.debounce.stop()
    var keys = Object.keys(root.inflight)
    for (var i = 0; i < keys.length; i++) {
      var p = root.inflight[keys[i]]
      p.cancelled = true
      p.signal(15)
    }
    root.inflight = ({})
  }
}
