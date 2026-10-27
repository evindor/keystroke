// Spell: check the spelling of one English word from the palette.
//
// Everything the rows depend on lives here as pure functions: the query
// parse, the bundled dictionary parse, membership, suggestions and the rows
// themselves. The bundled list is SymSpell's frequency dictionary (see
// README.md). Service.qml owns the side effects: FileView for the file and
// curl for the online service.

var NAME = "Spell check"
var ICON = "󰓆"
var COLOR = "#c586c0"
var PREFIX = "spell"
var CHECK = "\u2713"
var SUGGESTED = "Did you mean"     // the small label beside the top-ranked suggestion
var MAX_DISTANCE = 2
var MAX_RESULTS = 8
var MAX_CHARS = 32                // the longest word a query is even parsed at
var DICTIONARY_FILE = "frequency_dictionary_en_82_765.txt"
var ENDPOINT = "https://api.datamuse.com/words"
var TIMEOUT_S = 3
var DEBOUNCE_MS = 350             // the same typing pause Translate uses
var CACHE_LIMIT = 128
var ERROR_MS = 30000              // a failed fetch is retried after this
var FAIL_LIMIT = 3
var BACKOFF_MS = 60000            // held off after this many failures in a row

// ------------------------------------------------------------- query parse
// The word the user typed: the first token, lowercased, with every character
// that is not a letter or an apostrophe dropped. `raw` keeps the token as
// typed for the copy-anyway row.
function parse(rest) {
  var token = String(rest || "").trim().split(/\s+/)[0] || ""
  if (!token) return null
  return { raw: token.slice(0, 40), word: normalize(token) }
}

function normalize(text) {
  var t = String(text || "").toLowerCase().replace(/\u2019/g, "'").replace(/[^a-z']/g, "")
  t = t.replace(/''+/g, "'").replace(/^'+|'+$/g, "")
  return t.slice(0, MAX_CHARS)
}

// --------------------------------------------------------------- dictionary
// Parses a fetched dictionary.
function parseDictionary(text) {
  var lines = String(text || "").split("\n")
  var words = [], freqs = [], idx = {}
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i], at = line.indexOf(" ")
    if (at < 1) continue
    var raw = line.slice(0, at)
    if (raw.length > MAX_CHARS) continue
    var word = normalize(raw)
    var freq = Number(line.slice(at + 1).trim())
    if (!word || !(freq > 0)) continue
    if (idx[word] !== undefined) {
      var j = idx[word]
      if (freq > freqs[j]) freqs[j] = freq
      continue
    }
    idx[word] = words.length
    words.push(word)
    freqs.push(freq)
  }
  return { words: words, freqs: freqs, index: idx, heads: letters(words, 0), shoulders: letters(words, 1) }
}

// Buckets of word indices by the character at a position. Two positions are
// enough for the scan: a wrong first letter is usually a substitution, so the
// second character still matches; a dropped or doubled first letter means the
// query's first character is the target's second.
function letters(words, pos) {
  var out = {}
  for (var i = 0; i < words.length; i++) {
    var w = words[i]
    if (w.length <= pos) continue
    var c = w.charAt(pos)
    var list = out[c]
    if (!list) { list = []; out[c] = list }
    list.push(i)
  }
  return out
}

// Restricted Damerau-Levenshtein (optimal string alignment), with an early
// exit once a whole row is past max. Three tables rotate, so each row keeps
// the one above it for transpositions. Returns max + 1 for anything farther.
function distance(a, b, max) {
  var m = a.length, n = b.length
  if (Math.abs(m - n) > max) return max + 1
  if (a === b) return 0
  var rowA = new Array(n + 1), rowB = new Array(n + 1), rowC = new Array(n + 1)
  for (var j = 0; j <= n; j++) rowB[j] = j
  for (var i = 1; i <= m; i++) {
    rowC[0] = i
    var rowMin = rowC[0]
    var ca = a.charCodeAt(i - 1)
    for (var k = 1; k <= n; k++) {
      var cost = ca === b.charCodeAt(k - 1) ? 0 : 1
      var d = rowB[k] + 1
      var left = rowC[k - 1] + 1
      if (left < d) d = left
      var diag = rowB[k - 1] + cost
      if (diag < d) d = diag
      if (i > 1 && k > 1 && ca === b.charCodeAt(k - 2) && a.charCodeAt(i - 2) === b.charCodeAt(k - 1)) {
        var swap = rowA[k - 2] + 1
        if (swap < d) d = swap
      }
      rowC[k] = d
      if (d < rowMin) rowMin = d
    }
    if (rowMin > max) return max + 1
    var t = rowA; rowA = rowB; rowB = rowC; rowC = t
  }
  return rowB[n]
}

// Near matches for a word that is not in the list: every word that shares a
// head character within two positions of the length is scored, and the ones
// within reach are ordered by distance, then frequency, then word. Returns
// [{ word, freq, distance }].
function suggest(state, word, maxResults) {
  var w = normalize(word)
  if (!state || !w || w.length < 2) return []
  var l = w.length, cands = {}, from = l - MAX_DISTANCE, to = l + MAX_DISTANCE
  if (from < 1) from = 1
  gather(state, state.heads[w.charAt(0)], from, to, cands)
  gather(state, state.heads[w.charAt(1)], from, to, cands)
  gather(state, state.shoulders[w.charAt(0)], from, to, cands)
  gather(state, state.shoulders[w.charAt(1)], from, to, cands)
  var out = []
  for (var k in cands) {
    var i = cands[k]
    var d = distance(w, state.words[i], MAX_DISTANCE)
    if (d > MAX_DISTANCE) continue
    out.push({ word: state.words[i], freq: state.freqs[i], distance: d })
  }
  out.sort(byQuality)
  if (out.length > maxResults) out = out.slice(0, maxResults)
  return out
}

