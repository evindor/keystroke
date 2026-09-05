import QtQuick
import "../core/Match.js" as Match
import "../core/Calculator.js" as Calc

Item {
  id: root
  property var host: null
  readonly property var provider: ({
    apiVersion: 1,
    id: "calculator",
    name: "Calculator",
    icon: "󰃬",
    color: "#b1a2e8",
    description: "Private, instant arithmetic",
    settings: [{ key: "precision", type: "number", label: "Significant digits", "default": 12, min: 2, max: 15, integer: true }],
    query: function(ctx) { return root.query(ctx) }
  })

  function navRow(score) {
    return { id: "calc", title: "Calculator", subtitle: "Try 128 * 1.24 or 15% of 80", icon: "󰃬", section: "Calculator",
             verb: "Open", tier: "item", score: score, order: 3, action: { type: "navigate", scope: "calculator", title: "Calculator" } }
  }

  function query(ctx) {
    if (ctx.scope && ctx.scope !== "calculator") return []
    if (!ctx.query) return ctx.scope ? [] : [navRow(24)]
    var rows = []
    if (!ctx.scope) {
      var s = Match.match(ctx.query, "Calculator", "arithmetic math")
      if (s) rows.push(navRow(s))
    }
    var result = Calc.evaluate(ctx.query)
    if (!result) return rows
    if (result.partial !== undefined) {
      rows.unshift({ id: "result", title: result.partial + " …", subtitle: "Continue your calculation", icon: "󰃬", section: "Calculator",
                     verb: "Keep typing", tier: "answer", score: 200, disabled: true, action: { type: "noop" },
                     preview: result.partial + " …", previewLabel: "CALCULATOR", previewDetail: "Add the next number" })
      return rows
    }
    var text = Calc.format(result.value, ctx.settings.precision)
    rows.unshift({ id: "result", title: text, subtitle: ctx.query.trim() + " =", icon: "󰃬", section: "Calculator", verb: "Copy result",
                   tier: "answer", score: 200, action: { type: "copy", text: text }, preview: text, previewLabel: "RESULT",
                   previewDetail: ctx.query.trim() })
    return rows
  }
}
