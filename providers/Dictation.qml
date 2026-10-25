import QtQuick
import "../core/Locale.js" as Locale
import "../core/Match.js" as Match

Item {
  id: root
  property var host: null
  function t(key, args) { return Locale.text(root.host, key, args) }
  readonly property var provider: ({
    apiVersion: 1,
    id: "dictation",
    name: "Dictate to Clipboard",
    icon: "󰍬",
    description: "Speak, copy, or paste into your previous window",
    settings: [],
    query: function(ctx) {
      if (ctx.scope && ctx.scope !== "dictation") return []
      if (!ctx.scope) {
        var score = ctx.query ? Match.match(ctx.query, root.t("Dictate to Clipboard"), "Dictate to Clipboard dictation speech voice transcribe paste microphone") : 23
        var rows = score ? [{ id: "open", title: root.t("Dictate to Clipboard"), subtitle: root.t("Speak · Enter copies · Ctrl+Enter pastes"), icon: "󰍬",
          score: score, order: 5, verb: root.t("Dictate"), remember: true, action: { type: "dictate" } }] : []
        // Search may normalize a spoken command; copy the original prose.
        var raw = String(ctx.rawQuery === undefined ? ctx.query || "" : ctx.rawQuery)
        if (raw.trim()) rows.push({ id: "copy-query", title: root.t("Copy to Clipboard"), subtitle: root.t("Enter copies · Ctrl+Enter copies and pastes"), icon: "󰅌",
          section: "Continue with", tier: "fallback", score: 1, verb: root.t("Copy"), preview: raw, previewLabel: root.t("DICTATION"),
          previewDetail: "Original text · Ctrl+Enter pastes into your previous window",
          action: { type: "dictation-copy", text: raw }, altAction: { type: "dictation-copy", text: raw, paste: true } })
        return rows
      }
      var text = String(ctx.query || "")
      return [{ id: "transcript", title: text ? "Copy dictated text" : "Start speaking…", subtitle: root.t("Enter copies and closes · Ctrl+Enter pastes into your previous window"),
        icon: "󰍬", score: 100, verb: root.t("Copy"), disabled: !text.trim(),
        preview: text, previewLabel: root.t("DICTATION"), previewDetail: "Full transcript · earlier words can change as you speak",
        action: { type: "dictation-copy", text: text }, altAction: { type: "dictation-copy", text: text, paste: true } }]
    }
  })
}
