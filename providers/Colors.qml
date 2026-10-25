import QtQuick
import "../core/Locale.js" as Locale
import "../core/Match.js" as Match
import "../core/Colors.js" as Colors

Item {
  id: root
  property var host: null
  function t(key, args) { return Locale.text(root.host, key, args) }
  readonly property var provider: ({
    apiVersion: 1,
    id: "colors",
    name: "Colors",
    icon: "󰃉",
    color: "#e69ba9",
    description: "Screen eyedropper, HEX, RGB and HSL",
    settings: [{ key: "format", type: "enum", label: "Eyedropper format", "default": "hex", options: ["hex", "rgb"] }],
    query: function(ctx) { return root.query(ctx) }
  })

  function query(ctx) {
    if (ctx.scope) return []
    var rows = []
    var s = ctx.query ? Match.match(ctx.query, root.t("Pick a Color"), "Pick a Color color picker eyedropper screen hex") : 21
    if (s) rows.push({ id: "picker", title: root.t("Pick a Color"), subtitle: root.t("Sample any pixel on your screen"), icon: "󰃉", section: "Colors",
                       verb: root.t("Pick color"), tier: "item", score: s, order: 6, action: { type: "exec", argv: ["hyprpicker", "-a", "-f", ctx.settings.format] } })
    var parsed = Colors.parse(ctx.query)
    if (!parsed) return rows
    for (var i = 0; i < parsed.values.length; i++) {
      var v = parsed.values[i]
      rows.push({ id: "color-" + i, title: v.text, subtitle: v.label, icon: "●", tint: parsed.swatch, section: "Colors", verb: root.t("Copy color"),
                  tier: "answer", score: 190 - i, action: { type: "copy", text: v.text }, preview: v.text, previewLabel: root.t("COLOR"), swatch: parsed.swatch })
    }
    return rows
  }
}
