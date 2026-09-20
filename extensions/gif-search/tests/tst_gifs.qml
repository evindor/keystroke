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
  }
  function test_url() {
    var argv = Gifs.searchArgv("cats & dogs; $(whoami)", 2)
    compare(argv[argv.length - 2], "--")
    verify(argv[argv.length - 1].indexOf("offset=48") !== -1)
    verify(argv[argv.length - 1].indexOf("q=cats%20%26%20dogs%3B%20%24(whoami)") !== -1)
    verify(Gifs.searchArgv("", 0).pop().indexOf("&q=") === -1)
    compare(Gifs.mediaUrl("https://giphy.com.evil.test/a.gif"), "")
    compare(Gifs.mediaUrl("file:///tmp/a.gif"), "")
    compare(Gifs.mediaUrl("https://user@giphy.com/a.gif"), "")
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
