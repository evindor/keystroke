.pragma library
.import "Match.js" as Match

// Commands: the typed triggers a provider declares, so the host can explain
// them instead of every provider hand-rolling a prefix. A declaration names
// the prefix, the action and the arguments in order:
//
//   commands: [{ id: "translate", prefix: "tr", title: "Translate",
//                summary: "Translate text into your target languages",
//                args: [{ name: "to", hint: "a language code or name", optional: true },
//                       { name: "text", hint: "what to translate", rest: true }],
//                examples: ["tr bonjour", "tr fr good morning"] }]
//
// Extensions put it in extension.json (visible before their code loads);
// bundled providers put it on the provider object. From it the host derives:
// routing (the prefix is recognised and stripped, the provider gets
// ctx.command = { id, prefix, rest }), the user's own prefix (the reserved
// `prefix` setting), the hint line under the search field, the ghost
// placeholders in the field, Tab completion from the command's name, the
// Usage section on the extension's screen and the "/" screen listing every
// command. A typed command is exclusive: only its owner answers. A prefix
// made of punctuation ("~", ":", "/") is a sigil and needs no space after it.

var MAX_COMMANDS = 8
var MAX_ARGS = 6
var MAX_EXAMPLES = 4
var MAX_PREFIX = 16
var HELP_PREFIX = "/"
var BOOST = 20

function safeString(v, limit) { return String(v === undefined || v === null ? "" : v).replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, limit || 200) }

// "~", ":", "/" and the like attach to the text; words need a space after them.
function isSigil(prefix) { return /^[^\w\s]{1,2}$/.test(String(prefix || "")) }

// A prefix a user may type: one word (letters, digits, dashes) or a sigil.
function cleanPrefix(value) {
  var p = safeString(value, MAX_PREFIX + 1)
  if (!p || p.length > MAX_PREFIX) return ""
  if (isSigil(p)) return p
  return /^[a-z0-9][a-z0-9-]*$/i.test(p) ? p.toLowerCase() : ""
}

// The prefix schema the host adds to a provider's settings when it declares
// commands, so the user can rename the trigger on the ordinary settings screen.
function prefixSchema(commands) {
  var first = commands && commands.length ? commands[0] : null
  return { key: "prefix", type: "string", label: "Prefix", "default": first ? first.prefix : "",
           description: "The word or sign that triggers it" + (first ? "; " + first.prefix + " unless you change it" : "") }
}

// -> { commands: [{ id, prefix, sigil, title, summary, args: [{ name, hint, optional, rest }], examples }], errors: [] }
function compile(list) {
  var out = [], errors = []
  if (list === undefined || list === null) return { commands: out, errors: errors }
  if (!Array.isArray(list)) return { commands: out, errors: ["commands must be an array"] }
  for (var i = 0; i < list.length && out.length < MAX_COMMANDS; i++) {
    var c = list[i]
    if (!c || typeof c !== "object") { errors.push("command " + i + " is not an object"); continue }
    var prefix = cleanPrefix(c.prefix)
    var id = safeString(c.id, 40) || prefix || "command-" + i
    if (!prefix) { errors.push(id + ": prefix must be one word or a sign, at most " + MAX_PREFIX + " characters"); continue }
    var title = safeString(c.title, 60)
    if (!title) { errors.push(id + ": title is missing"); continue }
    var args = [], bad = ""
    var declared = Array.isArray(c.args) ? c.args : []
    for (var a = 0; a < declared.length && a < MAX_ARGS; a++) {
      var arg = declared[a]
      var name = arg && typeof arg === "object" ? safeString(arg.name, 24).replace(/\s+/g, "-") : ""
      if (!name) { bad = "argument " + a + " needs a name"; break }
      if (args.length && args[args.length - 1].rest) { bad = "only the last argument may take the rest of the line"; break }
      args.push({ name: name, hint: safeString(arg.hint, 160), optional: arg.optional === true, rest: arg.rest === true })
    }
    if (bad) { errors.push(id + ": " + bad); continue }
    var examples = []
    var ex = Array.isArray(c.examples) ? c.examples : []
    for (var e = 0; e < ex.length && examples.length < MAX_EXAMPLES; e++) { var s = safeString(ex[e], 120); if (s) examples.push(s) }
    out.push({ id: id, prefix: prefix, sigil: isSigil(prefix), title: title, summary: safeString(c.summary, 200), args: args, examples: examples })
  }
  return { commands: out, errors: errors }
}

