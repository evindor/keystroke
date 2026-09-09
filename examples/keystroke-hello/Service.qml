import QtQuick

// A Keystroke provider is an Omarchy `service` plugin whose root object
// exposes `provider`. Omarchy loads this object into omarchy-shell, injects
// `shell`/`manifest`, and destroys it when the plugin is disabled or removed.
// Keystroke discovers it through shell.serviceFor(<plugin id>).
QtObject {
  id: root
  property var shell: null
  property var manifest: null

  readonly property var provider: ({
    apiVersion: 1,
    name: "Hello",
    icon: "✳",
    description: "Says hello from a separately installed plugin",
    prefix: "hello",
    // Optional: shapes of text this provider answers. A match lifts the rows
    // it returns by `boost` and arrives as ctx.patterns.matched.
    patterns: [
      { id: "greeting", regex: "^\\s*(hello|hi|hey)\\b", flags: "i", boost: 20, example: "hello Omarchy" }
    ],
    settings: [
      { key: "greeting", type: "string", label: "Greeting", "default": "Hello" }
    ],
    // ctx: { query, scope, sub, settings, patterns, pending(), host, shell, appLibrary, omarchyPath }
    query: function(ctx) {
      if (ctx.scope) return []
      var q = ctx.query.trim()
      var matched = ctx.patterns && ctx.patterns.matched.length > 0   // absent on hosts older than September 2026
      if (!matched && q.toLowerCase().indexOf("hello") !== 0) return []
      var name = q.replace(/^\s*(hello|hi|hey)\b/i, "").trim() || "Omarchy"
      var text = (ctx.settings.greeting || "Hello") + ", " + name + "!"
      return [{
        id: "hello", title: text, subtitle: "Copy this greeting", icon: "✳", tier: "item", score: 100,
        verb: "Copy", action: { type: "copy", text: text }, preview: text, previewLabel: "HELLO"
      }]
    }
  })
}
