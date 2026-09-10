.pragma library
.import "Languages.js" as Languages

// Pure functions for the Translate extension: the query grammar, the request
// to translate.google.com, the response parser and the rows. Nothing here
// touches the network or the shell, so tests/tst_translate.qml covers it all.
//
// Accepted queries (case-insensitive):
//   tr bonjour              → detect the source, translate into the first target
//   tr fr good morning      → an explicit target by code or name
//   bonjour to english      → a natural trailing form ("to", "in", "into")
//   good morning (in scope) → no prefix needed on the extension's own screen
//
// The endpoint is the one the translate.google.com page uses, keyless and
// undocumented; see README.md for what that implies. The `tk` token the
// Raycast port computes is not validated for this client and is not sent.

var NAME = "Translate"
var ICON = "󰗊"
var COLOR = "#61afef"
var DEFAULT_KEY = "translate"
var ENDPOINT = "https://translate.google.com/translate_a/single"
var TTS_ENDPOINT = "https://translate.google.com/translate_tts"
var WEB = "https://translate.google.com/"
var PREFIXES = ["tr", "translate"]
var MIN_CHARS = 2
var MAX_CHARS = 5000        // what the web page accepts
var TTS_MAX_CHARS = 200
var URL_LIMIT = 2048        // longer than this goes as a POST body
var DEBOUNCE_MS = 350
var TIMEOUT_S = 20
var BACKOFF_MS = 60000      // after an HTTP 429
var CACHE_LIMIT = 300
var MAX_TARGETS = 6

// Two-letter codes that are also everyday English words are not accepted as
// a bare target ("tr it is raining" is a sentence, not Italian): name the
// language instead ("tr italian ...").
var AMBIGUOUS = { am: 1, as: 1, ay: 1, be: 1, ee: 1, ha: 1, hi: 1, ig: 1, is: 1, it: 1, my: 1, no: 1, ny: 1, om: 1, or: 1, so: 1, st: 1, to: 1, ts: 1 }

// What people type → Google's code. Keys are lower case.
var ALIASES = {
  ua: "uk", ukr: "uk", cn: "zh-CN", zh: "zh-CN", chinese: "zh-CN", mandarin: "zh-CN", "zh-hans": "zh-CN", "zh-hant": "zh-TW", tw: "zh-TW",
  he: "iw", heb: "iw", jp: "ja", jpn: "ja", kr: "ko", kor: "ko", gr: "el", greek: "el", cz: "cs", czech: "cs", dk: "da", se: "sv",
  br: "pt", "pt-br": "pt", brazilian: "pt", portuguese: "pt", fil: "tl", ph: "tl", tagalog: "tl", jw: "jv", ger: "de", deutsch: "de",
  eng: "en", english: "en", fra: "fr", fre: "fr", spa: "es", esp: "es", ita: "it", rus: "ru", pol: "pl", nl: "nl", dutch: "nl",
  farsi: "fa", persian: "fa", nb: "no", nn: "no", norwegian: "no", punjabi: "pa", "sr-latn": "sr", ms: "ms", tr: "tr", turkish: "tr"
}

var SETTINGS = [
  { key: "targets", type: "string", label: "Target languages", "default": "en,fr",
    description: "Language codes separated by commas, tried in order; pick them on the Translate screen" },
  { key: "source", type: "enum", label: "Translate from", options: ["auto", "en", "fr", "de", "es", "uk", "ru"], "default": "auto",
    optionLabels: { auto: "Detect", en: "English", fr: "French", de: "German", es: "Spanish", uk: "Ukrainian", ru: "Russian" } },
  { key: "defaultAction", type: "enum", label: "Default action", options: ["copy", "paste"], "default": "copy",
    optionLabels: { copy: "Copy", paste: "Paste into the focused app" }, description: "What Enter does on a translation; Ctrl+Enter does the other" },
  { key: "prioritizeCrossLanguage", type: "boolean", label: "Prioritise cross-language results", "default": false,
    description: "When the text is already in one of your target languages, that echo goes last" },
  { key: "selection", type: "boolean", label: "Offer the selected text", "default": true,
    description: "Reads the primary selection (or the clipboard) when the palette opens and offers to translate it" },
  { key: "speak", type: "boolean", label: "Offer pronunciation playback", "default": false,
    description: "A Speak row that streams Google's text-to-speech through mpv" },
  { key: "proxy", type: "string", label: "HTTP proxy", "default": "",
    description: "Passed to curl as --proxy, e.g. http://proxy.example.com:8080" }
]

