import QtQuick
import QtTest
import "../core/Currency.js" as Currency

TestCase {
  name: "Currency"
  property var table: ({ version: 1, base: "EUR", fetchedAt: "2026-09-10T08:00:00Z",
                         rates: { USD: { rate: 1.2, date: "2026-09-10" }, TRY: { rate: 60, date: "2026-09-10" }, GBP: { rate: 0.8, date: "2026-09-10" }, JPY: { rate: 170, date: "2026-09-10" } } })
  function rows(code, rate) { return [{ base: "EUR", quote: code, rate: rate, date: "2026-09-10" }] }
  function goodRows() {
    var out = [], codes = ["USD", "GBP", "TRY", "JPY", "CHF", "CAD", "AUD", "SEK", "NOK", "DKK", "PLN"]
    for (var i = 0; i < codes.length; i++) out.push({ base: "EUR", quote: codes[i], rate: i + 1.5, date: "2026-09-10" })
    return out
  }

  function test_queries() {
    compare(Currency.parse("100 usd to try"), { amount: 100, base: "USD", quote: "TRY", key: "USD/TRY", explicit: true })
    compare(Currency.parse("12,50 eur in tl").amount, 12.5)
    compare(Currency.parse("12,50 eur in tl").quote, "TRY")
    compare(Currency.parse("100 USD into GBP").quote, "GBP")
    compare(Currency.parse("$100 in eur"), { amount: 100, base: "USD", quote: "EUR", key: "USD/EUR", explicit: true })
    compare(Currency.parse("100€ to $").key, "EUR/USD")
    compare(Currency.parse("£ 20 in try").base, "GBP")
    compare(Currency.parse("100 usd to tr"), null)
    compare(Currency.parse("$100 usd to eur"), null)      // a symbol and a code both naming the base
    compare(Currency.parse("2m in feet"), null)
    compare(Currency.parse("10 mb in kb"), null)
    compare(Currency.parse("100", "EUR"), null)
    compare(Currency.parse("sqrt(144)", "EUR"), null)
    compare(Currency.parse("", "EUR"), null)
  }

  function test_implicit_target() {
    compare(Currency.parse("129usd", "TRY").quote, "TRY")
    compare(Currency.parse("129 usd", "EUR").quote, "EUR")
    compare(Currency.parse("129usd", "TRY").explicit, false)
    compare(Currency.parse("129 usd to eur", "TRY").quote, "EUR")
    compare(Currency.parse("129 usd to", "TRY"), null)
    compare(Currency.parse("129 usd to e", "TRY"), null)
    compare(Currency.parse("12,50eur", "TL").quote, "TRY")
    compare(Currency.parse("100 usd", "USD").quote, "EUR")      // never 1:1
    compare(Currency.parse("100 eur", "EUR").quote, "USD")
    compare(Currency.parse("100 eur", ""), null)
  }

  function test_known_codes() {
    verify(Currency.known("USD", null) && Currency.known("EUR", null) && !Currency.known("KGS", null))
    verify(Currency.known("JPY", table) && Currency.known("EUR", table) && !Currency.known("CHF", table))
  }

  function test_preferred_target() {
    compare(Currency.preferredTarget({ preferredCurrency: "TRY", targetMode: "preferred" }, { USD: 10 }, table, "USD"), "TRY")
    compare(Currency.preferredTarget({ preferredCurrency: "tl", targetMode: "preferred" }, {}, table, "USD"), "TRY")
    compare(Currency.preferredTarget({ preferredCurrency: "", targetMode: "preferred" }, {}, table, "GBP"), "GBP")
    compare(Currency.preferredTarget({ preferredCurrency: "", targetMode: "preferred" }, {}, table, ""), "USD")
    compare(Currency.preferredTarget({ preferredCurrency: "CHF", targetMode: "preferred" }, {}, table, "GBP"), "GBP")   // not in the table: the locale's
    compare(Currency.preferredTarget({ preferredCurrency: "CHF", targetMode: "preferred" }, {}, table, "XXX"), "USD")
    compare(Currency.preferredTarget({ preferredCurrency: "", targetMode: "preferred" }, {}, null, "PLN"), "PLN")       // before the first download
    compare(Currency.preferredTarget({ preferredCurrency: "TRY", targetMode: "automatic" }, { USD: 10, TRY: 2 }, table, ""), "USD")
    compare(Currency.preferredTarget({ preferredCurrency: "TRY", targetMode: "automatic" }, {}, table, ""), "TRY")
    compare(Currency.preferredTarget({ preferredCurrency: "TRY", targetMode: "automatic" }, { USD: 2, TRY: 2 }, table, ""), "TRY")
    compare(Currency.preferredTarget({ preferredCurrency: "TRY", targetMode: "automatic" }, { XYZ: 100, GBP: 3 }, table, ""), "GBP")
    compare(Currency.readCounts('{"version":1,"counts":{"TRY":3,"USD":-2,"invalid":7}}'), { TRY: 3 })
    compare(Currency.readCounts("broken"), {})
    compare(Currency.bump({ TRY: 3 }, "TRY"), { TRY: 4 })
    compare(Currency.bump({}, "USD"), { USD: 1 })
  }

  function test_cross_rates() {
    var cache = { base: "EUR", rates: { USD: { rate: 1.2, date: "2026-09-10" }, TRY: { rate: 60, date: "2026-09-10" } } }
    compare(Currency.crossRate(cache, Currency.parse("100 usd to try")).rate, 50)
    compare(Currency.crossRate(cache, Currency.parse("100 eur to try")).rate, 60)
    compare(Currency.crossRate(cache, Currency.parse("100 try to eur")).rate, 1 / 60)
    compare(Currency.crossRate(cache, Currency.parse("100 usd to gbp")), null)
    compare(Currency.crossRate(cache, Currency.parse("100 usd to try")).date, "2026-09-10")
    cache.rates.USD.date = "2026-09-09"
    compare(Currency.crossRate(cache, Currency.parse("100 usd to try")).date, "2026-09-09 / 2026-09-10")
    compare(Currency.result(Currency.parse("100 usd to try"), 50), (5000).toLocaleString(Qt.locale(), "f", 2) + " TRY")
    compare(Currency.rateText(1 / 60), "0.0166667")
    compare(Currency.dateText("2026-09-09 / 2026-09-10"), "9 Sep 2026 / 10 Sep 2026")
  }

  function test_table_validation() {
    var built = Currency.buildCache(goodRows(), "2026-09-10T08:00:00Z")
    verify(built && built.version === 1 && built.base === "EUR" && built.rates.USD.rate === 1.5 && built.fetchedAt === "2026-09-10T08:00:00Z")
    compare(Currency.buildCache([], "x"), null)
    compare(Currency.buildCache(goodRows().slice(0, 3), "x"), null)                         // too few to be the real table
    var bad = goodRows(); bad[0].rate = 0
    compare(Currency.buildCache(bad, "x"), null)
    bad = goodRows(); bad[1].base = "USD"
    compare(Currency.buildCache(bad, "x"), null)
    bad = goodRows(); bad[2].date = "yesterday"
    compare(Currency.buildCache(bad, "x"), null)
    bad = goodRows(); bad.push(goodRows()[0])
    compare(Currency.buildCache(bad, "x"), null)                                            // a duplicate
    bad = goodRows(); bad[3].rate = "170"
    compare(Currency.buildCache(bad, "x"), null)
    verify(Currency.parseResponse(JSON.stringify(goodRows()), "x") !== null)
    compare(Currency.parseResponse("<html>", "x"), null)
    compare(Currency.parseResponse('{"message":"not found"}', "x"), null)
    verify(Currency.readCache(JSON.stringify(built)) !== null)
    compare(Currency.readCache('{"version":2}'), null)
    compare(Currency.readCache(""), null)
  }

  function test_refresh_boundary() {
    var fetched = new Date(2026, 8, 10, 5).toISOString()
    verify(!Currency.overdue(fetched, new Date(2026, 8, 11, 3, 59).getTime()))
    verify(Currency.overdue(fetched, new Date(2026, 8, 11, 4).getTime()))
    verify(Currency.overdue("invalid", Date.now()))
    var fresh = { fetchedAt: fetched }, now = new Date(2026, 8, 10, 12).getTime(), later = new Date(2026, 8, 12, 12).getTime()
    verify(Currency.shouldFetch(null, now, false, 0))
    verify(!Currency.shouldFetch(null, now, true, 0))                                  // one at a time
    verify(!Currency.shouldFetch(fresh, now, false, 0))
    verify(Currency.shouldFetch(fresh, later, false, 0))
    verify(!Currency.shouldFetch(fresh, later, false, later - 1000))                   // failed a second ago: wait
    verify(Currency.shouldFetch(fresh, later, false, later - Currency.RETRY_MS - 1))
  }

  function test_fetch_argv() {
    var argv = Currency.fetchArgv("/h/.cache/keystroke/currency", "/h/.local/state/keystroke/currency")
    compare(argv.slice(0, 2), ["bash", "-c"])
    verify(argv[2].indexOf("curl -sS --fail --max-time 15 -- https://api.frankfurter.dev/v2/rates") > 0)
    verify(argv[2].indexOf('mkdir -p -- "$1" "$2"') === 0)
    compare(argv.slice(3), ["keystroke-currency", "/h/.cache/keystroke/currency", "/h/.local/state/keystroke/currency"])
  }

  function test_rows() {
    var now = new Date(2026, 8, 10, 9).getTime()
    var out = Currency.rows(Currency.parse("100 usd to try"), table, { fetching: false, error: "" }, "100 usd to try", now)
    compare(out.length, 1)
    compare(out[0].title, (5000).toLocaleString(Qt.locale(), "f", 2) + " TRY")
    compare(out[0].subtitle, "1 USD = 50 TRY · rates from 10 Sep 2026")
    compare(out[0].action, { type: "copy", text: out[0].title })
    compare(out[0].altAction, { type: "copy", text: "5000.00" })
    compare(out[0].currencyTarget, "TRY")
    verify(out[0].previewDetail.indexOf("Frankfurter") > 0)
    compare(Currency.rows(Currency.parse("129usd", "TRY"), table, {}, "129usd", now)[0].currencyTarget, undefined)
    compare(Currency.rows(Currency.parse("100 kgs to lbs"), table, {}, "100 kgs to lbs", now), [])
    compare(Currency.rows(Currency.parse("100 usd to chf"), table, {}, "100 usd to chf", now), [])   // not in this table
    compare(Currency.rows(Currency.parse("100 kgs to lbs"), null, { fetching: true }, "100 kgs to lbs", now), [])
    var waiting = Currency.rows(Currency.parse("100 usd to chf"), null, { fetching: true }, "100 usd to chf", now)
    compare(waiting.length, 1)
    compare(waiting[0].title, "Downloading exchange rates…")
    verify(waiting[0].disabled)
    var failed = Currency.rows(Currency.parse("100 usd to chf"), null, { fetching: false, error: "curl exited with code 6" }, "100 usd to chf", now)
    compare(failed[0].title, "Exchange rates unavailable")
    verify(failed[0].subtitle.indexOf("curl exited with code 6") === 0)
    var stale = Currency.rows(Currency.parse("100 usd to try"), table, { fetching: false, error: "curl exited with code 6" }, "100 usd to try", now + 3 * 86400000)
    verify(stale[0].previewDetail.indexOf("Refresh failed: curl exited with code 6") > 0)
  }
}