// The command with the user's prefix applied. Only a provider's first command
// can be renamed; the others keep what they declared.
function effective(command, override, position) {
  var prefix = position === 0 ? cleanPrefix(override) || command.prefix : command.prefix
  if (prefix === command.prefix) return command
  var out = {}
  for (var k in command) out[k] = command[k]
  out.prefix = prefix
  out.sigil = isSigil(prefix)
  return out
}

// "tr [to] <text>", ":<feeling>", "timer <duration> [name]"
function usage(command) {
  var parts = command.args.map(function(a) { return a.optional ? "[" + a.name + "]" : "<" + a.name + ">" })
  if (!parts.length) return command.prefix
  return command.prefix + (command.sigil ? "" : " ") + parts.join(" ")
}

// The typed form of a prefix, ready for the first argument.
function typed(command) { return command.prefix + (command.sigil ? "" : " ") }

// ------------------------------------------------------------------ index
// providers: [{ key, name, icon, iconFont, iconSource, tint, commands, override }]
// for the enabled providers, in registry order.
// -> { items: [{ key, name, icon, iconFont, iconSource, tint, command }], conflicts: [{ key, prefix, with }] }
function buildIndex(providers) {
  var items = [], conflicts = [], owner = ({})
  for (var i = 0; i < (providers || []).length; i++) {
    var p = providers[i]
    for (var c = 0; c < (p.commands || []).length; c++) {
      var command = effective(p.commands[c], p.override, c)
      var key = command.prefix.toLowerCase()
      if (owner[key] && owner[key] !== p.key) { conflicts.push({ key: p.key, prefix: command.prefix, with: owner[key] }); continue }
      owner[key] = p.key
      items.push({ key: p.key, name: p.name || p.key, icon: p.icon || "", iconFont: p.iconFont || "", iconSource: p.iconSource || "", tint: p.tint || "", command: command })
    }
  }
  return { items: items, conflicts: conflicts }
}

// Which command a query starts with, longest prefix first.
// -> { key, name, command, prefix, rest, exclusive } or null
function match(items, query) {
  var q = String(query || ""), lead = /^\s*/.exec(q)[0], text = q.slice(lead.length), lower = text.toLowerCase()
  var best = null
  for (var i = 0; i < (items || []).length; i++) {
    var cmd = items[i].command, p = cmd.prefix, pl = p.toLowerCase()
    if (lower.indexOf(pl) !== 0) continue
    if (!cmd.sigil && lower.length > pl.length && !/\s/.test(lower.charAt(pl.length))) continue
    if (best && best.prefix.length >= p.length) continue
    var rest = cmd.sigil ? text.slice(p.length) : text.slice(p.length).replace(/^\s/, "")
    best = { key: items[i].key, name: items[i].name, command: cmd, prefix: p, rest: rest, exclusive: true }
  }
  return best
}

// The placeholders still to type and the argument the caret is on.
// -> { ghost, index, arg } ghost: "" when every argument has a word
function placeholders(command, rest) {
  var args = command.args, r = String(rest || "")
  if (!args.length) return { ghost: "", index: -1, arg: null }
  var words = r.trim() ? r.trim().split(/\s+/) : []
  var endsWithSpace = r.length > 0 && /\s$/.test(r)
  var current = r === "" ? 0 : endsWithSpace ? words.length : words.length - 1
  for (var i = 0; i < args.length; i++) if (args[i].rest && current > i) current = i
  if (current >= args.length) return { ghost: "", index: -1, arg: null }
  var from = r === "" || endsWithSpace ? current : current + 1
  var cur = args[current]
  if (cur.rest && words.length - current > 0) from = args.length     // a word is already in the rest argument: nothing more to show
  var ghost = args.slice(from).map(function(a) { return a.optional ? "[" + a.name + "]" : "<" + a.name + ">" }).join(" ")
  if (ghost && !(r === "" || endsWithSpace)) ghost = " " + ghost
  return { ghost: ghost, index: current, arg: cur }
}

// The ghost text for the field: the placeholders, with a space in front when
// the user has typed a bare word prefix ("tr" → "tr [to] <text>").
function ghost(m, text) {
  if (!m) return ""
  var p = placeholders(m.command, m.rest).ghost
  if (p && m.rest === "" && !m.command.sigil && !/\s$/.test(String(text || ""))) p = " " + p
  return p
}

// The line under the search field: the action, then the argument the caret
// is on and what it means.
function hintLine(m) {
  if (!m) return ""
  var cmd = m.command, p = placeholders(cmd, m.rest)
  if (p.arg) return cmd.title + " · " + p.arg.name + ": " + (p.arg.hint || "") + (p.arg.optional ? " (optional)" : "")
  return cmd.title + (cmd.summary ? " · " + cmd.summary : "")
}

