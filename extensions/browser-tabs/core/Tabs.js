.pragma library

var ICON = ""
var SECTION = "Browser tabs"
var APP_SECTION = "Application tabs"
var SETTINGS = [
  { key: "root", type: "boolean", label: "Show tabs in the main search", "default": true,
    description: "Off: tabs appear only after the @ command or on this extension's screen" },
  { key: "rootLimit", type: "number", label: "Tabs in the main search", "default": 5, min: 1, max: 20, integer: true,
    description: "At most this many tabs mix into the main results" },
  { key: "appTabs", type: "boolean", label: "Include application tabs", "default": false,
    description: "On: tabs of GTK and Qt applications that expose them (Nautilus, Pinta, ...) are listed too" }
]

function request(ctx, id) {
  var explicit = !!ctx.command || ctx.scope === id
  var text = String(ctx.command ? ctx.command.rest : ctx.query || "").trim()
  var settings = ctx.settings || {}
  var allowed = explicit || (!ctx.scope && settings.root !== false && text.length >= 2)
  var limit = Math.max(1, Math.min(20, Number(settings.rootLimit) || 5))
  return { explicit: explicit, text: text, allowed: allowed, appTabs: settings.appTabs === true, limit: explicit ? 0 : limit }
}

function argv(helper) { return ["python3", helper, "--json-lines"] }

function scanRequest(id) { return { version: 1, id: id, type: "scan", options: { ghostty: false, ghosttyPalette: false } } }
function activateRequest(id, tab) { return { version: 1, id: id, type: "activate", itemId: String(tab.id), token: String(tab.token) } }
function shutdownRequest(id) { return { version: 1, id: id, type: "shutdown" } }

// The helper's public items, reduced to the tabs this extension shows and the
// token that activates each one. Windows and anything malformed are dropped.
function tabs(items) {
  var out = []
  for (var i = 0; i < (items || []).length; i++) {
    var t = items[i]
    if (!t || (t.kind !== "browser-tab" && t.kind !== "app-tab")) continue
    if (typeof t.id !== "string" || !t.id || typeof t.activationToken !== "string" || !t.activationToken) continue
    out.push({ id: t.id, kind: t.kind, title: String(t.title || "Untitled"), browser: String(t.provider || ""),
      context: String(t.context || ""), active: t.active === true, token: t.activationToken, order: out.length })
  }
  return out
}

// One protocol line in, a description of what changed out. A snapshot for
// another scan (an older, cancelled one) is ignored.
function message(line, scanId) {
  var m
  try { m = JSON.parse(String(line || "")) } catch (_) { return { type: "invalid" } }
  if (!m || m.version !== 1 || typeof m.type !== "string") return { type: "invalid" }
  if (m.type === "ready") return { type: "ready", atspi: !!(m.capabilities && m.capabilities.atspi) }
  if (m.type === "snapshot") {
    if (String(m.requestId || "") !== scanId) return { type: "stale" }
    if (m.full === true) return { type: "full", tabs: tabs(m.items) }
    if (m.provider === "atspi") return { type: "partial", tabs: tabs(m.items) }
    return { type: "other" }
  }
  if (m.type === "activation") return { type: "activation", ok: m.ok === true, message: String(m.message || "") }
  if (m.type === "error") return { type: "error", message: String(m.message || "") }
  return { type: "other" }
}

function signature(list) {
  return list.map(function(t) { return t.id + "\u0001" + t.title }).join("\u0002")
}

// The root shows only a handful of tabs, so it narrows the list itself: every
// word of the query must appear, letters in order, in the title. The host's
// matcher ranks what is left; explicit requests are left entirely to it.
function subsequence(needle, hay) {
  var j = 0
  for (var i = 0; i < hay.length && j < needle.length; i++) if (hay.charAt(i) === needle.charAt(j)) j++
  return j === needle.length
}

function filter(list, req) {
  var out = []
  var words = req.limit ? req.text.toLowerCase().split(/\s+/).filter(function(w) { return !!w }) : []
  for (var i = 0; i < list.length; i++) {
    var t = list[i]
    if (t.kind === "app-tab" && !req.appTabs) continue
    if (req.limit) {
      if (out.length >= req.limit) break
      var hay = t.title.toLowerCase(), ok = true
      for (var k = 0; k < words.length && ok; k++) ok = subsequence(words[k], hay)
      if (!ok) continue
    }
    out.push(t)
  }
  return out
}

function status(title, subtitle) {
  return { id: "status", title: title, subtitle: subtitle || "", icon: ICON, section: SECTION,
    tier: "item", score: 1, disabled: true, action: { type: "noop" } }
}

// iconFor maps a browser or application name to an image URL ("" when none is known).
function rows(list, req, state, iconFor) {
  var out = []
  for (var i = 0; i < list.length; i++) {
    var t = list[i]
    var row = { id: "tab:" + t.id, title: t.title, subtitle: [t.browser, t.active ? "Current tab" : ""].filter(function(s) { return !!s }).join(" · "),
      icon: ICON, iconSource: iconFor ? String(iconFor(t.browser) || "") : "", section: t.kind === "app-tab" ? APP_SECTION : SECTION,
      keywords: t.browser, tier: "item", order: out.length, verb: "Switch to",
      action: { type: "tab-focus", tab: t.id } }
    if (!req.text) row.score = 1000 - out.length
    out.push(row)
  }
  if (!req.explicit || out.length) return out
  if (state.unavailable) return [status("Accessibility is unavailable", "Browser tabs are read through AT-SPI; install at-spi2-core and python-gobject")]
  if (state.scanning && !state.scanned) return [status("Looking for tabs...")]
  return [status("No browser tabs found", "Chromium-based browsers need --force-renderer-accessibility; see the extension's README")]
}
