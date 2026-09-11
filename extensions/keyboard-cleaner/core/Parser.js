.pragma library

// Pure logic for the Keyboard Cleaner extension: the query shapes it
// answers, how a typed duration is read, the rows it shows and the argv it
// runs. No processes and no QML here; tests/tst_parser.qml covers it.
//
// The extension blocks every keyboard and pointing device for a chosen
// duration so they can be wiped down. `wipe 30s` is the declared command
// (the host hands over the text after the prefix); `block 5m`, `clean 2
// minutes` and `wash 30s` are the alternative verbs, matched through the
// patterns below the same way Keystroke's own providers match shapes.

var NAME = "Keyboard Cleaner"
var ICON = "󰌓"              // nf-md-keyboard_variant, the glyph the Omalaunch extension uses
var COLOR = "#7aa2f7"
var MIN_SECONDS = 1
// Five minutes is long enough to clean a keyboard and short enough that a
// slip like `block 1h` cannot lock anyone out of their session.
var MAX_SECONDS = 5 * 60
var LONG_BLOCK = 60          // anything past a minute asks first

// -------------------------------------------------------------------------
// patterns
//
// Declared shapes lift our row when they match. Verb + duration shapes get
// a real boost; `wipe` itself is the declared command and needs none. The
// bare-duration shapes (`30s`, `5m`) overlap the Timer's, so they carry a
// small boost: our row sits in *Continue with* under the Timer's, never
// above it. Every regex is anchored at the start.
var VERB = "(wipe|wash|clean|block)"
var ALT_VERB = "(wash|clean|block)"
var PATTERNS = [
  { id: "verb-seconds", regex: "^\\s*" + ALT_VERB + "\\b\\s*\\d+\\s*s(ec(ond)?s?)?\\b", flags: "i", boost: 18,
    example: "block 30s", description: "Block input for a number of seconds" },
  { id: "verb-minutes", regex: "^\\s*" + ALT_VERB + "\\b\\s*\\d+\\s*m(in(ute)?s?)?\\b", flags: "i", boost: 18,
    example: "clean 2 minutes", description: "Block input for a number of minutes" },
  { id: "verb-only", regex: "^\\s*" + ALT_VERB + "\\s*$", flags: "i", boost: 6,
    example: "block", description: "A verb on its own uses the default duration" },
  { id: "bare-seconds", regex: "^\\s*\\d+\\s*s(ec(ond)?s?)?\\b", flags: "i", boost: 4,
    example: "30s", description: "A bare duration, offered below the Timer" },
  { id: "bare-minutes", regex: "^\\s*\\d+\\s*m(in(ute)?s?)?\\b", flags: "i", boost: 4,
    example: "5m", description: "A bare duration, offered below the Timer" }
]

// -------------------------------------------------------------------------
// parsing

var UNIT = { s: 1, sec: 1, secs: 1, second: 1, seconds: 1, m: 60, min: 60, mins: 60, minute: 60, minutes: 60, h: 3600, hr: 3600, hrs: 3600, hour: 3600, hours: 3600 }

// Reads a duration at the start of `text`: "30s", "2 minutes", "1m30s",
// or, when bareIsSeconds, a plain number. Returns { seconds, rest } or null.
function readDuration(text, bareIsSeconds) {
  var t = String(text || "").trim(), total = 0, consumed = 0, parts = 0
  var re = /^(\d+(?:\.\d+)?)(?:([a-zA-Z]+)|\s+([a-zA-Z]+)(?=\s|$))?(?=\s|\d|$)/
  while (true) {
    var m = re.exec(t.slice(consumed))
    if (!m) break
    var n = Number(m[1]), unit = (m[2] || m[3] || "").toLowerCase(), width = m[0].length
    if (unit && !UNIT[unit]) {
      if (m[2]) break                       // "10x" is not a duration
      unit = ""; width = m[1].length        // "10 later": a bare number, the word starts the note
    }
    if (unit) total += n * UNIT[unit]
    else { if (parts || !bareIsSeconds) break; total += n }
    parts++
    consumed += width
    var ws = /^\s+/.exec(t.slice(consumed))
    if (ws) consumed += ws[0].length
    if (!unit) break
  }
  if (!parts) return null
  return { seconds: Math.round(total), rest: t.slice(consumed).trim() }
}

function clampSeconds(n) {
  n = Math.round(Number(n) || 0)
  if (n < MIN_SECONDS) return MIN_SECONDS
  if (n > MAX_SECONDS) return MAX_SECONDS
  return n
}

function defaultSeconds(settings) {
  var n = Number(settings && settings.defaultSeconds)
  return clampSeconds(n > 0 ? n : 30)
}

// The text after the declared prefix: `30s note`, `2m`, `90`, or nothing.
// A bare number is seconds. Always a request; the default fills a missing
// duration. `clamped` says the typed duration was cut to the maximum.
function parseCommand(rest, settings) {
  var d = readDuration(rest, true)
  if (!d) return { verb: "wipe", seconds: defaultSeconds(settings), label: String(rest || "").trim().slice(0, 80), defaulted: true, clamped: false }
  return { verb: "wipe", seconds: clampSeconds(d.seconds), label: d.rest.slice(0, 80), defaulted: false, clamped: d.seconds > MAX_SECONDS }
}

