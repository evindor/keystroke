pragma ComponentBehavior: Bound
import QtQuick
import Quickshell

QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  readonly property string key: extension ? extension.id : "keystroke-itt"
  property var settings: ({})

  readonly property Component view: Component {
    Editor { settings: root.settings; omarchyPath: root.omarchyPath }
  }

  readonly property var provider: ({
    apiVersion: 1,
    name: "keystroke-ITT",
    icon: "󰏫",
    color: "#8bceb4",
    description: "Improve This Text with OpenAI, Grok, or the Omarchy default agent",
    settings: [
      { key: "provider", type: "enum", label: "AI provider", "default": "openai",
        options: ["openai", "grok", "omarchy"],
        optionLabels: { openai: "OpenAI", grok: "Grok", omarchy: "Omarchy default agent" } },
      { key: "openaiModel", type: "string", label: "OpenAI model", "default": "gpt-4.1-mini" },
      { key: "grokModel", type: "string", label: "Grok model", "default": "grok-4" },
      { key: "openaiKeyFile", type: "string", label: "OpenAI API key file", "default": "",
        description: "Path to a file containing the key. Leave blank to use OPENAI_API_KEY." },
      { key: "grokKeyFile", type: "string", label: "Grok API key file", "default": "",
        description: "Path to a file containing the key. Leave blank to use XAI_API_KEY." }
    ],
    view: root.view,
    query: function(ctx) {
      if (!ctx.command && ctx.scope !== root.key && ctx.query.trim().toLowerCase() !== "itt")
        return []
      return [{ id: "improve", title: "Improve This Text", subtitle: "Open the editor",
        verb: "Open", score: 100, action: { type: "provider-view", provider: root.key } }]
    },
    activate: function(row, ctx) {
      root.settings = ctx.settings
      return row.action
    }
  })
}
