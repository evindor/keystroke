import QtQuick
import QtTest
import "../core/Gifs.js" as Gifs

TestCase {
  name: "Gifs"
  function test_command() {
    var rows = Gifs.rows({ query: "reaction cats", command: { rest: "cats" } }, "gif-search")
    compare(rows[0].action.term, "cats")
    compare(rows[0].id, Gifs.rows({ query: "", command: { rest: "dogs" } }, "gif-search")[0].id)
    compare(Gifs.rows({ query: "cats", scope: "other" }, "gif-search").length, 0)
    verify(Gifs.rows({ query: "unrelated" }, "gif-search")[0].score === undefined)
    // Without a key the root row says so instead of promising a search.
    var unset = Gifs.rows({ query: "", command: { rest: "" } }, "gif-search", true)[0]
    compare(unset.verb, "Set up")
    verify(unset.subtitle.indexOf("GIPHY API key") !== -1)
  }
  function test_argv() {
    var argv = Gifs.searchArgv("/h/search.py", "cats & dogs; $(whoami)", 2, "pg-13")
    compare(argv[0], "python3")
    compare(argv[1], "/h/search.py")
    compare(argv[2], "search")
    compare(argv[argv.indexOf("--offset") + 1], "48")
    compare(argv[argv.indexOf("--limit") + 1], "24")
    compare(argv[argv.indexOf("--rating") + 1], "pg-13")
    // The term travels as one argv element, never spliced into a URL or a shell.
    compare(argv[argv.indexOf("--query") + 1], "cats & dogs; $(whoami)")
    // The key is not in argv at all; the helper reads it from the environment.
    verify(argv.every(function(a) { return a.indexOf("api_key") === -1 }))
    var trending = Gifs.searchArgv("/h/search.py", "", 0, "g")
    compare(trending[2], "trending")
    verify(trending.indexOf("--query") === -1)
    // An unknown rating falls back to the safest one rather than reaching GIPHY.
    compare(Gifs.searchArgv("/h/s.py", "x", 0, "nonsense")[argv.indexOf("--rating") + 1], "g")
  }
  function test_media_url() {
    compare(Gifs.mediaUrl("https://giphy.com.evil.test/a.gif"), "")
    compare(Gifs.mediaUrl("file:///tmp/a.gif"), "")
    compare(Gifs.mediaUrl("https://user@giphy.com/a.gif"), "")
  }
  function test_settings() {
    var byKey = ({})
    Gifs.SETTINGS.forEach(function(s) { byKey[s.key] = s })
    verify(byKey.apiKey.secret)
    compare(byKey.apiKey.type, "string")
    compare(byKey.apiKey.setup.url, Gifs.SIGNUP_URL)
    verify(byKey.apiKey.setup.notice.indexOf("not set") !== -1)
    compare(byKey.rating["default"], "g")
    compare(byKey.rating.options, Gifs.RATINGS)
  }
  function test_response() {
    var gif = { id: "a", title: "Cat", images: { original: { url: "https://media.giphy.com/a.gif" }, preview_gif: { url: "https://media.giphy.com/small.gif" } } }
    var result = Gifs.parse(JSON.stringify({ data: [null, {}, gif, gif], pagination: { offset: 0, count: 4, total_count: 10 } }))
    compare(result.items.length, 1)
    compare(result.items[0].id, "a")
    verify(result.more)
    compare(Gifs.parse('{"data":[]}').items.length, 0)
    verify(!Gifs.parse('{"data":[]}').more)
    var failed = false
    try { Gifs.parse('{"error":"rate limited"}') } catch (e) { failed = true }
    verify(failed)
  }
}
