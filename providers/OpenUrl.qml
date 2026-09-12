import QtQuick
import "../core/Url.js" as Url

Item {
  id: root
  property var host: null
  readonly property var provider: ({
    apiVersion: 1,
    id: "open-url",
    name: "Open URL",
    icon: "󰖟",
    color: "#8bceb4",
    description: "Open a web address in your default browser",
    commands: [{
      id: "open", prefix: "$", title: "Open URL", summary: "Open a web address in your default browser",
      args: [{ name: "url", hint: "a web address, with or without https://", rest: true }],
      examples: ["$example.com", "$http://localhost:3000"]
    }],
    settings: [],
    query: function(ctx) { return root.query(ctx) }
  })

  function query(ctx) {
    if (ctx.scope && ctx.scope !== "open-url") return []
    var explicit = !!ctx.command || ctx.scope === "open-url"
    var text = ctx.command ? ctx.command.rest : ctx.query
    var parsed = Url.parse(text, explicit)
    if (!parsed) {
      if (!explicit) return []
      return [{ id: "hint", title: String(text || "").trim() ? "Enter a valid web address" : "Enter a URL",
                subtitle: "For example: example.com or http://localhost:3000", icon: "󰖟", section: "Open URL",
                tier: "answer", score: 250, disabled: true, verb: "Keep typing", action: { type: "noop" } }]
    }
    return [{ id: "open", title: "Open " + parsed.url, subtitle: "Open URL · Default browser", icon: "󰖟", section: "Open URL",
              tier: "answer", score: 250, verb: "Open URL", hint: "↵ opens in default browser",
              preview: parsed.url, previewLabel: "URL", previewDetail: "Open in your default browser",
              action: { type: "url", url: parsed.url } }]
  }
}
