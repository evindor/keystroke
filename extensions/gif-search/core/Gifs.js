.pragma library

var PAGE_SIZE = 24
var ICON = "󰵸"

function searchArgv(term, page) {
  var url = "https://gif-search.raycast.com/api/giphy?type=gifs&lang=en&limit=" + PAGE_SIZE + "&offset=" + (page * PAGE_SIZE)
  if (term) url += "&q=" + encodeURIComponent(term)
  return ["curl", "--silent", "--show-error", "--fail", "--max-time", "15", "--max-filesize", "2097152", "--", url]
}

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

function rows(ctx, key) {
  if (ctx.scope && ctx.scope !== key) return []
  var explicit = !!ctx.command || ctx.scope === key
  var term = explicit ? String(ctx.command ? ctx.command.rest : ctx.query || "").trim() : ""
  var row = { id: "gif-search-open", title: "Search GIFs", subtitle: term || "Browse trending GIFs on GIPHY",
    icon: ICON, keywords: "gif giphy reactions", section: "GIF Search", verb: "Browse",
    action: { type: "gif-view", term: term } }
  if (explicit || !ctx.query) row.score = 100
  return [row]
}
