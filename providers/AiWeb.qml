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
        description: "Absolute folder for agent --workspace; also sent to the desktop deeplink" }
    ],
    query: function(ctx) { return root.query(ctx) }
  })

  // `agent` is a generic name; it only counts when it resolves inside a Cursor
  // install (the installer links ~/.local/bin/agent to .../cursor-agent/...).
  Process {
    id: detect
    command: ["bash", "-lc", "for c in claude-desktop chatgpt claude codex cursor; do command -v \"$c\" >/dev/null 2>&1 && echo \"$c\"; done; a=$(command -v agent 2>/dev/null) && case \"$(readlink -f \"$a\")\" in *cursor*) echo agent;; esac"]
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
    return AiTargets.rows(ctx.settings, root.available, q)
  }
}