// The prefix ("tr", renameable) is declared as a command in extension.json;
// the host recognises it and hands over the rest. The natural trailing form
// is a pattern, since it has no prefix.
var PATTERNS = [
  { id: "target", regex: "\\S\\s+(?:to|in|into)\\s+[a-zA-Z][a-zA-Z-]+\\s*$", flags: "i", boost: 14, example: "bonjour to english", description: "Translates into a named language" }
]

function defaults() {
  var out = {}
  for (var i = 0; i < SETTINGS.length; i++) out[SETTINGS[i].key] = SETTINGS[i]["default"]
  return out
}

// ------------------------------------------------------------ languages
var byCode = null, byName = null
function index() {
  if (byCode) return
  byCode = {}; byName = {}
  var list = Languages.LANGUAGES
  for (var i = 0; i < list.length; i++) {
    byCode[list[i].code.toLowerCase()] = list[i].code
    var name = list[i].name.toLowerCase()
    if (byName[name] === undefined) byName[name] = list[i].code
    var plain = name.replace(/\s*\(.*\)\s*$/, "")
    if (plain !== name && byName[plain] === undefined) byName[plain] = list[i].code   // "portuguese" → the first Portuguese
  }
}

// A code, alias or English name → Google's code, or "" when unknown.
function resolve(word) {
  index()
  var w = String(word || "").trim().toLowerCase().replace(/[.,:;!?]+$/, "")
  if (!w) return ""
  if (w === "auto" || w === "detect") return "auto"
  if (ALIASES[w] !== undefined) return ALIASES[w]
  if (byCode[w] !== undefined) return byCode[w]
  if (byName[w] !== undefined) return byName[w]
  return ""
}

// The target a typed word names, or "" when it does not name one; bare codes
// that are also English words are refused (see AMBIGUOUS).
function resolveTarget(word) {
  var w = String(word || "").trim().toLowerCase()
  if (AMBIGUOUS[w] && ALIASES[w] === undefined) return ""
  var code = resolve(w)
  return code === "auto" ? "" : code
}

function languageName(code) {
  index()
  var c = String(code || "")
  if (!c || c === "auto") return "Detected"
  var list = Languages.LANGUAGES
  for (var i = 0; i < list.length; i++) if (list[i].code.toLowerCase() === c.toLowerCase()) return list[i].name
  return c
}

// "en,fr" → ["en", "fr"]: resolved, deduplicated, at most MAX_TARGETS, never empty.
function targetList(value) {
  var out = [], parts = String(value || "").split(/[\s,;]+/)
  for (var i = 0; i < parts.length && out.length < MAX_TARGETS; i++) {
    var code = resolve(parts[i])
    if (code && code !== "auto" && out.indexOf(code) < 0) out.push(code)
  }
  return out.length ? out : ["en"]
}

function sourceCode(settings) {
  var code = resolve(settings && settings.source)
  return code || "auto"
}

// ---------------------------------------------------------------- query
// { text, to, explicit, prefixed, natural } or null when the query is not a
// translation request. `scoped` treats the whole query as the text;
// `stripped` says the host already removed the prefix (ctx.command.rest).
function parse(query, scoped, stripped) {
  var q = String(query || "").trim()
  var lower = q.toLowerCase(), rest = q, prefixed = !!stripped
  if (stripped && !q) return { text: "", to: "", explicit: false, prefixed: true, natural: false }
  if (!scoped && !stripped) {
    for (var i = 0; i < PREFIXES.length; i++) {
      var p = PREFIXES[i]
      if (lower === p) return { text: "", to: "", explicit: false, prefixed: true, natural: false }
      if (lower.indexOf(p + " ") === 0) { rest = q.slice(p.length + 1).trim(); prefixed = true; break }
    }
  }
  var natural = /^(.*\S)\s+(?:to|in|into)\s+([a-zA-Z][a-zA-Z-]*)\s*$/i.exec(rest)
  if (natural) {
    var target = resolveTarget(natural[2])
    if (target) return { text: clamp(natural[1]), to: target, explicit: true, prefixed: prefixed, natural: true }
  }
  if (!prefixed && !scoped) return null
  var leading = /^([a-zA-Z][a-zA-Z-]*)\s+(\S[\s\S]*)$/.exec(rest)
  if (leading) {
    var code = resolveTarget(leading[1])
    if (code) return { text: clamp(leading[2]), to: code, explicit: true, prefixed: prefixed, natural: false }
  }
  return { text: clamp(rest), to: "", explicit: false, prefixed: prefixed, natural: false }
}

