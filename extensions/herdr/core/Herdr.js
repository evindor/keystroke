.pragma library

var ICON = "󱚣"
var GROUPS = [
  { kind: "agent", section: "Herdr agents", icon: "󱚣" },
  { kind: "workspace", section: "Herdr workspaces", icon: "" },
  { kind: "tab", section: "Herdr tabs", icon: "" },
  { kind: "pane", section: "Herdr panes", icon: "" },
  { kind: "session", section: "Herdr sessions", icon: "" }
]
var SETTINGS = [
  { key: "root", type: "boolean", label: "Show agents and workspaces in the main search", "default": true,
    description: "Off: Herdr appears only after the % command or on this extension's screen" },
  { key: "panes", type: "boolean", label: "List panes", "default": true,
    description: "Panes running an agent are always listed once, as the agent" },
  { key: "tabs", type: "boolean", label: "List tabs", "default": true }
]

function group(kind) {
  for (var i = 0; i < GROUPS.length; i++) if (GROUPS[i].kind === kind) return GROUPS[i]
  return GROUPS[0]
}

function request(ctx, id) {
  var explicit = !!ctx.command || ctx.scope === id
  var text = String(ctx.command ? ctx.command.rest : ctx.query || "").trim()
  var settings = ctx.settings || {}
  var allowed = explicit || (!ctx.scope && settings.root !== false && text.length >= 2)
  return { explicit: explicit, text: text, allowed: allowed, panes: settings.panes !== false, tabs: settings.tabs !== false }
}

function argv(helper, args) { return ["python3", helper].concat(args) }

function nativeId(value) { return typeof value === "string" && value.trim() !== "" && !/[\u0000\r\n]/.test(value) }

function list(value, key) {
  var out = [], rows = value && Array.isArray(value) ? value : []
  for (var i = 0; i < rows.length; i++) if (rows[i] && nativeId(rows[i][key])) out.push(rows[i])
  return out
}

function title(s) { s = String(s || ""); return s ? s.charAt(0).toUpperCase() + s.slice(1) : "" }

function tilde(path, home) {
  path = String(path || "")
  if (home && (path === home || path.indexOf(home + "/") === 0)) return "~" + path.slice(home.length)
  return path
}

function basename(path) { var parts = String(path || "").split("/"); return parts[parts.length - 1] || "" }

function count(n, word) { n = n || 0; return n + " " + word + (n === 1 ? "" : "s") }

// Herdr labels a tab with its number until it is renamed: "Tab 2", not a bare "2".
function tabLabel(tab) {
  var label = String(tab.label || ""), number = String(tab.number || "")
  return label && label !== number ? label : "Tab " + number
}

function status(value) {
  var s = String(value || "")
  return s && s !== "unknown" ? title(s) : ""
}

// Drops anything without a usable native id, so rows() only builds focus argv from safe values.
function parse(text) {
  var value
  try { value = JSON.parse(text) } catch (_) { return { sessions: [], error: "Could not read Herdr's state" } }
  if (!value || !Array.isArray(value.sessions)) return { sessions: [], error: "Could not read Herdr's state" }
  var sessions = []
  for (var i = 0; i < value.sessions.length; i++) {
    var s = value.sessions[i]
    if (!s || !nativeId(s.name)) continue
    if (typeof s.error === "string") { sessions.push({ name: s.name, error: s.error, attached: false, workspaces: [], tabs: [], panes: [], agents: [] }); continue }
    var snap = s.snapshot || {}
    sessions.push({ name: s.name, attached: Array.isArray(s.windows) && s.windows.length > 0, error: "",
      focusedPane: String(snap.focused_pane_id || ""), focusedTab: String(snap.focused_tab_id || ""), focusedWorkspace: String(snap.focused_workspace_id || ""),
      workspaces: list(snap.workspaces, "workspace_id"), tabs: list(snap.tabs, "tab_id"),
      panes: list(snap.panes, "pane_id"), agents: list(snap.agents, "pane_id") })
  }
  return { sessions: sessions, error: typeof value.error === "string" ? value.error : "" }
}

