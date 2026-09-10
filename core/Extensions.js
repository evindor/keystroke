.pragma library
.import "Match.js" as Match
.import "Commands.js" as Commands

// Extensions: third-party providers that ship inside Keystroke itself, one
// folder each under extensions/ (reviewed and merged through pull requests,
// like Raycast's extensions repository), plus any folder the user drops into
// ~/.local/share/keystroke/extensions to develop one. Every extension is off
// until the user turns it on; an extension that is off is never compiled or
// instantiated, so a fresh install runs none of this code.
//
// Pure functions over the folder scan and the palette's rows live here so
// they can be unit-tested; providers/Registry.qml owns the scan process and
// the service instances, providers/Extensions.qml the screen.
//
// Scopes: extensions (the screen) › extensions/<id> (one extension)

var KEY = "extensions"
var ICON = "󰏓"
var FILE = "extension.json"
var ID_RE = /^[a-z0-9][a-z0-9-]{0,63}$/
var SOURCE_URL = "https://github.com/evindor/keystroke/tree/main/extensions/"
var GUIDE_URL = "https://github.com/evindor/keystroke/blob/main/CONTRIBUTING.md#build-an-extension"

function navigate(scope, title) { return { type: "navigate", scope: scope, title: title } }
function safeString(v, limit) { return String(v === undefined || v === null ? "" : v).replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, limit || 400) }
function pathOf(url) { return String(url || "").replace(/^file:\/\//, "").replace(/\/$/, "") }
function localDir(home) { return home + "/.local/share/keystroke/extensions" }

// A path inside the extension folder: relative, no `..`, no leading slash.
function insideFolder(p) {
  var s = String(p || "")
  return !!s && s.charAt(0) !== "/" && s.split("/").indexOf("..") < 0 && s.split("/").indexOf("") < 0
}

// ------------------------------------------------------------------ scan
// One record per extension.json, NUL-terminated: the source on the first
// line, the folder on the second, the file after them. The built-in folder
// comes first, the local one after it, so a local folder with the same id
// replaces the shipped one (that is how an author iterates on an extension
// that already ships). The glob skips dot folders.
var SCAN_SCRIPT = 'emit() { for m in "$2"/*/extension.json; do [ -f "$m" ] || continue; printf "%s\\n%s\\n" "$1" "${m%/extension.json}"; cat "$m"; printf "\\0"; done; }; ' +
  'emit builtin "$1"; emit local "$2"'
function scanArgv(builtinDir, localDir) { return ["bash", "-c", SCAN_SCRIPT, "keystroke-extensions-scan", builtinDir, localDir] }

// { manifests: { id: manifest }, problems: [{ id, message }] }. A manifest is
// the parsed extension.json plus `id` (the folder name), `dir` and `source`
// ("builtin" | "local"). reserved: keys an extension may not take (the bundled
// provider ids). A folder that cannot be used is reported, never half-loaded.
function parseScan(text, reserved) {
  var manifests = ({}), problems = []
  var taken = ({})
  for (var r = 0; r < (reserved || []).length; r++) taken[reserved[r]] = true
  var records = String(text || "").split("\u0000")
  for (var i = 0; i < records.length; i++) {
    var rec = records[i], a = rec.indexOf("\n")
    if (a < 0) continue
    var b = rec.indexOf("\n", a + 1)
    if (b < 0) continue
    var source = rec.slice(0, a), dir = rec.slice(a + 1, b), body = rec.slice(b + 1)
    var id = dir.slice(dir.lastIndexOf("/") + 1)
    var problem = validate(id, body, taken)
    if (problem) { problems.push({ id: id, message: problem.message }); continue }
    var m = parseManifest(body)
    m.id = id; m.dir = dir; m.source = source === "local" ? "local" : "builtin"
    manifests[id] = m
  }
  return { manifests: manifests, problems: problems }
}

function parseManifest(body) {
  var m = JSON.parse(body)
  var out = { name: safeString(m.name, 80), version: safeString(m.version, 64), author: safeString(m.author, 80), description: safeString(m.description, 300),
              apiVersion: m.apiVersion, icon: safeString(m.icon, 8), color: safeString(m.color, 32), homepage: safeString(m.homepage, 512),
              entry: safeString(m.entry || "Service.qml", 200), license: safeString(m.license, 40) }
  if (m.setup && typeof m.setup === "object") out.setup = { run: safeString(m.setup.run, 200), summary: safeString(m.setup.summary, 300) }
  // Commands are kept as declared and compiled by the registry (core/Commands.js),
  // which reports what does not compile; the folder stays usable.
  if (Array.isArray(m.commands)) out.commands = m.commands.slice(0, Commands.MAX_COMMANDS)
  return out
}

// null when the folder is usable, else { message }.
function validate(id, body, taken) {
  if (!ID_RE.test(id)) return { message: "Folder name must be lowercase letters, digits and dashes" }
  if (taken && taken[id]) return { message: "The id " + id + " belongs to a bundled provider" }
  var m
  try { m = JSON.parse(body) } catch (e) { return { message: FILE + " is not valid JSON" } }
  if (!m || typeof m !== "object" || Array.isArray(m)) return { message: FILE + " must be an object" }
  if (m.apiVersion !== 1) return { message: "Needs Keystroke provider API 1, " + FILE + " declares " + JSON.stringify(m.apiVersion === undefined ? null : m.apiVersion) }
  if (!safeString(m.name, 80)) return { message: FILE + " needs a name" }
  var entry = m.entry === undefined ? "Service.qml" : m.entry
  if (typeof entry !== "string" || !insideFolder(entry) || !/\.qml$/.test(entry)) return { message: "entry must be a .qml file inside the extension folder" }
  if (m.setup !== undefined) {
    if (!m.setup || typeof m.setup !== "object" || typeof m.setup.run !== "string" || !insideFolder(m.setup.run))
      return { message: "setup.run must be a script inside the extension folder" }
  }
  if (m.commands !== undefined && !Array.isArray(m.commands)) return { message: "commands must be an array" }
  return null
}

function serviceUrl(manifest) {
  if (!manifest || !manifest.dir || !insideFolder(manifest.entry)) return ""
  return "file://" + manifest.dir + "/" + manifest.entry
}

// The provider entry the registry keeps for an extension that is off or
// failed to load: enough for Settings and the Extensions screen, never asked
// for rows (the host skips disabled providers before calling query).
function placeholder(manifest) {
  return { apiVersion: 1, name: manifest.name || manifest.id, icon: manifest.icon || ICON, color: manifest.color, description: manifest.description,
           commands: manifest.commands, settings: [], query: function() { return [] } }
}

// --------------------------------------------------------------- listing
// One record per extension for the screen. entries: the registry's entries
// (source "extension"); enabledIn(id): Keystroke's switch; problems: [{ id, message }];
// prefixOf(id): the user's prefix for the extension's first command, "" for the declared one.
function list(entries, enabledIn, problems, prefixOf) {
  var trouble = ({})
  for (var p = 0; p < (problems || []).length; p++)
    if (problems[p] && !trouble[problems[p].id]) trouble[problems[p].id] = safeString(problems[p].message, 300)
  var out = []
  for (var i = 0; i < (entries || []).length; i++) {
    var e = entries[i]
    if (e.source !== "extension" || !e.manifest) continue
    var m = e.manifest, p = e.provider || {}
    out.push({ id: m.id, name: safeString(p.name, 80) || m.name || m.id, version: m.version, description: safeString(p.description, 300) || m.description,
               author: m.author, homepage: m.homepage, dir: m.dir, local: m.source === "local", setup: m.setup || null, loaded: !!e.loaded,
               enabled: enabledIn ? !!enabledIn(m.id) : false, problem: trouble[m.id] || "",
               icon: safeString(p.icon, 8) || m.icon || "", iconFont: safeString(p.iconFont, 80), iconSource: safeString(p.iconSource, 1024),
               tint: safeString(p.color, 32) || m.color || "", examples: [], commands: e.commands || [], prefix: prefixOf ? String(prefixOf(m.id) || "") : "" })
  }
  out.sort(function(a, b) { return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : 1 })
  return out
}
function iconOf(e) { return { icon: e.icon || ICON, iconFont: e.iconFont || "", iconSource: e.iconSource || "", tint: e.tint || "" } }

// Keystroke's switch is a plain setting effect; the host writes it, the
// registry loads or destroys the service, and the screen is queried again.
function enableEffect(id, value) {
  return { type: "setting", path: ["providers", id], key: "enabled", value: !!value, schema: { key: "enabled", type: "boolean" } }
}
// The question and what has been checked. No link to the source: the
// palette cannot hand focus to a browser and survive, so the extension's
// screen and Settings carry the source row instead.
function enableConfirm(e) { return "Turn on " + e.name + "?" }
function enableDetail(e) {
  if (e.local) return "This is a local folder in " + e.dir + " that nobody has reviewed. It will run inside your shell with your permissions. Run it at your own risk, and check its code first."
  return "This extension was automatically checked and reviewed before it shipped with Keystroke, and it runs inside your shell with your permissions. Nonetheless, run it at your own risk. It's recommended to check the extension code first."
}

// ------------------------------------------------------------------ setup
// Setup runs in a visible floating terminal, never in the background: the
// user asked for it, watches it, and reads its result. The launcher takes
// one shell string; everything that varies is single-quoted into it.
function shellQuote(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
var SETUP_SCRIPT = 'dir="$1"; run="$2"; cd "$dir" || exit 1; echo "Keystroke: running $run in $dir"; echo; "./$run"; code=$?; echo; echo "$run exited with status $code"; exit $code'
function setupArgv(omarchyPath, e) {
  var run = e.setup ? e.setup.run : ""
  if (!run || !insideFolder(run)) return null
  return [omarchyPath + "/bin/omarchy-launch-floating-terminal-with-presentation",
          "bash -c " + shellQuote(SETUP_SCRIPT) + " keystroke-setup " + shellQuote(e.dir) + " " + shellQuote(run)]
}
function setupConfirm(e) {
  return "Open a terminal and run " + e.setup.run + " from " + e.dir + "?" + (e.setup.summary ? " " + e.setup.summary : "")
}

// ---------------------------------------------------------------------- rows

function navRow(score, counts) {
  var sub = counts && counts.total ? counts.on + " of " + counts.total + " on" : "Third-party providers that ship with Keystroke"
  return { id: "open", title: "Extensions", subtitle: sub, icon: ICON, section: "Keystroke",
           verb: "Open", tier: "item", score: score, order: 8, keywords: "extensions plugins community",
           description: "extensions plugins community providers turn on off enable disable", action: navigate(KEY, "Extensions") }
}

function stateText(e) {
  if (e.problem) return "Needs attention"
  return e.enabled ? "On" : "Off"
}

function listRow(e) {
  var origin = e.local ? "local folder" : "ships with Keystroke"
  var sub = (e.version ? "v" + e.version + " · " : "") + (e.problem ? e.problem : e.enabled ? "On · " + origin : "Off · " + origin)
  var ic = iconOf(e)
  var row = { id: e.id, title: e.name, subtitle: sub, icon: ic.icon, iconFont: ic.iconFont, iconSource: ic.iconSource, tint: ic.tint,
              section: e.enabled ? "On" : "Available", verb: "Open", tier: "item", order: e.enabled ? 0 : 10,
              accessory: stateText(e), keywords: e.id + (e.local ? " local" : ""), description: e.description, badge: e.local ? "local" : "extension",
              action: navigate(KEY + "/" + e.id, e.name) }
  // Turning an extension on runs its code, so that always goes through the
  // confirmation on its own screen; turning it off is one key here.
  if (e.enabled) { row.altAction = enableEffect(e.id, false); row.hint = "ctrl ↵ turn off" }
  return row
}

function guideRow() {
  return { id: "guide", title: "Write your own", subtitle: "A folder in ~/.local/share/keystroke/extensions runs at once; a pull request ships it to everyone",
           icon: "", section: "Extend", verb: "Open guide", tier: "item", order: 90, keywords: "guide contribute develop write local",
           description: "write develop create contribute extension guide local folder pull request", action: { type: "url", url: GUIDE_URL } }
}

// The Extensions screen.
function screenRows(query, extensions) {
  var q = String(query || "").trim(), rows = [], i
  for (i = 0; i < extensions.length; i++) rows.push(listRow(extensions[i]))
  if (!extensions.length)
    rows.push({ id: "none", title: "No extensions found", subtitle: "Keystroke's extensions folder is empty", icon: ICON, section: "Available",
                verb: "", tier: "item", score: 1, order: 0, disabled: true, action: { type: "noop" } })
  rows.push(guideRow())
  if (!q) for (i = 0; i < rows.length; i++) if (rows[i].score === undefined) rows[i].score = 1
  return rows
}

// One extension's screen. Usage comes first: what to type, what the
// arguments mean, examples that run when activated, and the prefix row.
function detailRows(query, e) {
  var rows = Commands.usageRows(e.commands || [], e.prefix, "settings/" + e.id), icons = iconOf(e)
  for (var u = 0; u < rows.length; u++) {
    rows[u].order = rows[u].order - 1000
    if (rows[u].id !== "usage/prefix") { rows[u].icon = icons.icon; rows[u].iconFont = icons.iconFont; rows[u].iconSource = icons.iconSource; rows[u].tint = icons.tint }
  }
  var on = { id: e.id + "/enabled", title: "Enabled", subtitle: e.enabled ? "Answering queries" : "Off: its code is not loaded",
             icon: "", section: e.name, verb: "Toggle", tier: "item", order: 0, accessory: e.enabled ? "On" : "Off", keywords: "enable disable on off",
             action: enableEffect(e.id, !e.enabled) }
  if (!e.enabled) { on.confirm = enableConfirm(e); on.confirmDetail = enableDetail(e) }
  rows.push(on)
  if (e.problem)
    rows.push({ id: e.id + "/problem", title: "Needs attention", subtitle: e.problem, icon: "󰀦", section: e.name, verb: "", tier: "item", order: 1,
                disabled: true, keywords: "problem error attention", action: { type: "noop" } })
  if (e.setup)
    rows.push({ id: e.id + "/setup", title: "Run setup", subtitle: e.setup.summary || "Opens a terminal and runs " + e.setup.run, icon: "",
                section: e.name, verb: "Run", tier: "item", order: 2, keywords: "setup install prepare download build",
                confirm: setupConfirm(e), action: { type: "extension-setup", id: e.id } })
  rows.push({ id: e.id + "/settings", title: "Settings", subtitle: e.enabled ? "Keystroke Settings › " + e.name : "Turn the extension on to see its settings",
              icon: "󰒓", section: e.name, verb: "Open", tier: "item", order: 3, action: navigate("settings/" + e.id, e.name) })
  if (e.local)
    rows.push({ id: e.id + "/folder", title: "Open folder", subtitle: e.dir, icon: "", section: e.name, verb: "Open", tier: "item", order: 4,
                keywords: "folder source directory", action: { type: "exec", argv: ["xdg-open", e.dir] } })
  else
    rows.push({ id: e.id + "/source", title: "Open source", subtitle: e.homepage || SOURCE_URL + e.id, icon: "", section: e.name, verb: "Open", tier: "item", order: 4,
                keywords: "source github repository homepage", action: { type: "url", url: e.homepage || SOURCE_URL + e.id } })
  var ic = iconOf(e)
  rows.push({ id: e.id + "/about", title: e.name + (e.version ? " v" + e.version : ""), subtitle: [e.author, e.description].filter(Boolean).join(" · ") || e.id,
              icon: ic.icon, iconFont: ic.iconFont, iconSource: ic.iconSource, tint: ic.tint,
              section: "About", verb: "", tier: "item", order: 20, disabled: true, badge: e.local ? "local" : "extension", action: { type: "noop" } })
  if (e.examples && e.examples.length)
    rows.push({ id: e.id + "/patterns", title: (e.commands && e.commands.length ? "Also answers " : "Answers queries like ") + e.examples.join(" · "),
                subtitle: "Declared patterns lift this extension's results when a query matches",
                icon: "", section: "About", verb: "", tier: "item", order: 21, disabled: true, keywords: "patterns examples", action: { type: "noop" } })
  var q = String(query || "").trim()
  if (!q) for (var i = 0; i < rows.length; i++) if (rows[i].score === undefined) rows[i].score = 1
  return rows
}

function scopeId(scope) {
  var s = String(scope || "")
  if (s === KEY) return ""
  return s.indexOf(KEY + "/") === 0 ? s.slice(KEY.length + 1) : null
}
