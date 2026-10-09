import QtQuick
import QtTest
import "../core/Windows.js" as Windows

TestCase {
  name: "Windows"

  readonly property var clients: [
    { address: "0xaaa", mapped: true, hidden: false, "class": "chromium", title: "GitHub - Chromium", workspace: { id: 1, name: "1" }, focusHistoryID: 2 },
    { address: "0xbbb", mapped: true, hidden: false, "class": "Alacritty", title: "nvim README.md", workspace: { id: 2, name: "2" }, focusHistoryID: 0 },
    { address: "0xccc", mapped: true, hidden: false, "class": "obsidian", title: "Notes", workspace: { id: -98, name: "special:scratchpad" }, focusHistoryID: 1 },
    { address: "0xddd", mapped: false, "class": "ghost", title: "Unmapped", workspace: { id: 1, name: "1" }, focusHistoryID: 3 },
    { address: "0xeee; exit", mapped: true, "class": "evil", title: "Bad address", workspace: { id: 1, name: "1" }, focusHistoryID: 4 },
    { address: "fff", mapped: true, "class": "Spotify", title: "", initialTitle: "Spotify", workspace: { id: 7, name: "music" }, focusHistoryID: 5 }
  ]

  function test_request() {
    verify(!Windows.request({ query: "a", scope: "" }, "windows").allowed)
    var root = Windows.request({ query: "ch", scope: "" }, "windows")
    verify(root.allowed && !root.explicit)
    compare(root.limit, 5)
    verify(!Windows.request({ query: "chrome", scope: "", settings: { root: false } }, "windows").allowed)
    verify(!Windows.request({ query: "chrome", scope: "files" }, "windows").allowed)
    var cmd = Windows.request({ query: ">", command: { rest: "" }, scope: "", settings: { root: false } }, "windows")
    verify(cmd.allowed && cmd.explicit)
    compare(cmd.limit, 0)
    compare(Windows.request({ query: "ch", scope: "", settings: { rootLimit: 99 } }, "windows").limit, 20)
  }

  function test_addresses_are_validated() {
    compare(Windows.address("0xABC"), "0xabc")
    compare(Windows.address("abc"), "0xabc")
    compare(Windows.address("0xeee; exit"), "")
    compare(Windows.address(""), "")
    compare(Windows.focusCommand("0xabc", false), "focuswindow address:0xabc")
    compare(Windows.focusCommand("0xabc", true), "hl.dsp.focus({ window = \"address:0xabc\" })")
    compare(Windows.focusCommand("\") os.exit(", true), "")
  }

  function test_windows_most_recent_first_focused_last() {
    var list = Windows.windows(clients)
    compare(list.map(function(w) { return w.address }), ["0xccc", "0xaaa", "0xfff", "0xbbb"])
    compare(list[0].workspace, "Scratchpad")
    compare(list[1].workspace, "Workspace 1")
    compare(list[2].workspace, "music")
    compare(list[2].title, "Spotify")
  }

  function test_came_from_only_on_the_current_workspace() {
    // On workspace 2 the last focused window (0xbbb) is the one you came from.
    var list = Windows.windows(clients, 2)
    verify(list[3].current && list[3].address === "0xbbb")
    // On an empty workspace it is elsewhere: listed first, like any other.
    list = Windows.windows(clients, 3)
    compare(list.map(function(w) { return w.address }), ["0xbbb", "0xccc", "0xaaa", "0xfff"])
    verify(!list[0].current)
    compare(Windows.rows(list, Windows.request({ query: ">", command: { rest: "" }, scope: "" }, "windows"), null).length, 4)
    // Focused in the scratchpad shown over workspace 3: still the one you came from.
    var scratch = [{ address: "0x1", "class": "a", title: "A", workspace: { id: -98, name: "special:scratchpad" }, focusHistoryID: 0 },
                   { address: "0x2", "class": "b", title: "B", workspace: { id: 1, name: "1" }, focusHistoryID: -1 }]
    list = Windows.windows(scratch, 3)
    verify(list[1].current && list[1].address === "0x1")
    compare(list[0].focus, 999)   // a window missing from the focus history sorts after the known ones
  }

  function test_rows_skip_focused_unless_asked() {
    var list = Windows.windows(clients)
    var req = Windows.request({ query: ">", command: { rest: "" }, scope: "" }, "windows")
    var rows = Windows.rows(list, req, null)
    compare(rows.length, 3)
    compare(rows[0].title, "Notes")
    compare(rows[0].subtitle, "obsidian · Scratchpad")
    compare(rows[0].action, { type: "window-focus", address: "0xccc" })
    verify(rows[0].score > rows[1].score)
    req.current = true
    compare(Windows.rows(list, req, null).length, 4)
  }

  function test_typed_rows_are_left_to_the_matcher() {
    var req = Windows.request({ query: "> git", command: { rest: "git" }, scope: "" }, "windows")
    var rows = Windows.rows(Windows.windows(clients), req, null)
    compare(rows[0].score, undefined)
    compare(rows[0].keywords, "obsidian")
  }

  function test_root_filter_narrows_and_caps() {
    var list = Windows.windows(clients)
    var req = Windows.request({ query: "chrm", scope: "" }, "windows")
    compare(Windows.filter(list, req).map(function(w) { return w.address }), ["0xaaa"])
    req = Windows.request({ query: "nvim", scope: "" }, "windows")
    compare(Windows.filter(list, req).length, 0)   // the focused window stays out
    req = Windows.request({ query: "o", scope: "", settings: { rootLimit: 1 } }, "windows")
    req.text = "o"
    compare(Windows.filter(list, req).length, 1)
  }

  function test_root_cap_keeps_the_obvious_hit() {
    // Five recent windows hold c..h..r scattered through their titles; the
    // least recent one is Chromium. The cap must not cut it.
    var many = ["Archive Manager", "nvim ~/omarchy/README.md", "Calendar - Thursday", "Chess - Match history report", "Archive: march photos"]
      .map(function(t, i) { return { address: "0x" + (i + 1), "class": "app", title: t, workspace: { id: 1, name: "1" }, focusHistoryID: i + 1 } })
      .concat([{ address: "0x9", "class": "chromium", title: "GitHub - Chromium", workspace: { id: 2, name: "2" }, focusHistoryID: 9 }])
    var list = Windows.windows(many)
    var picked = Windows.filter(list, Windows.request({ query: "chr", scope: "" }, "windows"))
    compare(picked.length, 5)
    compare(picked[0].address, "0x9")
    // Same tier: most recently used first ("arch" starts a word in both archives, appears inside "omarchy").
    picked = Windows.filter(list, Windows.request({ query: "arch", scope: "" }, "windows"))
    compare(picked.map(function(w) { return w.address }), ["0x1", "0x5", "0x2"])
    compare(Windows.quality(["git", "chr"], "github - chromium chromium"), 0)
    compare(Windows.quality(["hub"], "github - chromium"), 1)
    compare(Windows.quality(["gtb"], "github - chromium"), 2)
    compare(Windows.quality(["xyz"], "github - chromium"), -1)
  }

  function test_empty_explicit_list_says_so() {
    var req = Windows.request({ query: ">", command: { rest: "" }, scope: "" }, "windows")
    var rows = Windows.rows([], req, null)
    compare(rows.length, 1)
    verify(rows[0].disabled)
  }
}
