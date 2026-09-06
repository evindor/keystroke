.pragma library

// Local selection frecency: opaque hashed ids, decaying weights, timestamps.
// Pure functions over a plain entries object; the host owns the file.

var HALF_LIFE = 14 * 86400
var MAX_ENTRIES = 2000
var MAX_BONUS = 36

function parse(text) {
  var entries = {}
  try {
    var data = JSON.parse(String(text || ""))
    if (!data || data.version !== 1 || typeof data.entries !== "object") return entries
    for (var key in data.entries) {
      var e = data.entries[key]
      if (!e || typeof key !== "string" || key.length !== 32) continue
      var w = Number(e.weight), u = Number(e.updated)
      if (!isFinite(w) || !isFinite(u) || w < 0 || w > 1e6) continue
      entries[key] = { weight: w, updated: u }
    }
  } catch (err) { }
  return entries
}

function serialize(entries) {
  return JSON.stringify({ version: 1, entries: entries }) + "\n"
}

function key(providerId, rowId) {
  return Qt.md5(String(providerId) + "/" + String(rowId))
}

function weight(entries, k, now) {
  var e = entries[k]
  if (!e) return 0
  return e.weight * Math.pow(2, -Math.max(0, now - e.updated) / HALF_LIFE)
}

function bonus(entries, k, now) {
  if (!k) return 0
  return Math.min(MAX_BONUS, 12 * Math.log2(1 + weight(entries, k, now)))
}

function record(entries, k, now) {
  var next = {}
  for (var existing in entries) next[existing] = entries[existing]
  next[k] = { weight: Math.min(1e6, weight(entries, k, now) + 1), updated: now }
  var keys = Object.keys(next)
  if (keys.length > MAX_ENTRIES) {
    keys.sort(function(a, b) { return weight(next, b, now) - weight(next, a, now) })
    var pruned = {}
    for (var i = 0; i < MAX_ENTRIES; i++) pruned[keys[i]] = next[keys[i]]
    next = pruned
  }
  return next
}
