.pragma library

var ICON = "󰖟"
var SETTINGS = [
  { key: "history", type: "boolean", label: "Search history", "default": true,
    description: "Include pages visited in your default browser" },
  { key: "bookmarks", type: "boolean", label: "Search bookmarks", "default": true,
    description: "Include bookmarks saved in your default browser" }
]

function request(ctx, id) {
  var explicit = !!ctx.command || ctx.scope === id
  var query = String(ctx.command ? ctx.command.rest : ctx.query || "").trim().slice(0, 512)
  var settings = ctx.settings || {}
  return { query: query, explicit: explicit, history: settings.history !== false,
    bookmarks: settings.bookmarks !== false, allowed: !ctx.scope || ctx.scope === id }
}

function cacheKey(req) { return JSON.stringify([req.query, req.history, req.bookmarks]) }

function argv(helper, req) {
  return ["python3", helper, "--history", req.history ? "1" : "0", "--bookmarks", req.bookmarks ? "1" : "0", "--", req.query]
}

function parse(text) {
  try {
    var value = JSON.parse(text)
    if (value && Array.isArray(value.results) && typeof value.browser === "string") return value
  } catch (_) {}
  return { browser: "", results: [], error: "Browser search could not read browser data" }
}

function status(title, subtitle) {
  return { id: "status", title: title, subtitle: subtitle || "", icon: ICON, section: "Browser search",
    tier: "item", score: 1, disabled: true, action: { type: "noop" } }
}

function rows(result, req) {
  var out = [], items = result.results || []
  for (var i = 0; i < items.length && out.length < (req.explicit ? 30 : 8); i++) {
    var item = items[i]
    if (!item || typeof item.url !== "string" || !/^https?:\/\//i.test(item.url)) continue
    var bookmark = req.bookmarks && item.bookmark, history = req.history && item.history
    if (!bookmark && !history) continue
    var source = bookmark && history ? "Bookmark + History" : bookmark ? "Bookmark" : "History"
    out.push({ id: item.url, title: item.title || item.url, subtitle: item.url,
      icon: bookmark ? "󰃀" : ICON, section: "Browser search", accessory: source,
      keywords: item.url, tier: "item", score: 60 - out.length, remember: false,
      preview: item.url, previewLabel: source, previewDetail: result.browser + " · " + (item.profile || ""),
      verb: "Open", hint: "↵ opens · ctrl ↵ copies URL",
      action: { type: "url", url: item.url }, altAction: { type: "copy", text: item.url } })
  }
  if (req.explicit && result.error) out.push(status(result.error, result.browser))
  else if (req.explicit && !out.length) out.push(status("No matching pages", result.browser))
  return out
}