function clamp(text) { return String(text || "").trim().slice(0, MAX_CHARS) }

// The query to type for a spelling correction, in the shape the user used.
// prefix: the command prefix the host recognised (the user may have renamed it).
function retryQuery(query, req, corrected, prefix) {
  if (req.natural) return corrected + " to " + req.to
  if (!req.prefixed) return corrected
  var lower = String(query || "").trim().toLowerCase()
  var p = prefix ? prefix + " " : lower.indexOf("translate ") === 0 ? "translate " : "tr "
  return p + (req.explicit ? req.to + " " : "") + corrected
}

// ------------------------------------------------------------ transport
function cacheKey(text, from, to) { return from + "" + to + "" + text }

// The single-word dictionary payload is large; only ask for it for one word.
function wantsDictionary(text) { return text.length <= 40 && !/\s/.test(text) }

function requestArgv(text, from, to, proxy) {
  var params = "client=dict-chrome-ex&sl=" + encodeURIComponent(from) + "&tl=" + encodeURIComponent(to) + "&hl=" + encodeURIComponent(to)
             + "&dt=t&dt=rm&dt=ld&dt=qca" + (wantsDictionary(text) ? "&dt=bd" : "")
             + "&ie=UTF-8&oe=UTF-8&otf=1&ssel=0&tsel=0&kc=7"
  var argv = ["curl", "-sS", "--max-time", String(TIMEOUT_S), "-w", "\n__STATUS__%{http_code}"]
  if (proxy) argv.push("--proxy", String(proxy))
  var url = ENDPOINT + "?" + params + "&q=" + encodeURIComponent(text)
  if (url.length > URL_LIMIT) argv.push("--data-urlencode", "q=" + text, ENDPOINT + "?" + params)
  else argv.push(url)
  return argv
}

// curl's output is the body followed by the -w trailer → { status, body }.
function splitStatus(output) {
  var s = String(output || ""), at = s.lastIndexOf("\n__STATUS__")
  if (at < 0) return { status: 0, body: s }
  return { status: Number(s.slice(at + 11).trim()) || 0, body: s.slice(0, at) }
}

// The response is a JSON array; the indices below are the ones the Raycast
// extension reads (see README.md). Returns null when the shape is not there.
function parseResponse(body) {
  var b
  try { b = JSON.parse(String(body || "")) } catch (e) { return null }
  if (!Array.isArray(b) || !Array.isArray(b[0])) return null
  var text = "", pronunciation = "", sourcePhonetic = ""
  for (var i = 0; i < b[0].length; i++) {
    var seg = b[0][i]
    if (!Array.isArray(seg)) continue
    if (typeof seg[0] === "string") text += seg[0]
    if (typeof seg[2] === "string" && !pronunciation) pronunciation = seg[2]
    if (typeof seg[3] === "string" && !sourcePhonetic) sourcePhonetic = seg[3]
  }
  if (!text) return null
  var source = typeof b[2] === "string" ? b[2] : ""
  var confirmed = Array.isArray(b[8]) && Array.isArray(b[8][0]) && typeof b[8][0][0] === "string" ? b[8][0][0] : ""
  var dictionary = []
  if (Array.isArray(b[1])) {
    for (var d = 0; d < b[1].length; d++) {
      var entry = b[1][d]
      if (!Array.isArray(entry) || typeof entry[0] !== "string" || !Array.isArray(entry[1])) continue
      dictionary.push({ pos: entry[0], terms: entry[1].filter(function(t) { return typeof t === "string" }).slice(0, 6) })
    }
  }
  var correction = null
  if (Array.isArray(b[7]) && typeof b[7][1] === "string" && b[7][1]) correction = { text: b[7][1], auto: b[7][5] === true }
  return { text: text, source: source, confirmed: confirmed || source, pronunciation: pronunciation, sourcePhonetic: sourcePhonetic,
           dictionary: dictionary, correction: correction }
}