// A root query without the command: a verb with or without a duration, or
// a bare duration. Null when the query is about something else.
function parseQuery(rawQuery, settings) {
  var q = String(rawQuery || "").trim()
  if (!q) return null
  var m = new RegExp("^" + VERB + "\\b\\s*(.*)$", "i").exec(q)
  if (m) {
    var verb = m[1].toLowerCase(), tail = m[2]
    var d = readDuration(tail, false)
    if (d) return { verb: verb, seconds: clampSeconds(d.seconds), label: d.rest.slice(0, 80), defaulted: false, clamped: d.seconds > MAX_SECONDS }
    if (tail.trim()) return null            // "clean the house" is not for us
    return { verb: verb, seconds: defaultSeconds(settings), label: "", defaulted: true, clamped: false }
  }
  var bare = readDuration(q, false)
  if (!bare || bare.rest) return null       // "2m in feet" belongs to the converter
  return { verb: "", seconds: clampSeconds(bare.seconds), label: "", defaulted: false, clamped: bare.seconds > MAX_SECONDS }
}

// -------------------------------------------------------------------------
// display

// "5 minutes", "1 minute 30 seconds", "30 seconds".
function describeDuration(seconds) {
  seconds = Math.max(0, Math.round(Number(seconds) || 0))
  var m = Math.floor(seconds / 60), s = seconds % 60, parts = []
  if (m) parts.push(m + " minute" + (m === 1 ? "" : "s"))
  if (s || !parts.length) parts.push(s + " second" + (s === 1 ? "" : "s"))
  return parts.join(" ")
}

// "30s", "5m", "1m 30s" for the countdown digits.
function shortDuration(seconds) {
  seconds = Math.max(0, Math.round(Number(seconds) || 0))
  var m = Math.floor(seconds / 60), s = seconds % 60
  if (!m) return s + "s"
  return s ? m + "m " + s + "s" : m + "m"
}

// -------------------------------------------------------------------------
// argv

// The helper takes the duration as its own argument and discovers the
// devices itself; nothing typed by the user reaches the command line.
function blockArgv(helper, seconds, blockPointer) {
  var argv = [String(helper), "--seconds", String(clampSeconds(seconds))]
  if (blockPointer === false) argv.push("--keep-pointer")
  return argv
}

// One line of the helper's stdout: a JSON object, or null for anything else.
function parseReport(line) {
  try {
    var info = JSON.parse(String(line || ""))
    if (!info || typeof info !== "object") return null
    var out = {}
    if (typeof info.error === "string" && info.error) out.error = info.error.slice(0, 200)
    if (typeof info.blocked === "number" && isFinite(info.blocked)) out.blocked = Math.max(0, Math.round(info.blocked))
    if (typeof info.until === "number" && isFinite(info.until)) out.until = info.until
    return out
  } catch (e) { return null }
}

// -------------------------------------------------------------------------
// rows

function blockRow(parsed, state, viaCommand) {
  var what = state.blockPointer === false ? "the keyboard" : "the keyboard and pointer"
  var subtitle = "Disables " + what + " for " + describeDuration(parsed.seconds) + ", then brings them back"
  if (parsed.defaulted) subtitle += " · default length, add e.g. 30s to change it"
  else if (parsed.clamped) subtitle += " · cut to the 5 minute maximum"
  var row = {
    id: "block", title: "Block input for " + describeDuration(parsed.seconds) + (parsed.label ? ": " + parsed.label : ""),
    subtitle: subtitle, icon: ICON, section: NAME, verb: "Block",
    tier: viaCommand ? "answer" : "fallback", score: viaCommand ? 100 : 1, order: 0,
    keywords: "wipe clean wash block keyboard input",
    preview: shortDuration(parsed.seconds), previewLabel: "BLOCK INPUT", previewDetail: parsed.label || "Wipe, then wait for the countdown",
    action: { type: "block", seconds: parsed.seconds, label: parsed.label }
  }
  // Past a minute the palette cannot be reached to cancel, so ask first.
  if (parsed.seconds > LONG_BLOCK) row.confirm = "Block input for " + describeDuration(parsed.seconds) + "? Nothing you press or move counts until the countdown ends."
  return row
}

function navRow(state) {
  return { id: "open", title: NAME, subtitle: "Block input while you wipe the keyboard: wipe 30s", icon: ICON, section: NAME,
           verb: "Open", tier: "item", score: 6, order: 40, keywords: "wipe clean wash block keyboard input", description: "keyboard cleaner block input wipe",
           action: { type: "navigate", scope: state.key, title: NAME } }
}

// The extension's own screen: three fixed durations. Scores are given
// only for the empty listing; with a query the host's matcher decides.
function screenRows(state, listing) {
  var fixed = [[15, "Quick wipe"], [30, "The usual"], [60, "Keys and the touchpad"]]
  return fixed.map(function(f, i) {
    var row = { id: "fixed/" + f[0], title: "Block for " + describeDuration(f[0]), subtitle: f[1], icon: ICON, section: NAME, verb: "Block",
                tier: "item", order: i, keywords: "wipe block " + f[0], preview: shortDuration(f[0]), previewLabel: "BLOCK INPUT", previewDetail: f[1],
                action: { type: "block", seconds: f[0], label: "" } }
    if (listing) row.score = 50 - i
    return row
  })
}

// Every row for a query. commandRest is the text after the declared prefix
// when the host recognised it, null otherwise; matched says one of our
// patterns fired; scoped means the extension's own screen.
function rows(query, commandRest, matched, settings, scoped, state) {
  var q = String(query || "").trim(), out = []
  var viaCommand = commandRest !== null && commandRest !== undefined
  var parsed = viaCommand ? parseCommand(commandRest, settings) : parseQuery(q, settings)
  if (parsed) out.push(blockRow(parsed, state, viaCommand))
  if (scoped) out = out.concat(screenRows(state, !q))
  else if (!q) out.push(navRow(state))
  return out
}
