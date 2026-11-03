.pragma library

// Row building for the Raycast extension. The store download and the
// @raycast/api host live in host/; this file only decides what the palette
// shows. Tests import it directly.

var ICON = "󰏓"

function dataDir(home, xdg) {
  var base = xdg ? String(xdg) : String(home || "") + "/.local/share"
  return base.replace(/\/$/, "") + "/keystroke/raycast"
}

function extensionsDir(home, xdg) {
  return dataDir(home, xdg) + "/extensions"
}

function safeName(value) {
  var name = String(value || "")
  return /^[A-Za-z0-9._-]+$/.test(name) ? name : ""
}

function compatLabel(status) {
  if (status === "full") return "Works"
  if (status === "partial") return "Partial"
  if (status === "impossible") return "Unlikely"
  return ""
}

function contains(hay, needle) {
  if (!needle) return true
  return String(hay || "").toLowerCase().indexOf(String(needle).toLowerCase()) !== -1
}

function commandRows(installed, needle, scored) {
  var rows = []
  var list = installed || []
  for (var i = 0; i < list.length; i++) {
    var ext = list[i]
    var commands = ext.commands || []
    for (var c = 0; c < commands.length; c++) {
      var cmd = commands[c]
      var title = cmd.title || cmd.name
      var blob = title + " " + (cmd.name || "") + " " + (ext.title || "") + " " + (ext.name || "")
      if (scored && needle && !contains(blob, needle)) continue
      var row = {
        id: "cmd/" + ext.id + "/" + cmd.name,
        title: title,
        subtitle: ext.title || ext.name || "",
        icon: ICON,
        section: scored ? "Installed" : "",
        verb: cmd.mode === "no-view" ? "Run" : "Open",
        tier: "item",
        keywords: (ext.name || "") + " " + (cmd.name || "") + " raycast",
        description: cmd.description || cmd.subtitle || "",
        action: {
          type: "raycast-run",
          dir: ext.dir,
          command: cmd.name,
          mode: cmd.mode || "view",
          title: title
        }
      }
      if (scored) {
        row.score = 80
        row.order = i * 20 + c
      }
      rows.push(row)
    }
  }
  return rows
}

function findInstalled(installed, name) {
  var list = installed || []
  for (var i = 0; i < list.length; i++) if (list[i].name === name) return list[i]
  return null
}

function storeRows(store, installed) {
  var rows = []
  var list = store || []
  for (var i = 0; i < list.length; i++) {
    var ext = list[i]
    var handle = safeName(ext.handle)
    var name = safeName(ext.name)
    if (!handle || !name) continue
    var local = findInstalled(installed, name)
    var installedHere = !!(ext.installed || local)
    var label = installedHere ? "Installed" : compatLabel(ext.compat)
    var row = {
      id: "store/" + name,
      title: ext.title || name,
      subtitle: ext.description || name,
      icon: ICON,
      section: "Raycast store",
      verb: installedHere ? "Open" : "Install",
      tier: "item",
      order: i,
      score: 70,
      accessory: label,
      keywords: name + " " + handle + " raycast",
      description: ext.description || "",
      action: installedHere && local && local.commands && local.commands.length
        ? {
          type: "raycast-run",
          dir: local.dir,
          command: local.commands[0].name,
          mode: local.commands[0].mode || "view",
          title: local.commands[0].title || local.commands[0].name
        }
        : { type: "raycast-install", handle: handle, name: name }
    }
    if (!installedHere) {
      row.confirm = "Install " + (ext.title || name) + "?"
      row.confirmDetail = "Downloads the published Raycast bundle and runs it in this shell, with your permissions. Many extensions expect macOS, so some will not work."
      row.confirmText = "Install"
      row.cancelText = "Cancel"
    }
    rows.push(row)
  }
  return rows
}