// "interjección: ¡Hola!, ¡Caramba! · noun: …" for the preview pane.
function dictionarySummary(dictionary) {
  var lines = []
  for (var i = 0; i < (dictionary || []).length && lines.length < 4; i++) {
    if (dictionary[i].terms.length) lines.push(dictionary[i].pos + ": " + dictionary[i].terms.join(", "))
  }
  return lines.join("\n")
}

// The order translations are shown in: the configured order, with the
// language the text is already in moved last when the user asked for that.
function orderTargets(targets, detected, prioritize) {
  if (!prioritize || !detected) return targets.slice()
  return targets.filter(function(t) { return t !== detected }).concat(targets.filter(function(t) { return t === detected }))
}

// Same-language fallback: with "detect", English typed against an English
// first target would only echo, so the next target becomes the main answer.
function primaryTarget(order, detected) {
  for (var i = 0; i < order.length; i++) if (order[i] !== detected) return order[i]
  return order[0]
}

// The requests a subject needs right now, given what the cache already holds.
// The first response tells the detected language; the other targets and the
// reverse translation follow from it, so they are only listed once it is in.
//   subject: { text, from, to }   to: an explicit target or ""
//   lookup(text, from, to) → a parsed response, { error } or undefined
//   minimal: stop once the main translation is known (selection copy/paste)
function needed(subject, targets, settings, lookup, minimal) {
  var text = clamp(subject.text), from = subject.from || "auto", out = [], seen = {}
  function add(t, f, to) { var k = cacheKey(t, f, to); if (!seen[k]) { seen[k] = 1; out.push({ text: t, from: f, to: to, key: k }) } }
  if (text.length < MIN_CHARS) return out
  var first = subject.to || targets[0]
  add(text, from, first)
  var r0 = lookup(text, from, first)
  if (!r0 || r0.error) return out
  var detected = r0.source || (from === "auto" ? "" : from)
  var order = subject.to ? [subject.to] : orderTargets(targets, detected, settings.prioritizeCrossLanguage === true)
  var main = subject.to ? subject.to : primaryTarget(order, detected)
  add(text, from, main)
  var rm = lookup(text, from, main)
  if (minimal) return out
  for (var i = 0; i < order.length; i++) add(text, from, order[i])
  if (rm && !rm.error && rm.text && detected && detected !== main) add(rm.text, main, detected)
  return out
}

// What the palette and the view show for a subject: { main, reverse, extras, detected, order, correction }
// where each translation is { to, from, text, pronunciation, dictionary, error, pending }.
function resolveSubject(subject, targets, settings, lookup, busy) {
  var text = clamp(subject.text), from = subject.from || "auto"
  var first = subject.to || targets[0]
  var r0 = lookup(text, from, first)
  var detected = r0 && !r0.error ? (r0.source || (from === "auto" ? "" : from)) : (from === "auto" ? "" : from)
  var order = subject.to ? [subject.to] : orderTargets(targets, detected, settings.prioritizeCrossLanguage === true)
  var main = r0 && !r0.error && !subject.to ? primaryTarget(order, detected) : first
  function slot(t, f, to) {
    var r = lookup(t, f, to)
    if (!r) return { to: to, from: f, text: "", pronunciation: "", dictionary: [], error: "", pending: true, busy: busy(t, f, to) }
    if (r.error) return { to: to, from: f, text: "", pronunciation: "", dictionary: [], error: r.error, pending: false }
    return { to: to, from: f, text: r.text, pronunciation: r.pronunciation, dictionary: r.dictionary, error: "", pending: false }
  }
  var mainSlot = slot(text, from, main)
  var reverse = null
  if (mainSlot.text && detected && detected !== main) reverse = slot(mainSlot.text, main, detected)
  var extras = []
  for (var i = 0; i < order.length; i++) if (order[i] !== main) extras.push(slot(text, from, order[i]))
  var correction = r0 && !r0.error && r0.correction && r0.correction.text !== text ? r0.correction : null
  return { text: text, from: from, detected: detected, order: order, main: mainSlot, reverse: reverse, extras: extras, correction: correction }
}

