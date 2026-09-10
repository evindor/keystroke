.pragma library

// Currency conversion for the Keystroke palette: the query shapes, the
// EUR-based cross rates, the cache the rates live in, when to refresh it,
// and the rows. Pure functions; Service.qml owns the curl process and the
// files. tests/tst_currency.qml covers everything here.
//
//   100 usd to eur · 12,50 eur in tl · $100 in try · 100€ · 129usd

var NAME = "Currency"
var ICON = "󰄔"
var COLOR = "#81c8b6"
// Frankfurter serves the ECB reference rates, one table per working day,
// every currency quoted against the euro. No key, no account.
var URL = "https://api.frankfurter.dev/v2/rates"
var TIMEOUT_S = 15
var RETRY_MS = 10 * 60 * 1000       // after a failed download, try again this much later
var SYMBOLS = { "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₺": "TRY", "₹": "INR", "₩": "KRW", "₽": "RUB", "₴": "UAH", "₪": "ILS", "฿": "THB" }
var ALIASES = { TL: "TRY" }
// Answered before the first download; once a table exists, it decides.
var KNOWN = ("AED ARS AUD BGN BRL CAD CHF CLP CNY COP CZK DKK EGP EUR GBP HKD HUF IDR ILS INR ISK JPY KRW KZT MXN MYR NGN NOK NZD " +
             "PHP PKR PLN RON RUB SAR SEK SGD THB TRY TWD UAH USD VND ZAR").split(" ")

// ----------------------------------------------------------------- parsing

// A symbol, an alias or three letters → an ISO code; "" for anything else.
function code(token) {
  var t = String(token || "").trim()
  if (!t) return ""
  if (SYMBOLS[t]) return SYMBOLS[t]
  var u = t.toUpperCase()
  if (ALIASES[u]) return ALIASES[u]
  return /^[A-Z]{3}$/.test(u) ? u : ""
}

var SYM = "[$€£¥₺₹₩₽₴₪฿]"
var NUM = "[+-]?(?:\\d+(?:[.,]\\d+)?|[.,]\\d+)"
var RE = new RegExp("^\\s*(?:(" + SYM + ")\\s*)?(" + NUM + ")\\s*(" + SYM + "|[a-z]{2,3})?(?:\\s+(?:to|in|into|as)\\s+(" + SYM + "|[a-z]{2,3}))?\\s*$", "i")

// { amount, base, quote, key, explicit } or null. `target` fills in the
// quote when the query names none; an amount in the target itself goes to
// the other side of the euro so the answer is never 1:1.
function parse(query, target) {
  var m = RE.exec(String(query || ""))
  if (!m || (m[1] && m[3]) || (!m[1] && !m[3])) return null
  var base = code(m[1] || m[3]), amount = Number(m[2].replace(",", "."))
  if (!base || !isFinite(amount)) return null
  var explicit = !!m[4]
  var quote = explicit ? code(m[4]) : code(target)
  if (!quote) return null
  if (!explicit && quote === base) quote = base === "EUR" ? "USD" : "EUR"
  return { amount: amount, base: base, quote: quote, key: base + "/" + quote, explicit: explicit }
}

// Whether a code is one the table (or, before the first download, the
// built-in list) can answer for. "100 kgs to lbs" parses; this says no.
function known(c, cache) {
  if (c === "EUR") return true
  if (cache && cache.rates) return !!cache.rates[c]
  return KNOWN.indexOf(c) >= 0
}

// ------------------------------------------------------------------- rates

function crossRate(cache, conversion) {
  if (!cache || cache.base !== "EUR" || !cache.rates) return null
  var source = conversion.base === "EUR" ? { rate: 1, date: "" } : cache.rates[conversion.base]
  var target = conversion.quote === "EUR" ? { rate: 1, date: "" } : cache.rates[conversion.quote]
  if (!source || !target || !(source.rate > 0) || !(target.rate > 0)) return null
  var rate = target.rate / source.rate
  if (!isFinite(rate)) return null
  var dates = [source.date, target.date].filter(function(d) { return !!d })
  dates.sort()
  return { rate: rate, date: dates.length ? (dates[0] === dates[dates.length - 1] ? dates[0] : dates.join(" / ")) : "" }
}

// ------------------------------------------------------------------- cache

// Frankfurter's rows → the table we keep, or null when the answer is not
// what we expect (wrong base, a bad rate, a missing major currency).
function buildCache(rows, fetchedAt) {
  if (!Array.isArray(rows) || !rows.length) return null
  var rates = {}
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i]
    if (!r || r.base !== "EUR" || !/^[A-Z]{3}$/.test(String(r.quote)) || typeof r.rate !== "number" || !isFinite(r.rate) || r.rate <= 0
        || rates[r.quote] || !/^\d{4}-\d{2}-\d{2}$/.test(String(r.date))) return null
    rates[r.quote] = { rate: r.rate, date: r.date }
  }
  if (!rates.USD || !rates.GBP || Object.keys(rates).length < 10) return null
  return { version: 1, base: "EUR", fetchedAt: String(fetchedAt), rates: rates }
}

function parseResponse(text, fetchedAt) {
  try { return buildCache(JSON.parse(String(text || "")), fetchedAt) } catch (e) { return null }
}

// The file on disk, or null when it is not a table we wrote.
function readCache(text) {
  try {
    var c = JSON.parse(String(text || ""))
    return c && c.version === 1 && c.base === "EUR" && c.rates && typeof c.rates === "object" && typeof c.fetchedAt === "string" ? c : null
  } catch (e) { return null }
}

