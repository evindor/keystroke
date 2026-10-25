.pragma library

// Parsing, formatting and rows for the Coffee extension. Pure functions so
// tests/tst_coffee.qml can cover them without a shell.

var NAME = "Coffee"
var ICON = "󰅶"
var COLOR = "#c9a26b"
var KEYWORDS = "coffee caffeine caffeinate decaffeinate awake stay awake sleep"
var DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
var DAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
var DAY_WORD_RE = "sun(?:day)?|mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?"
var UNIT = { s: 1, sec: 1, secs: 1, second: 1, seconds: 1, m: 60, min: 60, mins: 60, minute: 60, minutes: 60, h: 3600, hr: 3600, hrs: 3600, hour: 3600, hours: 3600 }

function pad(n) { return (n < 10 ? "0" : "") + n }

function clockLabel(ms) {
  var d = new Date(ms)
  return pad(d.getHours()) + ":" + pad(d.getMinutes())
}

function describeDuration(seconds) {
  var s = Math.max(0, Math.round(seconds)), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60, out = []
  if (h) out.push(h + " h")
  if (m) out.push(m + " min")
  if (r || !out.length) out.push(r + " s")
  return out.join(" ")
}

function countdown(seconds) {
  var s = Math.max(0, Math.ceil(seconds)), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60
  return h ? h + ":" + pad(m) + ":" + pad(r) : m + ":" + pad(r)
}

