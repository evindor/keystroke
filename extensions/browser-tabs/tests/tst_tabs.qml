import QtQuick
import QtTest
import "../core/Tabs.js" as Tabs

TestCase {
  name: "BrowserTabs"

  readonly property var items: [
    { id: "hyprland:1", kind: "window", title: "GitHub - Chromium", activationToken: "w" },
    { id: "atspi:1", kind: "browser-tab", provider: "Chromium", title: "GitHub", active: true, activationToken: "v1.a" },
    { id: "atspi:2", kind: "browser-tab", provider: "Chromium", title: "Gmail - Inbox", activationToken: "v1.b" },
    { id: "atspi:3", kind: "app-tab", provider: "Nautilus", title: "Downloads", activationToken: "v1.c" },
    { id: "atspi:4", kind: "browser-tab", provider: "Firefox", title: "No token" },
    { id: "", kind: "browser-tab", title: "No id", activationToken: "v1.d" }
  ]
  readonly property var state: ({ unavailable: false, scanning: false, scanned: true })
  function cmd(rest) { return Tabs.request({ query: "@ " + rest, command: { rest: rest }, scope: "" }, "browser-tabs") }

  function test_request() {
    verify(!Tabs.request({ query: "g", scope: "" }, "browser-tabs").allowed)
    var root = Tabs.request({ query: "gh", scope: "" }, "browser-tabs")
    verify(root.allowed && !root.explicit)
    compare(root.limit, 5)
    verify(!Tabs.request({ query: "github", scope: "", settings: { root: false } }, "browser-tabs").allowed)
    verify(cmd("").explicit)
    compare(cmd("").limit, 0)
  }

  function test_tabs_keep_only_actionable_tabs() {
    var list = Tabs.tabs(items)
    compare(list.map(function(t) { return t.id }), ["atspi:1", "atspi:2", "atspi:3"])
    compare(list[0].token, "v1.a")
    verify(list[0].active)
  }

  function test_messages() {
    compare(Tabs.message('{"version":1,"type":"ready","capabilities":{"atspi":true}}', ""), { type: "ready", atspi: true })
    compare(Tabs.message("garbage", "scan-1").type, "invalid")
    compare(Tabs.message('{"version":1,"type":"snapshot","requestId":"scan-0","full":true,"items":[]}', "scan-1").type, "stale")
    var full = Tabs.message(JSON.stringify({ version: 1, type: "snapshot", requestId: "scan-1", full: true, items: items }), "scan-1")
    compare(full.type, "full")
    compare(full.tabs.length, 3)
    compare(Tabs.message(JSON.stringify({ version: 1, type: "snapshot", requestId: "scan-1", full: false, provider: "hyprland", items: items }), "scan-1").type, "other")
    compare(Tabs.message(JSON.stringify({ version: 1, type: "snapshot", requestId: "scan-1", full: false, provider: "atspi", items: items }), "scan-1").type, "partial")
    compare(Tabs.message('{"version":1,"type":"activation","ok":false,"message":"closed"}', ""), { type: "activation", ok: false, message: "closed" })
  }

  function test_requests() {
    compare(Tabs.scanRequest("scan-1"), { version: 1, id: "scan-1", type: "scan", options: { ghostty: false, ghosttyPalette: false } })
    compare(Tabs.activateRequest("activate-2", { id: "atspi:1", token: "v1.a" }), { version: 1, id: "activate-2", type: "activate", itemId: "atspi:1", token: "v1.a" })
  }

  function test_rows_and_app_tabs_setting() {
    var list = Tabs.tabs(items)
    var rows = Tabs.rows(Tabs.filter(list, cmd("")), cmd(""), state, null)
    compare(rows.length, 2)
    compare(rows[0].subtitle, "Chromium · Current tab")
    compare(rows[0].action, { type: "tab-focus", tab: "atspi:1" })
    verify(rows[0].score > rows[1].score)
    var req = Tabs.request({ query: "@", command: { rest: "" }, scope: "", settings: { appTabs: true } }, "browser-tabs")
    rows = Tabs.rows(Tabs.filter(list, req), req, state, null)
    compare(rows.length, 3)
    compare(rows[2].section, "Application tabs")
  }

  function test_root_filter() {
    var list = Tabs.tabs(items)
    compare(Tabs.filter(list, Tabs.request({ query: "inbx", scope: "" }, "browser-tabs")).map(function(t) { return t.title }), ["Gmail - Inbox"])
    compare(Tabs.filter(list, Tabs.request({ query: "gi", scope: "", settings: { rootLimit: 1 } }, "browser-tabs")).length, 1)
  }

  function test_status_rows() {
    compare(Tabs.rows([], cmd(""), { unavailable: true }, null)[0].title, "Accessibility is unavailable")
    compare(Tabs.rows([], cmd(""), { scanning: true, scanned: false }, null)[0].title, "Looking for tabs...")
    compare(Tabs.rows([], cmd(""), state, null)[0].title, "No browser tabs found")
    compare(Tabs.rows([], Tabs.request({ query: "gh", scope: "" }, "browser-tabs"), state, null).length, 0)
  }
}