// The table is due for a refresh once the clock passes 04:00 local time
// after it was fetched: the ECB publishes in the afternoon, so one download
// a day, at the first conversion of the day, is always current.
function overdue(fetchedAt, nowMs) {
  var now = new Date(nowMs), boundary = new Date(nowMs)
  boundary.setHours(4, 0, 0, 0)
  if (now < boundary) boundary.setDate(boundary.getDate() - 1)
  var fetched = Date.parse(fetchedAt)
  return !isFinite(fetched) || fetched < boundary.getTime()
}

function shouldFetch(cache, nowMs, fetching, failedAt) {
  if (fetching) return false
  if (cache && !overdue(cache.fetchedAt, nowMs)) return false
  return !(failedAt > 0) || nowMs - failedAt > RETRY_MS
}

// curl through a script that is entirely ours: it creates the two folders
// the service writes to and prints the table to stdout. The folders are
// the only arguments, and they never come from the user.
var FETCH_SCRIPT = 'mkdir -p -- "$1" "$2" && exec curl -sS --fail --max-time ' + TIMEOUT_S + ' -- ' + URL
function fetchArgv(cacheDir, stateDir) {
  return ["bash", "-c", FETCH_SCRIPT, "keystroke-currency", String(cacheDir), String(stateDir)]
}

// ------------------------------------------------------------------ target

// The quote for an amount that names none: the setting, else the locale's
// currency, else USD, each only if the table knows it. In automatic mode,
// the explicit target used most often wins over the preferred one.
function preferredTarget(settings, counts, cache, localeCurrency) {
  var s = settings || {}, fromLocale = code(localeCurrency)
  var wanted = code(s.preferredCurrency) || fromLocale || "USD"
  if (!known(wanted, cache)) wanted = fromLocale && known(fromLocale, cache) ? fromLocale : "USD"
  if (String(s.targetMode) !== "automatic") return wanted
  var winner = wanted, best = Number((counts || {})[wanted]) || 0
  Object.keys(counts || {}).sort().forEach(function(c) {
    var n = counts[c]
    if (known(c, cache) && typeof n === "number" && isFinite(n) && n > best) { winner = c; best = n }
  })
  return winner
}

function readCounts(raw) {
  var counts = {}
  try {
    var data = JSON.parse(String(raw || ""))
    if (!data || data.version !== 1 || !data.counts) return counts
    Object.keys(data.counts).forEach(function(c) {
      var n = data.counts[c]
      if (/^[A-Z]{3}$/.test(c) && typeof n === "number" && isFinite(n) && n > 0) counts[c] = Math.min(Math.floor(n), 1000000)
    })
  } catch (e) { }
  return counts
}

function bump(counts, c) {
  var next = JSON.parse(JSON.stringify(counts || {}))
  next[c] = Math.min((Number(next[c]) || 0) + 1, 1000000)
  return next
}

// ----------------------------------------------------------------- display

function result(conversion, rate) {
  var value = conversion.amount * rate
  return isFinite(value) ? value.toLocaleString(Qt.locale(), "f", 2) + " " + conversion.quote : ""
}

function rateText(rate) { return String(Number(rate.toPrecision(6))) }

// "2026-09-10" → "10 Sep 2026"; two dates joined with " / " stay two.
function dateText(iso) {
  return String(iso || "").split(" / ").map(function(d) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d)
    return m ? Qt.formatDate(new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])), "d MMM yyyy") : d
  }).join(" / ")
}

function fetchedText(fetchedAt, nowMs) {
  var t = Date.parse(fetchedAt)
  if (!isFinite(t)) return "fetched at an unknown time"
  var d = new Date(t), now = new Date(nowMs)
  var sameDay = d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
  return "fetched " + (sameDay ? "today " : Qt.formatDate(d, "d MMM ") ) + Qt.formatTime(d, "HH:mm")
}

// -------------------------------------------------------------------- rows

// One answer row, or one disabled status row while the first table is on
// its way (or failed to arrive), or nothing when a code is not a currency.
function rows(conversion, cache, status, query, nowMs) {
  if (!conversion) return []
  if (!known(conversion.base, cache) || !known(conversion.quote, cache)) return []
  var pair = cache ? crossRate(cache, conversion) : null
  if (pair) {
    var value = result(conversion, pair.rate)
    if (!value) return []
    var detail = "1 " + conversion.base + " = " + rateText(pair.rate) + " " + conversion.quote
    var failed = !!(status && status.error && overdue(cache.fetchedAt, nowMs))
    // The pane shows the first lines: the rate, its date and when it was
    // fetched (with the failure, if a refresh is due and did not happen).
    var row = { id: "conversion", title: value, subtitle: detail + " · rates from " + dateText(pair.date), icon: ICON, section: NAME,
                verb: "Copy result", tier: "answer", score: 195,
                preview: value, previewLabel: "CURRENCY",
                previewDetail: detail + "\nRates from " + dateText(pair.date) + "\n" + fetchedText(cache.fetchedAt, nowMs) + (failed ? " · refresh failed" : "")
                               + "\nFrankfurter (ECB reference rates)" + (failed ? "\n" + status.error : "") + "\nCtrl+Enter copies the number alone",
                action: { type: "copy", text: value }, altAction: { type: "copy", text: (conversion.amount * pair.rate).toFixed(2) } }
    if (conversion.explicit) row.currencyTarget = conversion.quote
    return [row]
  }
  if (cache) return []
  var fetching = !!(status && status.fetching), error = status && status.error
  return [{ id: "status", title: fetching ? "Downloading exchange rates…" : "Exchange rates unavailable",
            subtitle: fetching ? "From Frankfurter, once a day" : (error || "Could not reach Frankfurter") + " · tried again in a few minutes",
            icon: ICON, section: NAME, tier: "answer", score: 195, disabled: true, action: { type: "noop" } }]
}
