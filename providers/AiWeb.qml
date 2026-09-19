import QtQuick
import Quickshell
import Quickshell.Io
import "../core/AiTargets.js" as AiTargets

// Fallbacks for queries nothing else answers. Typing never contacts a
// provider; every hand-off is an explicit activation that opens the target
// with the prompt already in its composer (see core/AiTargets.js for the
// verified links). Targets are detected once at load and re-checked when the
// desktop entries change; a missing app or CLI falls back to the browser.
Item {
  id: root
  property var host: null
  property var available: ({})

  readonly property var provider: ({
    apiVersion: 1,
    id: "ai",
    name: "AI & Web Search",
    icon: "✳",
    color: "#e79c85",
    description: "Continue any query in Claude, ChatGPT, Cursor or Google",
    settings: [
      { key: "provider", type: "enum", label: "Preferred assistant", "default": "chatgpt",
        options: ["chatgpt", "claude", "cursor"],
        optionLabels: { chatgpt: "ChatGPT / Codex", claude: "Claude", cursor: "Cursor" },
        description: "Listed first among the fallbacks" },
      { key: "mode", type: "enum", label: "Open conversations in", "default": "desktop", options: ["desktop", "cli", "browser"],
        description: "Controls Claude and Cursor; ChatGPT opens in the browser. Codex has its own provider settings." },
      { key: "autoSend", type: "boolean", label: "Send immediately in the browser", "default": false,
        description: "ChatGPT only. Claude, Cursor and the desktop apps always let you review the prompt first" },
      { key: "cursorWorkspace", type: "string", label: "Cursor workspace folder", "default": "",
        description: "Optional path or folder name for Cursor hand-offs (desktop deeplink and agent --workspace)" }
    ],
    query: function(ctx) { return root.query(ctx) }
  })

  Process {
    id: detect
    command: ["bash", "-lc", "for c in claude-desktop chatgpt claude codex cursor agent; do command -v \"$c\" >/dev/null 2>&1 && echo \"$c\"; done"]
    running: true
    stdout: StdioCollector {
      onStreamFinished: {
        var found = ({})
        var lines = text.split("\n")
        for (var i = 0; i < lines.length; i++) if (lines[i].trim()) found[lines[i].trim()] = true
        root.available = found
      }
    }
  }

  // Installing or removing one of the apps changes the desktop entries; that is
  // the moment to look again instead of forking bash on every open.
  Connections {
    target: DesktopEntries.applications
    function onValuesChanged() { if (!detect.running) detect.running = true }
  }

  function query(ctx) {
    if (ctx.scope || !ctx.query.trim()) return []
    var q = String(ctx.rawQuery === undefined ? ctx.query : ctx.rawQuery).trim()
    var rows = [{ id: "google", title: "Search Google", subtitle: q, icon: "󰊭", section: "Continue with", verb: "Search", tier: "fallback", score: 2,
                  action: { type: "url", url: AiTargets.googleUrl(q) } }]
    var preferred = ctx.settings.provider || "chatgpt"
    var order = preferred === "cursor" ? ["cursor"] : (preferred === "claude" ? ["claude", "chatgpt"] : ["chatgpt", "claude"])
    for (var i = 0; i < order.length; i++) {
      if (order[i] === "cursor") {
        var c = AiTargets.cursorPlan(ctx.settings.mode, root.available, q, ctx.settings.cursorWorkspace)
        if (!c) continue
        rows.push({ id: c.id, title: c.title, subtitle: c.subtitle, icon: "󰨞", section: "Continue with",
                    verb: c.verb, tier: "fallback", score: 3, action: c.effect,
                    preview: q, previewLabel: "PROMPT", previewDetail: "Opens with this prompt in the composer" })
        continue
      }
      var p = AiTargets.plan(order[i], order[i] === "chatgpt" ? "browser" : ctx.settings.mode, ctx.settings.autoSend === true, root.available, q)
      rows.push({ id: p.id, title: p.title, subtitle: p.subtitle, icon: order[i] === "claude" ? "󰛄" : "󰭹", section: "Continue with",
                  verb: p.verb, tier: "fallback", score: i === 0 ? 3 : 2, action: p.effect,
                  preview: q, previewLabel: "PROMPT", previewDetail: "Opens with this prompt in the composer" })
    }
    if (preferred !== "cursor") {
      var extra = AiTargets.cursorPlan(ctx.settings.mode, root.available, q, ctx.settings.cursorWorkspace)
      if (extra)
        rows.push({ id: extra.id, title: extra.title, subtitle: extra.subtitle, icon: "󰨞", section: "Continue with",
                    verb: extra.verb, tier: "fallback", score: 2.5, action: extra.effect,
                    preview: q, previewLabel: "PROMPT", previewDetail: "Opens with this prompt in the composer" })
    }
    return rows
  }
}
