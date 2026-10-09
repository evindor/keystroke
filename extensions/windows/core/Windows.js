.pragma library

var ICON = ""
var SECTION = "Windows"
var SETTINGS = [
  { key: "root", type: "boolean", label: "Show windows in the main search", "default": true,
    description: "Off: windows appear only after the > command or on this extension's screen" },
  { key: "rootLimit", type: "number", label: "Windows in the main search", "default": 5, min: 1, max: 20, integer: true,
    description: "At most this many windows mix into the main results" },
  { key: "current", type: "boolean", label: "List the focused window", "default": false,
    description: "On: the window you came from is listed too, last" }
]

function request(ctx, id) {
  var explicit = !!ctx.command || ctx.scope === id
  var text = String(ctx.command ? ctx.command.rest : ctx.query || "").trim()
  var settings = ctx.settings || {}
  var allowed = explicit || (!ctx.scope && settings.root !== false && text.length >= 2)
  var limit = Math.max(1, Math.min(20, Number(settings.rootLimit) || 5))
  return { explicit: explicit, text: text, allowed: allowed, current: settings.current === true, limit: explicit ? 0 : limit }
}

// Hyprland addresses are 0x-prefixed hex; anything else never reaches a dispatch string.
function address(value) {
  var a = String(value || "")
  if (a && a.indexOf("0x") !== 0) a = "0x" + a
  return /^0x[0-9a-f]{1,16}$/i.test(a) ? a.toLowerCase() : ""
}

function workspaceLabel(ws) {
  var name = String(ws && ws.name || "")
  if (name.indexOf("special") === 0) return name === "special" || name === "special:scratchpad" ? "Scratchpad" : name.slice(8)
  if (name && !/^-?\d+$/.test(name)) return name
  return "Workspace " + String(ws && ws.id !== undefined ? ws.id : name)
}

// One plain record per mapped client, from hyprctl clients -j shaped objects.
// The last focused window (focusHistoryID 0) is the one you came from only
// when it is on the workspace you are on (`here`, a workspace id) or on a
// special workspace shown over it: an empty workspace has no focused window,
// and the last one elsewhere is listed like any other. Without `here`, the
// last focused window counts as the one you came from.
function windows(clients, here) {
  var out = []
  for (var i = 0; i < (clients || []).length; i++) {
    var c = clients[i]
    if (!c || c.mapped === false || c.hidden === true) continue
    var a = address(c.address)
    if (!a) continue
    var cls = String(c["class"] || c.initialClass || "")
    var focus = typeof c.focusHistoryID === "number" && c.focusHistoryID >= 0 ? c.focusHistoryID : 999
    var ws = c.workspace || {}
    var current = focus === 0 && (typeof here !== "number" || ws.id === here || String(ws.name || "").indexOf("special") === 0)
    out.push({ address: a, title: String(c.title || c.initialTitle || cls || "Untitled"), cls: cls,
      workspace: workspaceLabel(c.workspace), focus: focus, current: current })
  }
  // Most recently used first; the window you came from goes last.
  out.sort(function(x, y) {
    var fx = x.current ? 1e6 : x.focus, fy = y.current ? 1e6 : y.focus
    return fx - fy
  })
  return out
}

// The root shows only a handful of windows, so it narrows the list itself:
// every word of the query must appear, letters in order, in the title or the
// class. Before the cap, windows where every word starts a word come first,
// then those that contain the words as typed, then scattered letters, so a
// long title that happens to hold the letters cannot crowd out the obvious
// hit. The host's matcher then ranks what is left; explicit requests are left
// entirely to it.
function subsequence(needle, hay) {
  var j = 0
  for (var i = 0; i < hay.length && j < needle.length; i++) if (hay.charAt(i) === needle.charAt(j)) j++
  return j === needle.length
}

function startsWord(needle, hay) {
  for (var at = hay.indexOf(needle); at >= 0; at = hay.indexOf(needle, at + 1))
    if (at === 0 || !/[a-z0-9]/.test(hay.charAt(at - 1))) return true
  return false
}

// 0: every word starts a word, 1: every word appears as typed, 2: letters in order, -1: no match.
function quality(words, hay) {
  var tier = 0
  for (var k = 0; k < words.length; k++) {
    if (startsWord(words[k], hay)) continue
    if (hay.indexOf(words[k]) >= 0) tier = Math.max(tier, 1)
    else if (subsequence(words[k], hay)) tier = 2
    else return -1
  }
  return tier
}

function filter(list, req) {
  if (!req.limit) return list
  var words = req.text.toLowerCase().split(/\s+/).filter(function(w) { return !!w })
  var tiers = [[], [], []]
  for (var i = 0; i < list.length; i++) {
    var w = list[i]
    if (w.current && !req.current) continue
    var t = quality(words, (w.title + " " + w.cls).toLowerCase())
    if (t >= 0) tiers[t].push(w)
  }
  return tiers[0].concat(tiers[1], tiers[2]).slice(0, req.limit)
}

function focusCommand(addr, lua) {
  var a = address(addr)
  if (!a) return ""
  return lua ? "hl.dsp.focus({ window = \"address:" + a + "\" })" : "focuswindow address:" + a
}

function status(title, subtitle) {
  return { id: "status", title: title, subtitle: subtitle || "", icon: ICON, section: SECTION,
    tier: "item", score: 1, disabled: true, action: { type: "noop" } }
}

// iconFor maps a window class to an image URL ("" when none is known).
function rows(list, req, iconFor) {
  var out = []
  for (var i = 0; i < list.length; i++) {
    var w = list[i]
    if (w.current && !req.current) continue
    var row = { id: "window:" + w.address, title: w.title, subtitle: [w.cls, w.workspace].filter(function(s) { return !!s }).join(" · "),
      icon: ICON, iconSource: iconFor ? String(iconFor(w.cls) || "") : "", section: SECTION,
      keywords: w.cls, tier: "item", order: out.length, verb: "Switch to",
      action: { type: "window-focus", address: w.address } }
    // An empty query keeps the most-recently-used order; a typed one is left to the matcher.
    if (!req.text) row.score = 1000 - out.length
    out.push(row)
  }
  if (req.explicit && !out.length) out.push(status("No other windows are open"))
  return out
}
