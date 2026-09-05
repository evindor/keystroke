import QtQuick
import "../core/Match.js" as Match
import "../core/Settings.js" as Settings

// Schema-generated settings screens for the palette and every provider.
// Scopes: settings | settings/palette | settings/<key> | settings/<key>/<setting>
Item {
  id: root
  property var host: null

  readonly property var provider: ({
    apiVersion: 1,
    id: "settings",
    name: "Keystroke Settings",
    icon: "󰒓",
    color: "#a5a4ad",
    description: "Providers, appearance and the config file",
    settings: [],
    query: function(ctx) { return root.query(ctx) }
  })

  function settingAction(path, key, value, schema) {
    return { type: "setting", path: path, key: key, value: value, schema: schema }
  }

  function schemaRows(ctx, path, schemas, values, scopePrefix, key) {
    var rows = []
    for (var i = 0; i < schemas.length; i++) {
      var schema = schemas[i]
      var k = schema.key
      var value = values[k]
      if (key) {
        if (k !== key) continue
        if (schema.type === "enum") {
          for (var o = 0; o < schema.options.length; o++) {
            var option = schema.options[o]
            rows.push({ id: String(option), title: String(option).charAt(0).toUpperCase() + String(option).slice(1),
                        subtitle: option === value ? "Selected" : "", icon: option === value ? "✓" : "○", section: schema.label,
                        verb: "Select", tier: "item", score: Match.match(ctx.query, String(option)), order: o,
                        action: root.settingAction(path, k, option, schema) })
          }
        } else if (schema.type === "string" || schema.type === "number") {
          var typed = schema.type === "number" ? Number(ctx.query) : ctx.query
          var ok = ctx.query.length > 0
          try { Settings.validate(schema, typed) } catch (e) { ok = false }
          rows.push({ id: "current", title: value === "" || value === undefined ? "Not set" : String(value), subtitle: "Current value · type a new one",
                      icon: "󰒓", section: schema.label, verb: "", tier: "item", score: 1, order: 0, disabled: true, action: { type: "noop" } })
          if (ok) rows.push({ id: "save", title: "Save “" + String(typed) + "”", subtitle: schema.description || "", icon: "✓", section: schema.label,
                              verb: "Save", tier: "item", score: 100, order: 1, action: root.settingAction(path, k, typed, schema) })
        }
        continue
      }
      var s = Match.match(ctx.query, schema.label, schema.description || "")
      if (!s) continue
      var isBool = schema.type === "boolean"
      rows.push({ id: k, title: schema.label, subtitle: schema.description || "", icon: "󰒓", section: "Settings", verb: isBool ? "Toggle" : "Change",
                  tier: "item", score: s, order: i, accessory: isBool ? (value ? "On" : "Off") : (value === "" || value === undefined ? "—" : String(value)),
                  action: isBool ? root.settingAction(path, k, !value, schema) : { type: "navigate", scope: scopePrefix + "/" + k, title: schema.label } })
    }
    return rows
  }

  function query(ctx) {
    if (!ctx.scope) {
      var s0 = ctx.query ? Match.match(ctx.query, "Keystroke Settings", "preferences providers extensions configuration appearance") : 20
      return s0 ? [{ id: "settings", title: "Keystroke Settings", subtitle: "Providers, appearance and the config file", icon: "󰒓", section: "Settings",
                     verb: "Open", tier: "item", score: s0, order: 7, action: { type: "navigate", scope: "settings", title: "Settings" } }] : []
    }
    if (ctx.scope.split("/")[0] !== "settings" || !root.host) return []
    var parts = ctx.sub ? ctx.sub.split("/") : []
    var rows = [], s
    if (!parts.length) {
      s = Match.match(ctx.query, "Appearance", "layout density accent preview theme")
      if (s) rows.push({ id: "palette", title: "Appearance", subtitle: "Density, accent and previews", icon: "󰏘", section: "Keystroke", verb: "Open",
                         tier: "item", score: s + 1, order: 0, action: { type: "navigate", scope: "settings/palette", title: "Appearance" } })
      s = Match.match(ctx.query, "Open config file", "edit json")
      if (s) rows.push({ id: "config", title: "Open config file", subtitle: root.host.configPath, icon: "", section: "Keystroke", verb: "Open file",
                         tier: "item", score: s, order: 1, action: { type: "edit" } })
      var entries = root.host.registry.entries
      for (var i = 0; i < entries.length; i++) {
        var e = entries[i]
        if (e.key === "settings") continue
        s = Match.match(ctx.query, e.provider.name, e.provider.description || "")
        if (!s) continue
        var enabled = root.host.providerEnabled(e)
        var origin = e.source === "community" ? "Plugin " + e.pluginId : "Bundled"
        rows.push({ id: e.key, title: e.provider.name, subtitle: (enabled ? "Enabled" : "Disabled") + " · " + origin + (e.provider.description ? " · " + e.provider.description : ""),
                    icon: e.provider.icon || "⌘", iconFont: e.provider.iconFont || "", tint: e.provider.color || "", section: "Providers", verb: "Open",
                    tier: "item", score: s, order: 10 + i, badge: e.source === "community" ? "plugin" : "",
                    action: { type: "navigate", scope: "settings/" + e.key, title: e.provider.name } })
      }
      var problems = root.host.registry.problems
      for (var p = 0; p < problems.length; p++) {
        s = Match.match(ctx.query, problems[p].pluginId, "plugin problem")
        if (s) rows.push({ id: "problem-" + problems[p].pluginId, title: problems[p].pluginId, subtitle: problems[p].message, icon: "󰀦", section: "Plugins needing attention",
                           verb: "", tier: "item", score: s, order: 500 + p, disabled: true, badge: "plugin", action: { type: "noop" } })
      }
      return rows
    }
    var key = parts[0], setting = parts[1] || ""
    if (key === "palette")
      return root.schemaRows(ctx, ["palette"], root.host.paletteSchema, root.host.paletteValues(), "settings/palette", setting)
    var entry = root.host.registryEntry(key)
    if (!entry) return []
    var path = ["providers", key]
    var schemas = (entry.provider.settings || []).slice()
    var values = Settings.values(root.host.config, path, schemas)
    if (!setting) {
      var enabledSchema = { key: "enabled", type: "boolean", label: "Enable provider",
                            description: entry.source === "community" ? "Runs plugin code in your shell with your permissions" : "Include this provider in Keystroke" }
      var on = root.host.providerEnabled(entry)
      var es = Match.match(ctx.query, enabledSchema.label, enabledSchema.description)
      if (es) rows.push({ id: "enabled", title: enabledSchema.label, subtitle: enabledSchema.description, icon: "󰒓", section: "Settings", verb: "Toggle",
                          tier: "item", score: es + 1, order: -1, accessory: on ? "On" : "Off", action: root.settingAction(path, "enabled", !on, enabledSchema) })
      if (entry.source === "community" && !ctx.query)
        rows.push({ id: "provenance", title: "Provided by " + entry.pluginId, subtitle: "Community plugin · manage with omarchy plugin", icon: "󰏓",
                    section: "Settings", verb: "", tier: "item", score: 1, order: 900, disabled: true, badge: "plugin", action: { type: "noop" } })
    }
    return rows.concat(root.schemaRows(ctx, path, schemas, values, "settings/" + key, setting))
  }
}