// -------------------------------------------------------------------- rows
function queryEffect(text) { return { type: "query", text: String(text || "") } }

function commandRow(item, extra) {
  var cmd = item.command
  var row = { id: "command/" + item.key + "/" + cmd.id, title: cmd.title, subtitle: usage(cmd) + (cmd.summary ? " · " + cmd.summary : ""),
              icon: item.icon || "", iconFont: item.iconFont || "", iconSource: item.iconSource || "", tint: item.tint || "",
              section: "Commands", verb: "Type", tier: "item", accessory: cmd.prefix, keywords: cmd.prefix + " " + item.key + " " + item.name,
              description: cmd.summary, hint: "↵ types " + cmd.prefix, action: queryEffect(typed(cmd)) }
  for (var k in (extra || {})) row[k] = extra[k]
  return row
}

// The "/" screen: every command the user can type, filtered by the rest of
// the line ("/tr"), in registry order when there is no filter.
function helpRows(items, query) {
  var q = String(query || "").trim(), out = []
  for (var i = 0; i < (items || []).length; i++) {
    if (items[i].command.prefix === HELP_PREFIX) continue
    var row = commandRow(items[i], { order: i })
    if (!q) row.score = 1000 - i
    out.push(row)
  }
  return out
}

// Rows the root offers for a query that names a command without using its
// prefix ("trans" → Translate, "emo" → Emoji): Tab or Enter types the prefix.
function suggestRows(items, query, limit) {
  var q = String(query || "").trim(), out = []
  if (!q) return out
  for (var i = 0; i < (items || []).length && out.length < (limit || 3); i++) {
    var cmd = items[i].command
    if (cmd.prefix === HELP_PREFIX) continue
    var score = Match.match(q, cmd.title, cmd.prefix + " " + items[i].key, "", cmd.summary)
    if (!(score > 0)) continue
    out.push(commandRow(items[i], { score: score, order: i, hint: "tab types " + cmd.prefix }))
  }
  return out
}

// The Usage section at the top of an extension's screen: the usage line,
// runnable examples, and the prefix row when it can be changed.
// -> rows; settingsScope: "settings/<id>" when the extension is on, "" otherwise
function usageRows(commands, override, settingsScope) {
  var out = []
  for (var i = 0; i < (commands || []).length; i++) {
    var cmd = effective(commands[i], override, i), u = usage(cmd)
    out.push({ id: "usage/" + cmd.id, title: u, subtitle: cmd.title + (cmd.summary ? " · " + cmd.summary : ""), icon: "", section: "Usage",
               verb: "Type", tier: "item", order: i * 10, keywords: cmd.prefix + " usage " + cmd.title, hint: "↵ types " + cmd.prefix, action: queryEffect(typed(cmd)) })
    for (var a = 0; a < cmd.args.length; a++) {
      var arg = cmd.args[a]
      out.push({ id: "usage/" + cmd.id + "/arg/" + arg.name, title: (arg.optional ? "[" + arg.name + "]" : "<" + arg.name + ">") + (arg.hint ? "  " + arg.hint : ""),
                 subtitle: (arg.optional ? "Optional" : "Required") + (arg.rest ? " · the rest of the line" : ""), icon: "", section: "Usage", verb: "", tier: "item",
                 order: i * 10 + 1 + a * 0.1, disabled: true, keywords: "argument " + arg.name, action: { type: "noop" } })
    }
    for (var e = 0; e < cmd.examples.length; e++)
      out.push({ id: "usage/" + cmd.id + "/example/" + e, title: cmd.examples[e], subtitle: "Try it", icon: "", section: "Usage", verb: "Try",
                 tier: "item", order: i * 10 + 2 + e, keywords: "example try", action: queryEffect(cmd.examples[e]) })
  }
  if (out.length) {
    var first = effective(commands[0], override, 0)
    out.push({ id: "usage/prefix", title: "Prefix", subtitle: settingsScope ? "Change the word that triggers it" : "Turn the extension on to change the word that triggers it",
               icon: "󰒓", section: "Usage", verb: settingsScope ? "Change" : "", tier: "item", order: 90, accessory: first.prefix, keywords: "prefix trigger rename",
               disabled: !settingsScope, action: settingsScope ? { type: "navigate", scope: settingsScope + "/prefix", title: "Prefix" } : { type: "noop" } })
  }
  return out
}

// "Translate is on · type tr <text>, or find it by name"
function enabledNotice(name, commands, override) {
  if (!commands || !commands.length) return name + " is on"
  return name + " is on · type " + usage(effective(commands[0], override, 0)) + ", or find it by name"
}
