.pragma library

// One replacement pass: a value containing %2 must never become a placeholder.
function format(pattern, args) {
  var values = Array.isArray(args) ? args : []
  return String(pattern).replace(/%([1-9][0-9]*)/g, function(token, index) {
    var at = Number(index) - 1
    return at < values.length ? String(values[at]) : token
  })
}

// Settings are owned UI. Keep their action payloads, persisted values and ids
// unchanged, and retain the English path as search terms.
function settings(tree, translate, formatNumber) {
  var nodes = []
  for (var i = 0; i < tree.nodes.length; i++) {
    var original = tree.nodes[i], next = {}
    for (var key in original) next[key] = original[key]
    var literalName = (tree.literalNames || {})[original.id.split("/")[0]]
    next.parts = original.parts.map(function(part, index) { return index === 1 && literalName === part ? part : translate(part) })
    next.path = next.parts.join(" › ")
    next.title = next.parts[next.parts.length - 1]
    next.relative = ({})
    next.keywords = (original.keywords || "") + " " + original.path
    var fields = ["subtitle", "section", "verb", "description", "confirm", "confirmDetail", "confirmText", "cancelText"]
    for (var f = 0; f < fields.length; f++) next[fields[f]] = translate(original[fields[f]] || "")
    if (original.localizeAccessory) {
      next.accessory = translate(original.accessory)
      if (next.accessory === original.accessory && typeof original.accessory === "string") {
        var title = original.accessory.charAt(0).toUpperCase() + original.accessory.slice(1)
        if (translate(title) !== title) next.accessory = translate(title)
      }
    }
    if (original.accessoryNumber !== undefined && typeof formatNumber === "function") next.accessory = formatNumber(original.accessoryNumber)

    nodes.push(next)
  }
  return { nodes: nodes, screens: tree.screens, literalNames: tree.literalNames || ({}) }
}

function text(host, key, args) {
  return host && typeof host.t === "function" ? host.t(key, args) : format(key, args || [])
}

function extensionConsent(entry, translate) {
  return {
    message: translate("Turn on %1?", [entry.name]),
    detail: entry.local
      ? translate("This is a local folder in %1 that nobody has reviewed. It will run inside your shell with your permissions. Run it at your own risk, and check its code first.", [entry.dir])
      : translate("This extension was automatically checked and reviewed before it shipped with Keystroke, and it runs inside your shell with your permissions. Nonetheless, run it at your own risk. It's recommended to check the extension code first.")
  }
}
