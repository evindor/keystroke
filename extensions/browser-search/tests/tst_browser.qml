import QtQuick
import QtTest
import "../core/Browser.js" as Browser

TestCase {
  name: "BrowserSearch"
  function test_request() {
    var req = Browser.request({ query: "web docs", command: { rest: "docs" }, settings: { history: false }, scope: "" }, "browser-search")
    compare(req.query, "docs")
    verify(req.explicit)
    verify(!req.history && req.bookmarks)
    verify(!Browser.request({ scope: "files" }, "browser-search").allowed)
    verify(Browser.request({ scope: "browser-search", query: " docs " }, "browser-search").explicit)
  }
  function test_argv() {
    var req = { query: "-- $(touch /tmp/nope) ' docs", history: true, bookmarks: false }
    compare(Browser.argv("/tmp/a b/search.py", req), ["python3", "/tmp/a b/search.py", "--history", "1", "--bookmarks", "0", "--", req.query])
    verify(Browser.cacheKey(req) !== Browser.cacheKey({ query: req.query, history: false, bookmarks: true }))
  }
  function test_rows() {
    var data = { browser: "Chromium", results: [
      { url: "https://example.org", title: "Example", history: true, bookmark: true, profile: "Default" },
      { url: "javascript:alert(1)", title: "Unsafe", bookmark: true },
      { url: "https://history.org", title: "History", history: true }
    ] }
    var req = { history: false, bookmarks: true, explicit: true }
    var rows = Browser.rows(data, req)
    compare(rows.length, 1)
    compare(rows[0].accessory, "Bookmark")
    compare(rows[0].action, { type: "url", url: "https://example.org" })
    compare(rows[0].altAction, { type: "copy", text: "https://example.org" })
    verify(!rows[0].remember)
    req.history = true
    compare(Browser.rows(data, req)[0].id, rows[0].id)
    compare(Browser.rows(data, req)[0].accessory, "Bookmark + History")
  }
  function test_errors_and_empty() {
    verify(Browser.parse("invalid").error.length > 0)
    verify(Browser.parse('{"results":{}}').error.length > 0)
    compare(Browser.rows({ results: [], error: "Unsupported" }, { explicit: false }), [])
    compare(Browser.rows({ results: [], error: "Unsupported" }, { explicit: true })[0].title, "Unsupported")
    compare(Browser.rows({ results: [] }, { explicit: true })[0].title, "No matching pages")
  }
}
