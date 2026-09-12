.pragma library

var PAGE_SIZE = 24
var ICON = "󰵸"
var SIGNUP_URL = "https://developers.giphy.com/dashboard/"
var RATINGS = ["g", "pg", "pg-13", "r"]

// GIPHY splits what one endpoint used to answer: /search needs q, /trending
// refuses it. The key never appears here -- the helper reads it from the
// environment, because /proc/<pid>/cmdline is world readable.
function searchArgv(helper, term, page, rating) {
  var argv = ["python3", helper, term ? "search" : "trending",
              "--offset", String(page * PAGE_SIZE), "--limit", String(PAGE_SIZE),
              "--rating", RATINGS.indexOf(rating) >= 0 ? rating : RATINGS[0]]
  return term ? argv.concat(["--query", term]) : argv
}

var SETTINGS = [
  { key: "apiKey", type: "string", label: "GIPHY API key", "default": "", secret: true,
    description: "A free key from the GIPHY developer dashboard",
    // No hint: the row is narrow, and a hint here elides the notice itself.
    // The footer already shows the verb against ↵, and the preview the URL.
    setup: { notice: "GIPHY API key is not set", detail: "GIF Search needs your own free key from GIPHY",
             verb: "Get a key", icon: "󰌆", url: SIGNUP_URL } },
  { key: "rating", type: "enum", label: "Content rating", "default": "g", options: RATINGS,
    optionLabels: { g: "G — all audiences", pg: "PG", "pg-13": "PG-13", r: "R" },
    description: "The widest rating GIPHY may return" },
  { key: "defaultAction", type: "enum", label: "Default action", "default": "image",
    options: ["image", "link"], optionLabels: { image: "Copy image", link: "Copy link" },
    description: "Enter uses this action; Ctrl+Enter uses the other" },
  { key: "closeAfterCopy", type: "boolean", label: "Close after copy", "default": false }
]

function mediaUrl(value) {
  var url = String(value || "")
  return /^https:\/\/(?:[a-z0-9-]+\.)*giphy\.com\/[^\s]*$/i.test(url) ? url : ""
}

function parse(text) {
  var body = JSON.parse(text)
  if (!body || !Array.isArray(body.data) || (body.meta && Number(body.meta.status) !== 200)) throw new Error("GIPHY returned an unreadable response")
  var seen = {}, items = []
  body.data.slice(0, PAGE_SIZE).forEach(function(gif) {
    if (!gif || !gif.id || !gif.images) return
    var images = gif.images, url = mediaUrl(images.original && images.original.url)
    var preview = mediaUrl(images.fixed_height_small && images.fixed_height_small.url) || mediaUrl(images.preview_gif && images.preview_gif.url)
    if (!url || !preview || seen[gif.id]) return
    seen[gif.id] = true
    items.push({ id: String(gif.id), title: String(gif.title || "Untitled GIF"), url: url, preview: preview })
  })
  var p = body.pagination
  return { items: items, more: p ? Number(p.offset) + Number(p.count) < Number(p.total_count) : body.data.length === PAGE_SIZE }
}

function rows(ctx, key, needsKey) {
  if (ctx.scope && ctx.scope !== key) return []
  var explicit = !!ctx.command || ctx.scope === key
  var term = explicit ? String(ctx.command ? ctx.command.rest : ctx.query || "").trim() : ""
  var row = { id: "gif-search-open", title: "Search GIFs",
    subtitle: needsKey ? "Needs a free GIPHY API key — open to set one up" : (term || "Browse trending GIFs on GIPHY"),
    icon: ICON, keywords: "gif giphy reactions", section: "GIF Search", verb: needsKey ? "Set up" : "Browse",
    action: { type: "gif-view", term: term } }
  if (explicit || !ctx.query) row.score = 100
  return [row]
}
