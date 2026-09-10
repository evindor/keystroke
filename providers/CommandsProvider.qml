import QtQuick
import "../core/Commands.js" as Commands

// What can I type? The "/" screen: every command the enabled providers
// declare (core/Commands.js), each with its usage line and what its
// arguments mean; Enter types the prefix into the search field. "/" itself
// is declared here as a sigil command, so "/tr" filters the list, and the
// same rows answer the "commands" scope. For any other root query the
// provider offers up to three command rows whose name matches ("trans" →
// Translate), so a user who knows the name finds the prefix with Tab.
Item {
  id: root
  property var host: null

  readonly property var provider: ({
    apiVersion: 1,
    id: "commands",
    name: "Commands",
    icon: "󰘳",
    color: "#a5a4ad",
    description: "Every prefix you can type, with its arguments",
    commands: [
      { id: "help", prefix: Commands.HELP_PREFIX, title: "What can I type?", summary: "Lists every command with its arguments",
        args: [{ name: "command", hint: "part of a name or prefix, to filter the list", optional: true, rest: true }], examples: ["/", "/tr"] }
    ],
    settings: [],
    query: function(ctx) { return root.query(ctx) }
  })

  function navRow(score) {
    return { id: "help", title: "What can I type?", subtitle: "Every command and its arguments · or type /", icon: "󰘳", section: "Keystroke",
             verb: "Open", tier: "item", score: score, order: 99, keywords: "help commands prefixes usage",
             description: "help commands prefixes what can I type usage arguments", action: { type: "navigate", scope: "commands", title: "Commands" } }
  }

  function query(ctx) {
    var h = root.host
    if (!h) return []
    if (ctx.scope) return ctx.scope === "commands" ? Commands.helpRows(h.commandItems(), ctx.query) : []
    if (ctx.command) return Commands.helpRows(h.commandItems(), ctx.command.rest)
    if (!ctx.query) return [navRow(1)]
    return Commands.suggestRows(h.commandItems(), ctx.query, 3)
  }
}