// ------------------------------------------------------------------ durations
// Reads a duration at the start of `text`; returns { seconds, rest } or null.
function readDuration(text, bareIsMinutes) {
  var t = String(text || "").trim()
  var clock = /^(\d{1,2}):(\d{2})(?::(\d{2}))?(?=\s|$)/.exec(t)
  if (clock) {
    var secs = clock[3] !== undefined ? Number(clock[1]) * 3600 + Number(clock[2]) * 60 + Number(clock[3]) : Number(clock[1]) * 60 + Number(clock[2])
    return { seconds: secs, rest: t.slice(clock[0].length).trim() }
  }
  var total = 0, consumed = 0, parts = 0
  var re = /^(\d+(?:\.\d+)?)(?:([a-zA-Z]+)|\s+([a-zA-Z]+)(?=\s|$))?(?=\s|\d|$)/
  while (true) {
    var rest = t.slice(consumed)
    var m = re.exec(rest)
    if (!m) break
    var n = Number(m[1]), unit = (m[2] || m[3] || "").toLowerCase(), width = m[0].length
    if (unit && !UNIT[unit]) {
      if (m[2]) break
      unit = ""
      width = m[1].length
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

function parseDuration(text, bareIsMinutes) {
  var d = readDuration(text, bareIsMinutes)
  return d && !d.rest ? d : null
}

// ------------------------------------------------------------------ clock/time
function parseClock(text) {
  var t = String(text || "").trim().toLowerCase().replace(/\s+/g, " ")
  var m = /^(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*(am|pm)?$/.exec(t)
  if (!m) return null
  var h = Number(m[1]), min = m[2] === undefined ? 0 : Number(m[2]), sec = m[3] === undefined ? 0 : Number(m[3])
  var ap = m[4] || ""
  if (ap) {
    if (h < 1 || h > 12) return null
    if (ap === "pm" && h !== 12) h += 12
    if (ap === "am" && h === 12) h = 0
  }
  if (h > 23 || min > 59 || sec > 59) return null
  return { hours: h, minutes: min, seconds: sec }
}

// A time such as 5pm, 17:00, noon, midnight, tomorrow 8am, or in 30m.
// Returns { atMs, label, kind } or null. A time already past means tomorrow.
function parseUntil(text, now) {
  var t = String(text || "").trim().toLowerCase()
  if (!t) return null
  var inMatch = /^in\s+(.+)$/.exec(t)
  if (inMatch) {
    var d = parseDuration(inMatch[1], true)
    if (d) return { atMs: now + d.seconds * 1000, label: "in " + describeDuration(d.seconds), kind: "duration", seconds: d.seconds }
    return null
  }
  var tomorrow = false
  if (/^tomorrow\b/.test(t)) {
    tomorrow = true
    t = t.replace(/^tomorrow\s+/, "")
  }
  var at = null
  if (t === "noon") at = { hours: 12, minutes: 0, seconds: 0 }
  else if (t === "midnight") at = { hours: 0, minutes: 0, seconds: 0 }
  else at = parseClock(t)
  if (!at) return null
  var d2 = new Date(now)
  d2.setHours(at.hours, at.minutes, at.seconds, 0)
  if (tomorrow) d2.setDate(d2.getDate() + 1)
  else if (d2.getTime() <= now) d2.setDate(d2.getDate() + 1)
  return { atMs: d2.getTime(), label: clockLabel(d2.getTime()), kind: "until" }
}

// ------------------------------------------------------------------ schedules
function canonDay(word) {
  var w = String(word || "").toLowerCase()
  if (w.indexOf("sun") === 0) return 0
  if (w.indexOf("mon") === 0) return 1
  if (w.indexOf("tue") === 0) return 2
  if (w.indexOf("wed") === 0) return 3
  if (w.indexOf("thu") === 0) return 4
  if (w.indexOf("fri") === 0) return 5
  if (w.indexOf("sat") === 0) return 6
  return -1
}

function parseDays(text) {
  var t = " " + String(text || "").toLowerCase().replace(/,/g, " ") + " "
  var out = []
  function add(d) { if (d >= 0 && d < 7 && out.indexOf(d) < 0) out.push(d) }
  if (/\b(every\s*day|everyday|daily|all\s*days)\b/.test(t)) for (var i = 0; i < 7; i++) add(i)
  if (/\bweekdays?\b/.test(t)) for (var w = 1; w <= 5; w++) add(w)
  if (/\bweekends?\b/.test(t)) { add(0); add(6) }
  var rangeRe = new RegExp("\\b(" + DAY_WORD_RE + ")\\s*(?:-|to)\\s*(" + DAY_WORD_RE + ")\\b", "g")
  var m
  while ((m = rangeRe.exec(t))) {
    var a = canonDay(m[1]), b = canonDay(m[2])
    if (a < 0 || b < 0) continue
    for (var d = a; ; d = (d + 1) % 7) {
      add(d)
      if (d === b) break
    }
  }
  var re = new RegExp("\\b(" + DAY_WORD_RE + ")\\b", "g")
  while ((m = re.exec(t))) add(canonDay(m[1]))
  var ex = /\bexcept\s+(.+)$/.exec(t)
  if (ex) {
    var remove = parseDays(ex[1])
    out = out.filter(function(day) { return remove.indexOf(day) < 0 })
  }
  return out.sort(function(x, y) { return x - y })
}

function scheduleId(days, from, to) {
  return days.slice().sort(function(a, b) { return a - b }).join("") + "-" + String(from).replace(":", "") + "-" + String(to).replace(":", "")
}

function daySummary(days) {
  var d = (days || []).slice().sort(function(a, b) { return a - b })
  if (d.length === 7) return "Every day"
  if (d.length === 5 && d.join("") === "12345") return "Weekdays"
  if (d.length === 2 && d[0] === 0 && d[1] === 6) return "Weekends"
  var out = []
  for (var i = 0; i < d.length; i++) if (DAY_SHORT[d[i]]) out.push(DAY_SHORT[d[i]])
  return out.join(", ")
}

function describeSchedule(s) {
  if (!s) return ""
  return daySummary(s.days) + " " + s.from + "-" + s.to
}

function clockMinutes(text) {
  var m = /^(\d{2}):(\d{2})$/.exec(String(text || ""))
  if (!m) return -1
  var h = Number(m[1]), min = Number(m[2])
  return h > 23 || min > 59 ? -1 : h * 60 + min
}

function inWindow(s, date) {
  if (!s || !s.days) return false
  var d = date && typeof date.getDay === "function" ? date : new Date(date)
  if (s.days.indexOf(d.getDay()) < 0) return false
  var now = d.getHours() * 60 + d.getMinutes()
  var from = clockMinutes(s.from), to = clockMinutes(s.to)
  return from >= 0 && to > from && now >= from && now < to
}

function activeSchedule(schedules, date) {
  var list = schedules || []
  for (var i = 0; i < list.length; i++) if (!list[i].paused && inWindow(list[i], date)) return list[i]
  return null
}

// "Mon,Thu 09:00-14:00", "every day except Tuesday from 13:00 to 20:00",
// "weekdays 9am-5pm", "from 10:00 to 16:30". Returns a schedule or null.
function parseSchedule(text) {
  var t = String(text || "").trim()
  if (!t) return null
  t = t.replace(/^schedule\s+/i, "")
  var timeRe = /\b(?:from\s+)?(\d{1,2}(?::\d{2})?(?::\d{2})?\s*(?:am|pm)?)\s*(?:-|to)\s*(\d{1,2}(?::\d{2})?(?::\d{2})?\s*(?:am|pm)?)\b/i
  var m = timeRe.exec(t)
  if (!m) return null
  var from = parseClock(m[1]), to = parseClock(m[2])
  if (!from || !to) return null
  var fromMin = from.hours * 60 + from.minutes, toMin = to.hours * 60 + to.minutes
  if (toMin <= fromMin) return null
  var daysText = t.slice(0, m.index).replace(/\bfrom\b/gi, " ").trim()
  var days = parseDays(daysText)
  if (!days.length) days = [0, 1, 2, 3, 4, 5, 6]
  var fromText = pad(from.hours) + ":" + pad(from.minutes)
  var toText = pad(to.hours) + ":" + pad(to.minutes)
  return { id: scheduleId(days, fromText, toText), days: days, from: fromText, to: toText, paused: false }
}

// ------------------------------------------------------------------ rows
function withScore(row, score, query) {
  if (!query) row.score = score
  return row
}

function navRow(state, key, query) {
  var row = {
    id: "coffee/nav",
    title: NAME,
    subtitle: state.active ? statusTitle(state, state.now || Date.now()) : "Keep the computer awake: coffee 30m, coffee 5pm",
    icon: ICON,
    section: "Coffee",
    verb: "Open",
    tier: "item",
    order: 40,
    keywords: KEYWORDS,
    description: "Caffeinate keep awake prevent sleep",
    remember: true,
    accessory: state.active ? "on" : "",
    action: { type: "navigate", scope: key, title: NAME }
  }
  return withScore(row, 20, query)
}

function statusTitle(state, now) {
  if (!state.active) return "Not caffeinated"
  if (state.mode === "for" || state.mode === "until") {
    var left = Math.max(0, (state.endsAt - now) / 1000)
    if (left <= 0) return "Not caffeinated"
    return "Caffeinated for " + describeDuration(left) + " more"
  }
  if (state.mode === "while") return "Caffeinated while " + state.pattern + " runs"
  if (state.mode === "schedule") return "Caffeinated by schedule"
  return "Caffeinated indefinitely"
}

function statusDetail(state, now, settings) {
  var s = settings || {}
  if (!state.active) {
    var off = []
    if (s.preventIdle === false) off.push("screen lock")
    if (s.preventSleep === false) off.push("system sleep")
    if (off.length === 2) return "Both prevention settings are off"
    return "Starts on demand"
  }
  var parts = []
  if (s.preventIdle !== false) parts.push(state.idleOwned ? "screen lock paused by Coffee" : "screen lock already paused")
  if (s.preventSleep !== false) parts.push("system sleep blocked")
  if (state.mode === "for" || state.mode === "until") parts.push("ends at " + clockLabel(state.endsAt))
  if (state.mode === "schedule" && state.label) parts.push(state.label)
  return parts.join(" · ")
}

function statusRow(state, settings, now) {
  return {
    id: "coffee/status",
    title: statusTitle(state, now),
    subtitle: statusDetail(state, now, settings),
    icon: ICON,
    section: "Coffee",
    verb: "",
    tier: "answer",
    score: 100,
    order: 0,
    accessory: state.active ? "on" : "off",
    disabled: true,
    action: { type: "noop" }
  }
}

function manualRow(state, query) {
  return withScore({
    id: "coffee/on",
    title: "Caffeinate indefinitely",
    subtitle: "Keep the screen and the computer awake until you turn it off",
    icon: ICON,
    section: "Coffee",
    verb: "Start",
    tier: "answer",
    order: 1,
    keywords: "on start caffeinate awake",
    action: { type: "coffee-start", mode: "manual" }
  }, 95, query)
}

function stopRow(state, query, settings) {
  var row = {
    id: "coffee/off",
    title: "Decaffeinate",
    subtitle: "Let the screen lock and the computer sleep again",
    icon: ICON,
    section: "Coffee",
    verb: "Decaffeinate",
    tier: "item",
    order: 2,
    keywords: "off stop decaffeinate sleep",
    action: { type: "coffee-stop" }
  }
  if (state.mode === "schedule") {
    row.subtitle = settings && settings.decaffeinatePausesSchedules === true
      ? "Pause the schedule and let the screen lock and the computer sleep"
      : "Pause the schedule first, or turn on decaffeinate-pauses-schedules"
  }
  return withScore(row, 90, query)
}

function extendRow(seconds, query, order) {
  return withScore({
    id: "coffee/extend/" + seconds,
    title: "Extend by " + describeDuration(seconds),
    subtitle: "Add to the current timer",
    icon: ICON,
    section: "Coffee",
    verb: "Extend",
    tier: "item",
    order: order || 4,
    keywords: "extend more time",
    action: { type: "coffee-extend", seconds: seconds }
  }, 92, query)
}

function toggleRow(state, query) {
  return withScore({
    id: "coffee/toggle",
    title: state.active ? "Decaffeinate" : "Caffeinate",
    subtitle: state.active ? "Stop keeping the computer awake" : "Keep the screen and the computer awake",
    icon: ICON,
    section: "Coffee",
    verb: "Toggle",
    tier: "answer",
    order: 3,
    keywords: "toggle switch",
    action: { type: "coffee-toggle" }
  }, 94, query)
}

function forRow(seconds, label, query, order) {
  return withScore({
    id: "coffee/for/" + seconds,
    title: "Caffeinate for " + describeDuration(seconds),
    subtitle: label ? label : "Then let the screen lock and the computer sleep",
    icon: ICON,
    section: "Coffee",
    verb: "Start",
    tier: "answer",
    order: order || 4,
    keywords: "for duration " + describeDuration(seconds),
    action: { type: "coffee-start", mode: "for", seconds: seconds, label: label || "" }
  }, 93, query)
}

function untilRow(atMs, label, query, now, order) {
  var t = now === undefined ? Date.now() : now
  return withScore({
    id: "coffee/until/" + atMs,
    title: "Caffeinate until " + label,
    subtitle: "For " + describeDuration(Math.max(0, (atMs - t) / 1000)),
    icon: ICON,
    section: "Coffee",
    verb: "Start",
    tier: "answer",
    order: order || 4,
    keywords: "until time " + label,
    action: { type: "coffee-start", mode: "until", atMs: atMs, label: label }
  }, 93, query)
}

function whileRow(pattern, query) {
  return withScore({
    id: "coffee/while/custom",
    title: "Caffeinate while " + pattern + " runs",
    subtitle: "Stops when the app is no longer running",
    icon: ICON,
    section: "Coffee",
    verb: "Start",
    tier: "answer",
    order: 4,
    keywords: "while app running " + pattern,
    action: { type: "coffee-start", mode: "while", pattern: pattern }
  }, 93, query)
}

function queryRow(id, title, subtitle, text, query) {
  return withScore({
    id: id,
    title: title,
    subtitle: subtitle,
    icon: ICON,
    section: "Coffee",
    verb: "Type",
    tier: "item",
    order: 8,
    action: { type: "query", text: text }
  }, 60, query)
}

function hintRow(id, title, subtitle) {
  return {
    id: id,
    title: title,
    subtitle: subtitle || "",
    icon: ICON,
    section: "Coffee",
    verb: "",
    tier: "item",
    score: 1,
    order: 99,
    disabled: true,
    action: { type: "noop" }
  }
}

function screenRows(state, settings, key, query, now) {
  var out = [statusRow(state, settings, now)]
  if (state.active) {
    out.push(stopRow(state, query, settings))
    if (state.mode === "schedule" && state.scheduleId) {
      out.push({
        id: "coffee/schedule/pause-current",
        title: "Pause the running schedule",
        subtitle: state.label || "",
        icon: ICON,
        section: "Coffee",
        verb: "Pause",
        tier: "item",
        score: 91,
        order: 3,
        action: { type: "coffee-schedule-pause", id: state.scheduleId }
      })
    }
    if (state.mode === "for" || state.mode === "until") {
      out.push(extendRow(15 * 60, query, 4))
      out.push(extendRow(30 * 60, query, 5))
      out.push(extendRow(60 * 60, query, 6))
    }
  } else {
    out.push(manualRow(state, query))
    out.push(forRow(30 * 60, "", query))
    var midnight = parseUntil("midnight", now)
    if (midnight) out.push(untilRow(midnight.atMs, midnight.label, query, now))
  }
  out.push(queryRow("coffee/for", "Caffeinate for...", "15m, 1h30m, 0:45", "coffee-for ", query))
  out.push(queryRow("coffee/until", "Caffeinate until...", "5pm, 17:00, tomorrow 8am", "coffee-until ", query))
  out.push(queryRow("coffee/while", "Caffeinate while...", "An app name, e.g. Firefox", "coffee-while ", query))
  var add = queryRow("coffee/schedule/add", "Add a schedule", "Mon,Thu 09:00-14:00", "coffee-schedule add ", query)
  add.score = 5
  out.push(add)
  out = out.concat(scheduleListRows(state, key, now, query))
  return out
}

function forRows(rest, state, settings, key, now) {
  var text = String(rest || "").trim()
  if (!text) {
    var out = []
    var presets = [15 * 60, 30 * 60, 60 * 60, 2 * 60 * 60, 4 * 60 * 60]
    for (var i = 0; i < presets.length; i++) out.push(forRow(presets[i], "", "", 4 + i))
    out.push(hintRow("coffee/for/hint", "Type a duration", "15m, 1h30m, 0:45, or a bare number of minutes"))
    return out
  }
  var d = readDuration(text, true)
  if (!d) return [hintRow("coffee/for/hint", "That duration could not be read", "Try 15m, 1h30m, 0:45, or 90")]
  var label = d.rest.slice(0, 80)
  return [forRow(d.seconds, label, "")]
}

function untilRows(rest, state, settings, key, now) {
  var text = String(rest || "").trim()
  if (!text) {
    var out = []
    out.push(untilRow(now + 30 * 60 * 1000, clockLabel(now + 30 * 60 * 1000), "", now, 4))
    out.push(untilRow(now + 60 * 60 * 1000, clockLabel(now + 60 * 60 * 1000), "", now, 5))
    out.push(untilRow(now + 2 * 60 * 60 * 1000, clockLabel(now + 2 * 60 * 60 * 1000), "", now, 6))
    var midnight = parseUntil("midnight", now)
    if (midnight) out.push(untilRow(midnight.atMs, midnight.label, "", now, 7))
    var morning = parseUntil("8am", now)
    if (morning) out.push(untilRow(morning.atMs, morning.label, "", now, 8))
    out.push(hintRow("coffee/until/hint", "Type a time", "5pm, 17:00, noon, midnight, or tomorrow 8am"))
    return out
  }
  var u = parseUntil(text, now)
  if (!u) return [hintRow("coffee/until/hint", "That time could not be read", "Try 5pm, 17:00, noon, midnight, or tomorrow 8am")]
  if (u.kind === "duration") return [forRow(u.seconds, "", "")]
  return [untilRow(u.atMs, u.label, "", now)]
}

function whileRows(rest, state, settings, key, now) {
  var pattern = String(rest || "").trim()
  if (!pattern) return [hintRow("coffee/while/hint", "Type an app name", "For example coffee-while Firefox")]
  if (pattern.length > 100 || /[\x00-\x1f\x7f]/.test(pattern)) return [hintRow("coffee/while/hint", "That app name is not usable", "Use a short process or window name")]
  return [whileRow(pattern, "")]
}

function scheduleListRows(state, key, now, query) {
  var out = []
  var list = state.schedules || []
  for (var i = 0; i < list.length; i++) {
    var s = list[i]
    var active = inWindow(s, now)
    var row = {
      id: "coffee/schedule/" + s.id,
      title: describeSchedule(s),
      subtitle: s.paused ? "Paused" : (active ? "Active now" : "Scheduled"),
      icon: ICON,
      section: "Schedules",
      verb: "Open",
      tier: "item",
      order: 20 + i,
      accessory: s.paused ? "paused" : (active ? "on" : ""),
      keywords: "schedule " + s.id + " " + daySummary(s.days),
      action: { type: "navigate", scope: key + "/schedule/" + s.id, title: "Schedule" }
    }
    out.push(withScore(row, 50 - i, query))
  }
  if (!list.length) out.push(hintRow("coffee/schedule/none", "No schedules yet", "Add one with coffee-schedule add Mon,Thu 09:00-14:00"))
  return out
}

function scheduleDetailRows(id, state, settings, key, now) {
  var list = state.schedules || [], s = null
  for (var i = 0; i < list.length; i++) if (list[i].id === id) s = list[i]
  if (!s) return [hintRow("coffee/schedule/missing", "That schedule is gone", "Go back to Coffee to see the current schedules"), backRow(key)]
  var out = []
  out.push({
    id: "coffee/schedule/status",
    title: describeSchedule(s),
    subtitle: s.paused ? "Paused" : (inWindow(s, now) ? "Active now" : "Scheduled"),
    icon: ICON,
    section: "Schedule",
    verb: "",
    tier: "item",
    score: 100,
    order: 0,
    accessory: s.paused ? "paused" : (inWindow(s, now) ? "on" : ""),
    disabled: true,
    action: { type: "noop" }
  })
  out.push({
    id: "coffee/schedule/toggle",
    title: s.paused ? "Resume this schedule" : "Pause this schedule",
    subtitle: s.paused ? "It will caffeinate again when its window starts" : "It will not start until you resume it",
    icon: ICON,
    section: "Schedule",
    verb: s.paused ? "Resume" : "Pause",
    tier: "item",
    score: 90,
    order: 1,
    action: { type: s.paused ? "coffee-schedule-resume" : "coffee-schedule-pause", id: s.id }
  })
  out.push({
    id: "coffee/schedule/delete",
    title: "Delete this schedule",
    subtitle: "Remove it for good",
    icon: ICON,
    section: "Schedule",
    verb: "Delete",
    tier: "item",
    score: 80,
    order: 2,
    action: { type: "coffee-schedule-delete", id: s.id }
  })
  out.push(backRow(key))
  return out
}

function backRow(key) {
  return {
    id: "coffee/back",
    title: "Back to Coffee",
    subtitle: "Status and schedules",
    icon: ICON,
    section: "Coffee",
    verb: "Open",
    tier: "item",
    score: 10,
    order: 50,
    action: { type: "navigate", scope: key, title: NAME }
  }
}

function scheduleRows(rest, state, settings, key, now) {
  var text = String(rest || "").trim()
  var lower = text.toLowerCase()
  if (!text || lower === "list") {
    var rows = scheduleListRows(state, key, now, "")
    var add = queryRow("coffee/schedule/add", "Add a schedule", "Mon,Thu 09:00-14:00", "coffee-schedule add ", "")
    add.score = 5
    rows.push(add)
    return rows
  }
  if (lower.indexOf("add ") === 0) {
    var s = parseSchedule(text.slice(4))
    if (!s) return [hintRow("coffee/schedule/hint", "That schedule could not be read", "Try coffee-schedule add Mon,Thu 09:00-14:00")]
    return [{
      id: "coffee/schedule/add/" + s.id,
      title: "Add schedule: " + describeSchedule(s),
      subtitle: "Replaces an identical schedule",
      icon: ICON,
      section: "Schedules",
      verb: "Add",
      tier: "answer",
      score: 100,
      order: 0,
      action: { type: "coffee-schedule-add", schedule: s }
    }]
  }
  var actionMatch = /^(pause|resume|delete)\s+(.+)$/i.exec(text)
  if (actionMatch) {
    var verb = actionMatch[1].toLowerCase(), wanted = actionMatch[2].trim()
    var found = null, list = state.schedules || []
    for (var i = 0; i < list.length; i++) if (list[i].id === wanted || describeSchedule(list[i]).toLowerCase() === wanted.toLowerCase()) found = list[i]
    if (!found) return [hintRow("coffee/schedule/hint", "No schedule matches " + wanted, "Open Coffee to see the schedule names")]
    if (verb === "delete") return [{
      id: "coffee/schedule/delete/" + found.id,
      title: "Delete " + describeSchedule(found),
      subtitle: "Remove it for good",
      icon: ICON,
      section: "Schedules",
      verb: "Delete",
      tier: "item",
      score: 90,
      order: 0,
      action: { type: "coffee-schedule-delete", id: found.id }
    }]
    return [{
      id: "coffee/schedule/" + verb + "/" + found.id,
      title: (verb === "pause" ? "Pause " : "Resume ") + describeSchedule(found),
      subtitle: verb === "pause" ? "Stop caffeinating now and skip its windows" : "Caffeinate now if its window is open",
      icon: ICON,
      section: "Schedules",
      verb: verb === "pause" ? "Pause" : "Resume",
      tier: "item",
      score: 90,
      order: 0,
      action: { type: verb === "pause" ? "coffee-schedule-pause" : "coffee-schedule-resume", id: found.id }
    }]
  }
  var parsed = parseSchedule(text)
  if (parsed) return [{
    id: "coffee/schedule/add/" + parsed.id,
    title: "Add schedule: " + describeSchedule(parsed),
    subtitle: "Replaces an identical schedule",
    icon: ICON,
    section: "Schedules",
    verb: "Add",
    tier: "answer",
    score: 100,
    order: 0,
    action: { type: "coffee-schedule-add", schedule: parsed }
  }]
  return [hintRow("coffee/schedule/hint", "Try a schedule", "coffee-schedule add Mon,Thu 09:00-14:00")]
}

function mainRows(rest, state, settings, key, now) {
  var text = String(rest || "").trim()
  var lower = text.toLowerCase()
  if (!text) return [{
    id: "coffee/open",
    title: "Open Coffee",
    subtitle: statusTitle(state, now) + " · " + statusDetail(state, now, settings),
    icon: ICON,
    section: "Coffee",
    verb: "Open",
    tier: "item",
    score: 100,
    order: 0,
    action: { type: "navigate", scope: key, title: NAME }
  }]
  if (lower === "on" || lower === "start" || lower === "caffeinate") return [manualRow(state, "")]
  if (lower === "off" || lower === "stop" || lower === "decaffeinate") return [stopRow(state, "", settings)]
  if (lower === "toggle") return [toggleRow(state, "")]
  if (lower === "status") return [statusRow(state, settings, now), state.active ? stopRow(state, "", settings) : manualRow(state, "")]
  if (lower.indexOf("for ") === 0) return forRows(text.slice(4), state, settings, key, now)
  if (lower.indexOf("until ") === 0) return untilRows(text.slice(6), state, settings, key, now)
  if (lower.indexOf("while ") === 0) return whileRows(text.slice(6), state, settings, key, now)
  if (lower === "while") return whileRows("", state, settings, key, now)
  if (lower.indexOf("schedule") === 0) return scheduleRows(text.slice(8), state, settings, key, now)
  if (/^(in\s+|\d{1,2}:\d{2}|.*\d\s*(?:am|pm)\b|noon|midnight|tomorrow)/i.test(text)) {
    var u = parseUntil(text, now)
    if (u) return u.kind === "duration" ? [forRow(u.seconds, "", "")] : [untilRow(u.atMs, u.label, "", now)]
  }
  var d = readDuration(text, true)
  if (d) return [forRow(d.seconds, d.rest.slice(0, 80), "")]
  return [hintRow("coffee/hint", "Try on, off, status, 30m, 5pm, while Firefox, or schedule", "coffee-schedule add Mon,Thu 09:00-14:00")]
}

function rootRows(query, state, key) {
  return [navRow(state, key, query)]
}