// ---------------------------------------------------------------- effects
function copyEffect(text) { return { type: "copy", text: text } }

// Paste the way Keystroke's own dictation does: put the text on the clipboard,
// then press Shift+Insert in whatever has focus once the palette is gone. The
// text is a positional argument, never part of the command string.
function pasteArgv(text) {
  return ["sh", "-c", 'wl-copy -- "$1" && sleep 0.15 && wtype -M shift -k Insert -m shift', "keystroke-translate", String(text)]
}
function pasteEffect(text) { return { type: "exec", argv: pasteArgv(text) } }

function webUrl(text, from, to) {
  return WEB + "?sl=" + encodeURIComponent(from || "auto") + "&tl=" + encodeURIComponent(to) + "&text=" + encodeURIComponent(text) + "&op=translate"
}

function ttsUrl(text, lang) {
  return TTS_ENDPOINT + "?ie=UTF-8&client=tw-ob&tl=" + encodeURIComponent(lang) + "&q=" + encodeURIComponent(String(text).slice(0, TTS_MAX_CHARS))
}
function speakArgv(text, lang) { return ["mpv", "--no-video", "--really-quiet", "--", ttsUrl(text, lang)] }

function primaryEffects(text, settings) {
  var paste = settings.defaultAction === "paste"
  return { action: paste ? pasteEffect(text) : copyEffect(text), altAction: paste ? copyEffect(text) : pasteEffect(text),
           verb: paste ? "Paste" : "Copy", hint: paste ? "ctrl ↵ copies" : "ctrl ↵ pastes" }
}

// ------------------------------------------------------------------ rows
function ellipsis(text, n) { var t = String(text || "").replace(/\s+/g, " ").trim(); return t.length > n ? t.slice(0, n - 1) + "…" : t }
function arrow(from, to) { return languageName(from) + " → " + languageName(to) }

