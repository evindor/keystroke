import QtQuick
import QtTest
import "../core/Herdr.js" as Herdr

TestCase {
  name: "Herdr"

  readonly property var snap: ({
    focused_pane_id: "pane-1",
    workspaces: [ { workspace_id: "workspace-1", number: 1, label: "Project", tab_count: 1, pane_count: 2, agent_status: "working" },
                  { workspace_id: "", label: "No id" } ],
    tabs: [ { tab_id: "tab-1", workspace_id: "workspace-1", number: 1, label: "1", agent_status: "unknown" } ],
    panes: [ { pane_id: "pane-1", cwd: "/home/me/project", terminal_title_stripped: "Implement feature" },
             { pane_id: "pane-2", cwd: "/home/me/project", foreground_cwd: "/home/me/project/api", terminal_title: "" },
             { pane_id: "pane\nbad" } ],
    agents: [ { pane_id: "pane-1", agent: "claude", agent_status: "working", foreground_cwd: "/home/me/project/src", terminal_title_stripped: "Implement feature" } ]
  })
  readonly property string sample: JSON.stringify({ sessions: [
    { name: "default", windows: ["0xabc"], snapshot: snap },
    { name: "work", error: "socket closed" },
    { name: "", snapshot: snap }
  ] })
  function cmd(rest) { return { query: "% " + rest, command: { rest: rest }, scope: "" } }

  function test_request() {
    verify(!Herdr.request({ query: "c", scope: "" }, "herdr").allowed)
    verify(Herdr.request({ query: "cl", scope: "" }, "herdr").allowed)
    verify(!Herdr.request({ query: "claude", scope: "", settings: { root: false } }, "herdr").allowed)
    verify(!Herdr.request({ query: "claude", scope: "windows" }, "herdr").allowed)
    var r = Herdr.request(cmd(""), "herdr")
    verify(r.allowed && r.explicit && r.panes && r.tabs)
    verify(Herdr.request({ query: "", scope: "herdr" }, "herdr").explicit)
  }

  function test_parse_drops_unsafe_ids() {
    var data = Herdr.parse(sample)
    compare(data.sessions.length, 2)
    compare(data.sessions[0].workspaces.length, 1)
    compare(data.sessions[0].panes.length, 2)
    verify(data.sessions[0].attached)
    compare(data.sessions[1].error, "socket closed")
    verify(Herdr.parse("nope").error.length > 0)
  }

  function test_explicit_rows_grouped_agents_first() {
    var rows = Herdr.rows(Herdr.parse(sample), Herdr.request(cmd(""), "herdr"), "/x/herdr.py", "/home/me")
    compare(rows.map(function(r) { return r.section }),
            ["Herdr agents", "Herdr workspaces", "Herdr tabs", "Herdr panes", "Herdr sessions"])
    compare(rows[0].title, "Implement feature")
    compare(rows[0].subtitle, "Claude · ~/project/src · default")
    compare(rows[0].accessory, "Working")
    compare(rows[0].action.argv, ["python3", "/x/herdr.py", "focus", "default", "pane", "pane-1"])
    compare(rows[1].subtitle, "1 tab · 2 panes · default")
    compare(rows[2].title, "Tab 1")            // Herdr labels an unnamed tab with its number
    compare(rows[2].accessory, "")
    compare(rows[3].title, "api")              // the pane with the agent is listed once, as the agent
    compare(rows[3].subtitle, "~/project/api · default")
    compare(rows[4].subtitle, "Attached")      // the title already names the session
    compare(rows[4].action.argv, ["python3", "/x/herdr.py", "focus", "default", "session", "-"])
    verify(rows[0].score > rows[1].score)
  }

  function test_root_lists_only_agents_and_workspaces() {
    var rows = Herdr.rows(Herdr.parse(sample), Herdr.request({ query: "proj", scope: "" }, "herdr"), "/x/herdr.py", "/home/me")
    compare(rows.length, 2)
    compare(rows[0].score, undefined)
  }

  function test_settings_hide_tabs_and_panes() {
    var req = Herdr.request({ query: "%", command: { rest: "" }, scope: "", settings: { panes: false, tabs: false } }, "herdr")
    compare(Herdr.rows(Herdr.parse(sample), req, "/x/herdr.py", "").length, 3)
  }

  function test_status_rows() {
    var req = Herdr.request(cmd(""), "herdr")
    var rows = Herdr.rows({ sessions: [], error: "" }, req, "/x", "")
    compare(rows[0].title, "No Herdr session is running")
    rows = Herdr.rows(Herdr.parse(JSON.stringify({ sessions: [{ name: "work", error: "boom" }] })), req, "/x", "")
    compare(rows[0].title, "Herdr session work did not answer")
    verify(rows[0].disabled)
  }
}