function uninstallRows(installed) {
  var rows = []
  var list = installed || []
  for (var i = 0; i < list.length; i++) {
    var ext = list[i]
    rows.push({
      id: "remove/" + ext.id,
      title: "Uninstall " + (ext.title || ext.name),
      subtitle: "Remove the downloaded bundle",
      icon: ICON,
      section: "Installed",
      verb: "Uninstall",
      tier: "item",
      score: 5,
      order: 1000 + i,
      confirm: "Uninstall " + (ext.title || ext.name) + "?",
      confirmDetail: "Removes it from Keystroke. This does not change a Raycast install.",
      confirmText: "Uninstall",
      cancelText: "Keep",
      action: { type: "raycast-remove", id: ext.id }
    })
  }
  return rows
}

function blocker(nodeOk, runtime) {
  return {
    id: runtime ? "need-node" : "need-setup",
    title: nodeOk ? "Set up Raycast" : "Node.js 20 or newer is required",
    subtitle: nodeOk
      ? "Open Extensions, then Raycast, then Run setup"
      : "Install Node.js, then Run setup on the Raycast extension",
    icon: ICON,
    section: "Raycast",
    disabled: true,
    score: 100,
    tier: "item"
  }
}

// input: { scope, query, commandRest, inCommand, installed, store, searching, searchError, runtime, nodeOk }
function rows(input) {
  var src = input || {}
  var scope = String(src.scope || "")
  var scoped = scope === "raycast" || scope.indexOf("raycast/") === 0
  var prompted = scoped || !!src.inCommand
  var needle = scoped ? String(src.query || "").trim() : (src.inCommand ? String(src.commandRest || "").trim() : String(src.query || "").trim())
  if (!prompted && !needle) return []
  if (!src.ready) {
    if (!prompted) return []
    return [{
      id: "starting", title: "Starting Raycast", subtitle: "Checking Node", icon: ICON, section: "Raycast",
      disabled: true, score: 100, tier: "item"
    }]
  }
  if (!src.runtime || !src.nodeOk) {
    if (!prompted) return []
    return [blocker(!!src.nodeOk, !!src.runtime)]
  }
  var out = commandRows(src.installed, needle, prompted)
  if (!prompted) return out
  if (src.searchError) {
    out.push({
      id: "store-error",
      title: "Raycast store unavailable",
      subtitle: String(src.searchError),
      icon: ICON,
      section: "Raycast store",
      disabled: true,
      score: 60,
      tier: "item"
    })
  } else if (src.searching && !(src.store && src.store.length)) {
    out.push({
      id: "store-search",
      title: needle ? "Searching the Raycast store" : "Loading the Raycast store",
      subtitle: needle,
      icon: ICON,
      section: "Raycast store",
      disabled: true,
      score: 60,
      tier: "item"
    })
  } else if (needle && src.store && !src.store.length && !src.searching) {
    out.push({
      id: "store-empty",
      title: "No store extensions match",
      subtitle: needle,
      icon: ICON,
      section: "Raycast store",
      disabled: true,
      score: 60,
      tier: "item"
    })
  }
  var found = storeRows(src.store, src.installed)
  for (var i = 0; i < found.length; i++) out.push(found[i])
  if (scoped && !needle) {
    var removals = uninstallRows(src.installed)
    for (var r = 0; r < removals.length; r++) out.push(removals[r])
  }
  return out
}

function flatten(view) {
  var out = []
  if (!view || view.kind === "detail" || view.kind === "form") return out
  var sections = view.sections || []
  for (var s = 0; s < sections.length; s++) {
    var section = sections[s]
    var items = section.items || []
    if (section.title && items.length) out.push({ kind: "header", id: "header-" + s, title: section.title })
    for (var i = 0; i < items.length; i++) {
      var item = items[i]
      out.push({
        kind: "item",
        id: item.id,
        title: item.title || "",
        subtitle: item.subtitle || "",
        accessories: item.accessories || [],
        icon: item.icon || null,
        actions: item.actions || []
      })
    }
  }
  return out
}

function iconText(icon) {
  if (!icon || !icon.text) return ""
  return String(icon.text)
}

function iconSource(icon) {
  if (!icon) return ""
  if (icon.file) return String(icon.file)
  if (icon.url && String(icon.url).indexOf("https://") === 0) return String(icon.url)
  return ""
}
