import QtQuick
import Quickshell
import Quickshell.Io

// Fallbacks for queries nothing else answers. Typing never contacts a
// provider; every hand-off is an explicit activation. Targets are detected at
// query time and modes whose target is missing fall back to the browser.
Item {
  id: root
  property var host: null
  property var cliAvailable: ({})

  readonly property var provider: ({
    apiVersion: 1,
    id: "ai",
    name: "AI & Web Search",
    icon: "✳",
    color: "#e79c85",
    description: "Continue any query with Google, ChatGPT or Claude",
    settings: [
      { key: "provider", type: "enum", label: "Preferred AI provider", "default": "chatgpt", options: ["chatgpt", "claude"] },
      { key: "mode", type: "enum", label: "Open conversations in", "default": "desktop", options: ["desktop", "cli", "browser"],
        description: "Falls back to the browser when the app or CLI is not installed" }
    ],
    query: function(ctx) { return root.query(ctx) }
  })

  Process {
    command: ["bash", "-lc", "for c in claude codex; do command -v \"$c\" >/dev/null 2>&1 && echo \"$c\"; done"]
    running: true
    stdout: StdioCollector {
      onStreamFinished: {
        var found = ({})
        var lines = text.split("\n")
        for (var i = 0; i < lines.length; i++) if (lines[i].trim()) found[lines[i].trim()] = true
        root.cliAvailable = found
      }
    }
  }

  function desktopEntry(needle) {
    var values = DesktopEntries.applications.values || []
    for (var i = 0; i < values.length; i++) {
      var e = values[i]
      var id = String(e.id || "").toLowerCase(), name = String(e.name || "").toLowerCase()
      if (e.noDisplay) continue
      if (id.indexOf(needle) >= 0 || name.indexOf(needle) >= 0) return e
    }
    return null
  }

  function actionFor(providerId, name, mode, q) {
    var cli = providerId === "chatgpt" ? "codex" : "claude"
    var url = providerId === "chatgpt" ? "https://chatgpt.com/" : "https://claude.ai/new"
    var notify = { type: "notify", glyph: "󰅍", headline: "Prompt copied", body: "Paste it into a new chat in " + name + "." }
    if (mode === "cli" && root.cliAvailable[cli])
      return { effect: { type: "exec", argv: ["omarchy-launch-terminal", cli, q] }, subtitle: "New " + cli + " session · prompt passed as an argument" }
    if (mode === "desktop") {
      var entry = root.desktopEntry(providerId)
      if (entry) return { effect: { type: "compound", actions: [{ type: "copy", text: q }, { type: "app", id: String(entry.id), name: String(entry.name) }, notify] },
                          subtitle: "Desktop app · prompt copied, paste to start" }
    }
    var reason = mode === "browser" ? "Browser" : (mode === "cli" ? cli + " CLI not found · browser" : "Desktop app not found · browser")
    return { effect: { type: "compound", actions: [{ type: "copy", text: q }, { type: "url", url: url }, notify] }, subtitle: reason + " · prompt copied, paste to start" }
  }

  function query(ctx) {
    if (ctx.scope || !ctx.query.trim()) return []
    var q = ctx.query.trim()
    var rows = [{ id: "google", title: "Search Google", subtitle: q, icon: "󰊭", section: "Continue with", verb: "Search", tier: "fallback", score: 2,
                  action: { type: "url", url: "https://www.google.com/search?q=" + encodeURIComponent(q).replace(/%20/g, "+") } }]
    var providers = [["chatgpt", "ChatGPT", "󰭹"], ["claude", "Claude", "󰛄"]]
    for (var i = 0; i < providers.length; i++) {
      var p = providers[i]
      var a = root.actionFor(p[0], p[1], ctx.settings.mode, q)
      rows.push({ id: p[0], title: "Start a new chat in " + p[1], subtitle: a.subtitle, icon: p[2], section: "Continue with", verb: "Open " + p[1],
                  tier: "fallback", score: p[0] === ctx.settings.provider ? 3 : 2, action: a.effect })
    }
    return rows
  }
}