function statusRow(text, subtitle) {
  return { id: "status", title: text, subtitle: subtitle || "", icon: ICON, section: "Herdr",
    tier: "item", score: 1, disabled: true, action: { type: "noop" } }
}

// Every row focuses its target through the helper, which then raises the terminal showing it.
function rows(data, req, helper, home) {
  var items = []
  var multi = data.sessions.length > 1
  function add(kind, session, target, text, subtitle, accessory) {
    var g = group(kind)
    var where = multi && kind !== "session" ? session.name : ""
    items.push({ id: "herdr:" + session.name + ":" + kind + ":" + target, title: text,
      subtitle: [subtitle, where].filter(function(s) { return !!s }).join(" · "),
      icon: g.icon, section: g.section, accessory: accessory || "", tier: "item",
      keywords: kind, verb: "Go to", remember: true, rank: GROUPS.indexOf(g),
      action: { type: "exec", argv: argv(helper, ["focus", session.name, kind === "agent" ? "pane" : kind, target]) } })
  }
  for (var i = 0; i < data.sessions.length; i++) {
    var s = data.sessions[i]
    if (s.error) continue
    var withAgent = {}, wsLabel = {}
    for (var w = 0; w < s.workspaces.length; w++) wsLabel[s.workspaces[w].workspace_id] = String(s.workspaces[w].label || "Workspace " + (s.workspaces[w].number || ""))
    for (var a = 0; a < s.agents.length; a++) {
      var ag = s.agents[a]
      withAgent[ag.pane_id] = true
      var name = title(ag.agent || "agent")
      var cwd = tilde(ag.foreground_cwd || ag.cwd, home)
      add("agent", s, ag.pane_id, String(ag.terminal_title_stripped || ag.terminal_title || name), [name, cwd].filter(function(x) { return !!x }).join(" · "), status(ag.agent_status))
    }
    for (w = 0; w < s.workspaces.length; w++) {
      var ws = s.workspaces[w]
      add("workspace", s, ws.workspace_id, wsLabel[ws.workspace_id], count(ws.tab_count, "tab") + " · " + count(ws.pane_count, "pane"), status(ws.agent_status))
    }
    if (req.explicit && req.tabs) for (var t = 0; t < s.tabs.length; t++) {
      var tab = s.tabs[t]
      add("tab", s, tab.tab_id, tabLabel(tab), wsLabel[tab.workspace_id] || "", status(tab.agent_status))
    }
    if (req.explicit && req.panes) for (var p = 0; p < s.panes.length; p++) {
      var pane = s.panes[p]
      if (withAgent[pane.pane_id]) continue
      var pcwd = tilde(pane.foreground_cwd || pane.cwd, home)
      add("pane", s, pane.pane_id, String(pane.terminal_title_stripped || pane.terminal_title || basename(pcwd) || pane.pane_id), pcwd, "")
    }
    if (req.explicit) add("session", s, "-", s.name, s.attached ? "Attached" : "Detached, opens a terminal", "")
  }
  // Grouped like Everything: agents, workspaces, tabs, panes, sessions. An empty query keeps that order; a typed one is left to the matcher.
  items.sort(function(x, y) { return x.rank - y.rank })
  for (var k = 0; k < items.length; k++) {
    items[k].order = k
    if (!req.text) items[k].score = 1000 - k
    delete items[k].rank
  }
  if (req.explicit && !items.length) {
    var broken = data.sessions.filter(function(x) { return !!x.error })
    if (data.error) items.push(statusRow(data.error))
    else if (broken.length) items.push(statusRow("Herdr session " + broken[0].name + " did not answer", broken[0].error))
    else items.push(statusRow("No Herdr session is running", "Start one with herdr"))
  }
  return items
}