function gather(state, bucket, fromLen, toLen, cands) {
  if (!bucket) return
  for (var i = 0; i < bucket.length; i++) {
    var idx = bucket[i]
    if (cands[idx]) continue
    var w = state.words[idx]
    if (w.length < fromLen || w.length > toLen) continue
    cands[idx] = idx
  }
}

function byQuality(a, b) {
  if (a.distance !== b.distance) return a.distance - b.distance
  if (a.freq !== b.freq) return b.freq - a.freq
  if (a.word !== b.word) return a.word < b.word ? -1 : 1
  return 0
}

function isKnown(state, word) {
  return !!state && state.index[normalize(word)] !== undefined
}

// ---------------------------------------------------------------- transport
// curl's standard output is the body, then the -w trailer → { status, body }.
function splitStatus(output) {
  var s = String(output || ""), at = s.lastIndexOf("\n__STATUS__")
  if (at < 0) return { status: 0, body: s }
  return { status: Number(s.slice(at + 11).trim()) || 0, body: s.slice(0, at) }
}

function requestArgv(word) {
  var url = ENDPOINT + "?sp=" + encodeURIComponent(normalize(word)) + "&max=" + String(MAX_RESULTS)
  return ["curl", "-sS", "--max-time", String(TIMEOUT_S), "-w", "\n__STATUS__%{http_code}", url]
}

// The answer is a JSON array of { word, ... } objects. Only single tokens
// made of letters and apostrophes survive, in order, capped (`press pass`
// is not a correction for one word). `[]` is a valid, empty answer; null is
// for a body that is not JSON shaped like an array.
function parseSuggestions(body, cap) {
  var list
  try { list = JSON.parse(String(body || "")) } catch (e) { return null }
  if (!Array.isArray(list)) return null
  var out = [], seen = {}
  for (var i = 0; i < list.length && out.length < cap; i++) {
    var text = list[i] && list[i].word
    if (typeof text !== "string" || /\s/.test(text)) continue
    var w = normalize(text)
    if (!w || seen[w]) continue
    seen[w] = 1
    out.push(w)
  }
  return out
}

// -------------------------------------------------------------------- rows
function copyAction(text) { return { type: "copy", text: text } }
function pasteAction(text) { return { type: "paste", text: text } }

// ctx: { key, word, exact, raw, local (from suggest), net, prefix }
// net: null (the setting keeps it offline), or { words } when answered, or
//      { pending: true | failed: true | blocked: true }
function rows(ctx) {
  var key = ctx.key, base = { icon: ICON, section: NAME }
  function row(fields) {
    var r = {}
    for (var k in base) r[k] = base[k]
    for (var f in fields) r[f] = fields[f]
    return r
  }
  if (!ctx.word) {
    var prefix = ctx.prefix || PREFIX
    var example = (prefix ? prefix + " " : "") + "tresspass"
    return [row({ id: key + "/hint", title: "Type a word to check", subtitle: "Suggestions for one English word: " + example,
                  tier: "item", score: 2, order: 50, disabled: true, verb: "", action: { type: "noop" } })]
  }
  if (ctx.exact) {
    return [row({ id: key + "/ans", title: ctx.word, subtitle: "Spelled correctly", accessory: CHECK,
                  tier: "answer", score: 100, order: 0, verb: "Copy", altVerb: "Paste",
                  action: copyAction(ctx.word), altAction: pasteAction(ctx.word) })]
  }
  var net = ctx.net || {}
  var source = net.words && net.words.length ? net.words : (ctx.local || []).map(function(s) { return s.word })
  var out = [], seen = {}, w = ctx.word
  for (var i = 0; i < source.length && out.length < MAX_RESULTS; i++) {
    var s = source[i]
    if (!s || seen[s] || s === w) continue
    seen[s] = 1
    var fields = { id: key + "/sug/" + s, title: s, tier: "answer", score: 100, order: out.length,
                   verb: "Copy", altVerb: "Paste", action: copyAction(s), altAction: pasteAction(s) }
    if (!out.length) fields.accessory = SUGGESTED
    out.push(row(fields))
  }
  if (!out.length) {
    var raw = ctx.raw || w
    out.push(row({ id: key + "/raw", title: raw, subtitle: "Not in the offline dictionary", tier: "answer",
                   score: 100, order: 0, verb: "Copy", altVerb: "Paste", action: copyAction(raw), altAction: pasteAction(raw) }))
  }
  if (net.failed || net.blocked) {
    out.push(row({ id: key + "/status", title: net.blocked ? "Online suggestions paused for a minute" : "The online service did not answer",
                   subtitle: "The suggestions above come from the offline dictionary", tier: "item", score: 1,
                   order: 90, disabled: true, verb: "", action: { type: "noop" } }))
  }
  return out
}

function loadingRow(key) {
  return { icon: ICON, section: NAME, id: key + "/load", title: "Loading the dictionary", tier: "item", score: 2,
           order: 50, disabled: true, verb: "", action: { type: "noop" } }
}
