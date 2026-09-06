.pragma library

// Provisional matcher and host-owned ranking. A better fuzzy matcher is
// deferred by design; every provider goes through match() so a replacement is
// a one-file change. Scores are meaningful only within a tier.

var TIERS = { answer: 3, item: 2, fallback: 1 }
var WORD = /[a-z0-9_ª-￿]+/g

function words(text) {
  return String(text || "").toLowerCase().match(WORD) || []
}

// Prefer whole words; allow only short gaps within a closely matching word.
function match(query, title, keywords) {
  var q = String(query || "").toLowerCase().trim()
  var name = String(title || "").toLowerCase()
  if (!q) return 1
  if (q === name) return 120
  var terms = words(q)
  var ws = words(name)
  if (!terms.length) return 0
  var i, w
  if (terms.length === 1) {
    for (i = 0; i < ws.length; i++) if (ws[i] === q) return 112 - Math.min(i, 3)
    var best = 0
    for (i = 0; i < ws.length; i++) {
      w = ws[i]
      if (w.indexOf(q) === 0) best = Math.max(best, 100 + 10 * q.length / w.length - Math.min(i, 3))
    }
    if (best) return best
  }
  if (allPrefixed(terms, ws)) return 95
  if (q.length >= 3 && name.indexOf(q) >= 0) return 78
  var meta = words(keywords)
  if (allPrefixed(terms, ws.concat(meta))) return 60
  if (terms.length === 1 && q.length >= 3) {
    for (i = 0; i < ws.length; i++) {
      w = ws[i]
      if (w.charAt(0) !== q.charAt(0) || q.length / w.length < 0.65) continue
      var pos = -1, gaps = 0, ok = true
      for (var c = 0; c < q.length; c++) {
        var nxt = w.indexOf(q.charAt(c), pos + 1)
        if (nxt < 0) { ok = false; break }
        gaps += nxt - pos - 1
        pos = nxt
      }
      if (ok && gaps <= 2) return 45 - gaps * 5
    }
  }
  return 0
}

function allPrefixed(terms, ws) {
  for (var t = 0; t < terms.length; t++) {
    var found = false
    for (var i = 0; i < ws.length; i++) if (ws[i].indexOf(terms[t]) === 0) { found = true; break }
    if (!found) return false
  }
  return true
}

function tierValue(row) {
  return TIERS[row && row.tier] || TIERS.item
}

// bonus(row) is the frecency bonus; it only ever reorders within the item
// tier, so learning can never promote a row above a computed answer or push
// a fallback above a real match.
function rank(rows, bonus) {
  var out = rows.slice()
  out.sort(function(a, b) {
    var ta = tierValue(a), tb = tierValue(b)
    if (ta !== tb) return tb - ta
    var sa = Number(a.score || 0), sb = Number(b.score || 0)
    if (ta === TIERS.item && bonus) { sa += bonus(a); sb += bonus(b) }
    if (sa !== sb) return sb - sa
    var oa = a.order === undefined ? 50 : a.order, ob = b.order === undefined ? 50 : b.order
    if (oa !== ob) return oa - ob
    var na = String(a.title || "").toLowerCase(), nb = String(b.title || "").toLowerCase()
    return na < nb ? -1 : na > nb ? 1 : 0
  })
  return out
}