// ctx: { query, scope, key, iconSource, settings, targets, matched, selection, canSpeak, now, blockedUntil,
//        lookup(text, from, to), busy(text, from, to), req (a parsed request, when the host stripped the prefix), prefix }
function rows(ctx) {
  var key = ctx.key, scoped = ctx.scope === key
  if (ctx.scope && ctx.scope !== key) return ctx.scope === key + "/targets" ? pickerRows(ctx) : []
  var base = { icon: ICON, iconSource: ctx.iconSource, section: NAME }
  function row(fields) { var r = {}; for (var k in base) r[k] = base[k]; for (var f in fields) r[f] = fields[f]; return r }
  var out = [], q = String(ctx.query || ""), prefix = ctx.prefix || "tr"
  var req = ctx.req !== undefined ? ctx.req : parse(q, scoped)
  var settings = ctx.settings || defaults()
  var from = sourceCode(settings)

  if (!req && !scoped) {
    if (!q) {
      out.push(row({ id: "open", title: NAME, subtitle: ctx.selection ? "Translate the selection or type: tr bonjour" : "Google Translate: tr bonjour, bonjour to english", verb: "Open",
                     tier: "item", score: 6, order: 40, keywords: "translate tr google", description: "translate language google translate text",
                     action: { type: "navigate", scope: key, title: NAME } }))
      if (ctx.selection) out.push(selectionRow(ctx, row, "view"))
    }
    return out
  }
  // Only a matched pattern or the extension's own screen may answer: a provider
  // that answers every query would put a row under everything the user types.
  if (!scoped && !ctx.matched) return out

  if (!req.text) {
    if (ctx.selection) { out.push(selectionRow(ctx, row, "view")); out.push(selectionRow(ctx, row, "copy")); out.push(selectionRow(ctx, row, "paste")) }
    out.push(row({ id: "hint", title: scoped ? "Type text to translate" : "Type text after " + prefix, subtitle: "Into " + ctx.targets.map(languageName).join(", ") + " · " + prefix + " fr bonjour picks a language",
                   tier: "item", score: 2, order: 50, disabled: true, verb: "", action: { type: "noop" } }))
    if (scoped) out.push(targetsRow(ctx, row))
    return out
  }
  if (req.text.length < MIN_CHARS) {
    out.push(row({ id: "hint", title: "Keep typing", subtitle: "At least two characters", tier: "item", score: 2, order: 50, disabled: true, verb: "", action: { type: "noop" } }))
    return out
  }
  if (ctx.blockedUntil && ctx.blockedUntil > ctx.now) {
    out.push(row({ id: "translate/main", title: "Too many requests", subtitle: "Google is rate-limiting this address; try again in " + Math.ceil((ctx.blockedUntil - ctx.now) / 1000) + " s",
                   tier: "answer", score: 100, order: 0, disabled: true, verb: "", action: { type: "noop" } }))
    return out
  }
  var subject = { text: req.text, from: from, to: req.to }
  var view = resolveSubject(subject, ctx.targets, settings, ctx.lookup, ctx.busy)
  var main = view.main, toName = languageName(main.to)
  if (main.error) {
    out.push(row({ id: "translate/main", title: main.error, subtitle: arrow(view.detected || from, main.to), tier: "answer", score: 100, order: 0, disabled: true, verb: "", action: { type: "noop" } }))
  } else if (!main.text) {
    out.push(row({ id: "translate/main", title: "Translating…", subtitle: arrow(view.detected || from, main.to), tier: "answer", score: 100, order: 0, disabled: true, verb: "", action: { type: "noop" } }))
  } else {
    var eff = primaryEffects(main.text, settings)
    out.push(row({ id: "translate/main", title: main.text, subtitle: main.pronunciation ? main.pronunciation + " · " + arrow(view.detected || from, main.to) : arrow(view.detected || from, main.to),
                   tier: "answer", score: 100, order: 0, verb: eff.verb, hint: eff.hint, preview: main.text, previewLabel: toName.toUpperCase(),
                   previewDetail: dictionarySummary(main.dictionary) || arrow(view.detected || from, main.to), action: eff.action, altAction: eff.altAction }))
  }
  if (view.reverse && view.reverse.text) {
    out.push(row({ id: "translate/reverse", title: view.reverse.text, subtitle: "Back to " + languageName(view.detected) + " · a check on the translation",
                   tier: "item", score: 90, order: 1, verb: "Copy", action: copyEffect(view.reverse.text) }))
  }
  for (var i = 0; i < view.extras.length; i++) {
    var x = view.extras[i]
    if (!x.text || x.to === view.detected) continue     // the echo of the language typed is only shown in the editor
    var xe = primaryEffects(x.text, settings)
    out.push(row({ id: "translate/extra/" + x.to, title: x.text, subtitle: (x.pronunciation ? x.pronunciation + " · " : "") + arrow(view.detected || from, x.to),
                   tier: "item", score: 80 - i, order: 2 + i, verb: xe.verb, hint: xe.hint, preview: x.text, previewLabel: languageName(x.to).toUpperCase(),
                   previewDetail: dictionarySummary(x.dictionary) || arrow(view.detected || from, x.to), action: xe.action, altAction: xe.altAction }))
  }
  if (view.correction) {
    out.push(row({ id: "translate/correction", title: "Did you mean: " + view.correction.text, subtitle: view.correction.auto ? "Google translated the corrected spelling" : "Translate the corrected spelling instead",
                   tier: "item", score: 70, order: 10, verb: "Retry", action: { type: "translate-retry", query: retryQuery(q, req, view.correction.text, ctx.prefix), text: view.correction.text } }))
  }
  if (main.text) {
    out.push(row({ id: "translate/editor", title: "Open in the editor", subtitle: "Every target language, with the reverse translation", tier: "item", score: 60, order: 20, verb: "Open",
                   action: { type: "translate-view", text: req.text, to: req.to } }))
    if (settings.speak && ctx.canSpeak) {
      out.push(row({ id: "translate/speak", title: "Speak", subtitle: "Play the " + toName + " pronunciation with mpv", tier: "item", score: 55, order: 21, verb: "Play",
                     action: { type: "exec", argv: speakArgv(main.text, main.to) } }))
    }
    out.push(row({ id: "translate/web", title: "Open in Google Translate", subtitle: "translate.google.com in your browser", tier: "item", score: 50, order: 22, verb: "Open",
                   action: { type: "url", url: webUrl(req.text, from, main.to) } }))
  }
  return out
}

