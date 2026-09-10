.pragma library

// Parsing and formatting for the Timer extension. Pure functions, so
// tests/tst_timer.qml can cover them without a shell.
//
// Accepted queries (case-insensitive):
//   timer 10m tea        → 600 s, label "tea"      (prefix + duration + label)
//   timer 1h30m          → 5400 s                  (compound durations)
//   timer 90             → 90 min                  (a bare number after the prefix is minutes)
//   timer tea            → default minutes, label "tea"
//   10 min tea · 45s     → item rows, no prefix needed when a unit is present
//   1:30                 → 1 min 30 s; 1:30:00 → 1 h 30 min
// A bare number without the prefix is left alone: that is the calculator's.

var PREFIXES = ["timer", "countdown", "remind me in", "remind in"]
var UNIT = { s: 1, sec: 1, secs: 1, second: 1, seconds: 1, m: 60, min: 60, mins: 60, minute: 60, minutes: 60, h: 3600, hr: 3600, hrs: 3600, hour: 3600, hours: 3600 }

function stripPrefix(query) {
  var q = String(query || "").trim(), lower = q.toLowerCase()
  for (var i = 0; i < PREFIXES.length; i++) {
    var p = PREFIXES[i]
    if (lower === p) return { rest: "", prefixed: true }
    if (lower.indexOf(p + " ") === 0) return { rest: q.slice(p.length + 1).trim(), prefixed: true }
  }
  return { rest: q, prefixed: false }
}

// Reads a duration at the start of `text`; returns { seconds, rest } or null.
function readDuration(text, bareIsMinutes) {
  var t = String(text || "").trim()
  var clock = /^(\d{1,2}):(\d{2})(?::(\d{2}))?(?=\s|$)/.exec(t)
  if (clock) {
    var secs = clock[3] !== undefined ? Number(clock[1]) * 3600 + Number(clock[2]) * 60 + Number(clock[3]) : Number(clock[1]) * 60 + Number(clock[2])
    return { seconds: secs, rest: t.slice(clock[0].length).trim() }
  }
  var total = 0, consumed = 0, parts = 0
  // A number with its unit attached (10m) or separated by spaces (10 min); a
  // number followed by a word that is not a unit is a bare number and the
  // word starts the label ("timer 10 years" is ten minutes labelled "years").
  var re = /^(\d+(?:\.\d+)?)(?:([a-zA-Z]+)|\s+([a-zA-Z]+)(?=\s|$))?(?=\s|\d|$)/
  while (true) {
    var rest = t.slice(consumed)
    var m = re.exec(rest)
    if (!m) break
    var n = Number(m[1]), unit = (m[2] || m[3] || "").toLowerCase(), width = m[0].length
    if (unit && !UNIT[unit]) {
      if (m[2]) break                       // "10x": not a duration at all
      unit = ""; width = m[1].length        // "10 years": bare number, keep the word
    }
    if (unit) total += n * UNIT[unit]
    else {
      if (parts || !bareIsMinutes) break
      total += n * 60
    }
    parts++
    consumed += width
    var ws = /^\s+/.exec(t.slice(consumed))
    if (ws) consumed += ws[0].length
    if (!unit) break
  }
  if (!parts || total <= 0) return null
  return { seconds: Math.round(total), rest: t.slice(consumed).trim() }
}

// { seconds, label, prefixed } or null when the query is not a timer request.
function parse(query, defaultMinutes) {
  var p = stripPrefix(query)
  if (!p.prefixed && !p.rest) return null
  var d = readDuration(p.rest, p.prefixed)
  if (d) {
    if (d.seconds > 7 * 24 * 3600) return null
    return { seconds: d.seconds, label: d.rest.slice(0, 80), prefixed: p.prefixed }
  }
  if (!p.prefixed) return null
  var fallback = Number(defaultMinutes) > 0 ? Number(defaultMinutes) : 5
  return { seconds: Math.round(fallback * 60), label: p.rest.slice(0, 80), prefixed: true, defaulted: true }
}

function pad(n) { return (n < 10 ? "0" : "") + n }

// "1 h 30 min", "10 min", "45 s"
function describe(seconds) {
  var s = Math.max(0, Math.round(seconds)), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60, out = []
  if (h) out.push(h + " h")
  if (m) out.push(m + " min")
  if (r || !out.length) out.push(r + " s")
  return out.join(" ")
}

// "12:34" or "1:02:03" for a countdown accessory.
function countdown(seconds) {
  var s = Math.max(0, Math.ceil(seconds)), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60
  return h ? h + ":" + pad(m) + ":" + pad(r) : m + ":" + pad(r)
}

function endsAt(startMs, seconds) {
  var d = new Date(startMs + seconds * 1000)
  return pad(d.getHours()) + ":" + pad(d.getMinutes())
}

var counter = 0
function make(seconds, label, now) {
  counter++
  return { id: String(now) + "-" + counter, label: String(label || ""), seconds: seconds, startedAt: now, endsAt: now + seconds * 1000 }
}

function remaining(timer, now) { return (timer.endsAt - now) / 1000 }

// Rows for the palette. scoped: the extension's own screen.
function rows(query, timers, settings, now, scoped, scopeKey) {
  var out = [], i
  var req = parse(query, settings.defaultMinutes)
  if (req) {
    var title = "Start a " + describe(req.seconds) + " timer" + (req.label ? ": " + req.label : "")
    out.push({ id: "start", title: title, subtitle: "Ends at " + endsAt(now, req.seconds) + (req.defaulted ? " · default length, add e.g. 10m to change it" : ""),
               icon: "󰔛", section: "Timer", verb: "Start", tier: req.prefixed ? "answer" : "item", score: req.prefixed ? 100 : 40, order: 0,
               preview: countdown(req.seconds), previewLabel: "TIMER", previewDetail: req.label || "No label",
               action: { type: "timer-start", seconds: req.seconds, label: req.label } })
  }
  for (i = 0; i < timers.length; i++) {
    var t = timers[i], left = remaining(t, now)
    if (!scoped && query) continue
    out.push({ id: "running/" + t.id, title: t.label || "Timer", subtitle: describe(t.seconds) + " · ends at " + endsAt(t.startedAt, t.seconds), icon: "󰔛",
               section: "Running", verb: "Cancel", tier: "item", score: 30 - i, order: i, accessory: countdown(left), hint: "↵ cancels",
               confirm: "Cancel the " + (t.label || describe(t.seconds)) + " timer?", action: { type: "timer-cancel", id: t.id } })
  }
  if (!scoped) {
    if (!query) out.push(navRow(timers, 6, scopeKey))
  } else if (!timers.length && !req) {
    out.push({ id: "hint", title: "No timers running", subtitle: "Type a duration: 10m tea, 1h30m, 0:45", icon: "󰔛", section: "Timer",
               verb: "", tier: "item", score: 1, order: 50, disabled: true, action: { type: "noop" } })
  }
  return out
}

function navRow(timers, score, scopeKey) {
  return { id: "open", title: "Timers", subtitle: timers.length ? timers.length + " running" : "Countdown timers: timer 10m tea", icon: "󰔛", section: "Timer",
           verb: "Open", tier: "item", score: score, order: 40, keywords: "timer countdown", description: "timer countdown alarm remind",
           accessory: timers.length ? String(timers.length) : "", action: { type: "navigate", scope: scopeKey, title: "Timers" } }
}