function selectionRow(ctx, row, kind) {
  var text = ellipsis(ctx.selection, 60)
  if (kind === "copy") return row({ id: "selection/copy", title: "Copy the translated selection", subtitle: text, tier: "item", score: 8, order: 42, verb: "Copy",
                                    action: { type: "translate-selection", text: ctx.selection, paste: false } })
  if (kind === "paste") return row({ id: "selection/paste", title: "Paste the translated selection", subtitle: text + " · replaces the selection in the focused app", tier: "item", score: 7, order: 43, verb: "Paste",
                                     action: { type: "translate-selection", text: ctx.selection, paste: true } })
  return row({ id: "selection/view", title: "Translate the selection", subtitle: text, tier: "item", score: 9, order: 41, verb: "Open", hint: "↵ opens · ctrl ↵ copies the translation",
               keywords: "translate selection", action: { type: "translate-view", text: ctx.selection, to: "" }, altAction: { type: "translate-selection", text: ctx.selection, paste: false } })
}

function targetsRow(ctx, row) {
  return row({ id: "targets", title: "Target languages", subtitle: ctx.targets.map(languageName).join(", ") + " · in this order", tier: "item", score: 1, order: 60, verb: "Change",
               accessory: ctx.targets.join(", "), action: { type: "navigate", scope: ctx.key + "/targets", title: "Target languages" } })
}

// The language picker: one row per language, the chosen ones first, Enter toggles.
function pickerRows(ctx) {
  var list = Languages.LANGUAGES, out = [], q = String(ctx.query || ""), schema = SETTINGS[0]
  for (var i = 0; i < list.length; i++) {
    var code = list[i].code, at = ctx.targets.indexOf(code), chosen = at >= 0
    var next = chosen ? ctx.targets.filter(function(t) { return t !== code }) : ctx.targets.concat([code])
    var last = chosen && ctx.targets.length === 1, full = !chosen && ctx.targets.length >= MAX_TARGETS
    var r = { id: "lang/" + code, title: list[i].name, subtitle: chosen ? "Target " + (at + 1) + " of " + ctx.targets.length + " · " + code : code, icon: ICON, iconSource: ctx.iconSource,
              section: chosen ? "Chosen" : "Languages", keywords: code + " " + aliasesFor(code), tier: "item", order: chosen ? at : 1000 + i,
              accessory: chosen ? "✓" : "", verb: chosen ? "Remove" : "Add", disabled: last || full,
              hint: last ? "Keep at least one" : full ? "At most " + MAX_TARGETS : (chosen ? "↵ removes" : "↵ adds"),
              action: last || full ? { type: "noop" } : { type: "setting", path: ["providers", ctx.key], key: "targets", value: next.join(","), schema: schema } }
    if (!q) r.score = chosen ? 2000 - at : 1000 - i
    out.push(r)
  }
  out.sort(function(a, b) { return a.order - b.order })
  return out
}

function aliasesFor(code) {
  var out = []
  for (var a in ALIASES) if (ALIASES[a] === code && out.length < 4) out.push(a)
  return out.join(" ")
}

// Blocks for the editor view, in display order: the main translation, the
// other targets, then the reverse translation.
function viewBlocks(view) {
  var blocks = []
  function push(slot, label) {
    blocks.push({ id: label ? "reverse" : slot.to, label: label || languageName(slot.to), to: slot.to, text: slot.text, pronunciation: slot.pronunciation,
                  detail: dictionarySummary(slot.dictionary), error: slot.error, pending: slot.pending && !slot.text })
  }
  push(view.main)
  for (var i = 0; i < view.extras.length; i++) push(view.extras[i])
  if (view.reverse) push(view.reverse, "Back to " + languageName(view.detected))
  return blocks
}
