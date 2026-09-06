.pragma library
.import "Match.js" as Match

// Extensions: community providers as installable Omarchy plugins, managed
// from inside the palette. Pure functions over the Omarchy plugin registry,
// the Keystroke extension index, the marketplace catalog and the output of the
// git/omarchy commands the provider runs. providers/Extensions.qml owns the
// processes; everything that decides what to show or run lives here so it can
// be unit-tested.
//
// Scopes: extensions (the screen) › extensions/<plugin id> (one extension)

var KEY = "extensions"
var ICON = "󰏓"
var INDEX_URL = "https://raw.githubusercontent.com/evindor/keystroke/main/extensions/index.json"
var CATALOG_URL = "https://plugins.omarchy.org/catalog.json"
var MARKER = "x-keystroke"

function navigate(scope, title) { return { type: "navigate", scope: scope, title: title } }
function op(name, fields) { var a = { type: "ext", op: name }; for (var k in fields || {}) a[k] = fields[k]; return a }

function safeString(v, limit) { return String(v === undefined || v === null ? "" : v).replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, limit || 400) }

// A git URL the plugin CLI accepts as-is. Bare owner/repo shorthands are
// expanded to GitHub; anything that could be read as a git option is refused
// (omarchy-git-url-check does the same before cloning).
function gitUrl(text) {
  var t = safeString(text, 512)
  if (!t || t.charAt(0) === "-" || /\s/.test(t)) return ""
  if (/^https:\/\/[A-Za-z0-9.-]+\/[^\s]+$/.test(t)) return t
  if (/^git@[A-Za-z0-9.-]+:[^\s]+$/.test(t)) return t
  if (/^[A-Za-z0-9][A-Za-z0-9-]*\/[A-Za-z0-9._-]+$/.test(t)) return "https://github.com/" + t.replace(/\.git$/, "") + ".git"
  return ""
}

function repoSlug(url) {
  var m = /github\.com[:\/]([^\/\s]+\/[^\/\s]+?)(?:\.git)?\/?$/.exec(String(url || ""))
  return m ? m[1].toLowerCase() : String(url || "").toLowerCase()
}

// The Keystroke index: { version: 1, extensions: [ { id, name, description, author, repo, tags } ] }
function parseIndex(text) {
  var data
  try { data = JSON.parse(String(text || "")) } catch (e) { return [] }
  if (!data || data.version !== 1 || !Array.isArray(data.extensions)) return []
  var out = []
  for (var i = 0; i < data.extensions.length; i++) {
    var e = data.extensions[i]
    if (!e || typeof e !== "object") continue
    var id = safeString(e.id, 120).toLowerCase(), repo = gitUrl(e.repo)
    if (!id || !repo) continue
    out.push({ id: id, name: safeString(e.name, 80) || id, description: safeString(e.description, 300), author: safeString(e.author, 80),
               repo: repo, tags: Array.isArray(e.tags) ? e.tags.map(function(t) { return safeString(t, 30) }).filter(Boolean) : [], source: "index" })
  }
  return out
}

// The marketplace catalog (plugins.omarchy.org/catalog.json) does not carry
// manifests, so a Keystroke extension is recognised by naming itself one:
// "keystroke" in the id, name or tags, or a description that speaks of
// Keystroke the palette ("for Keystroke", "Keystroke extension") rather than
// of key presses ("one keystroke away").
function namesKeystroke(p) {
  var id = String(p.id || "").toLowerCase(), name = String(p.name || "").toLowerCase()
  if (id.indexOf("keystroke") >= 0 || name.indexOf("keystroke") >= 0) return true
  var tags = Array.isArray(p.tags) ? p.tags : []
  for (var i = 0; i < tags.length; i++) if (String(tags[i]).toLowerCase() === "keystroke") return true
  var d = String(p.description || "")
  return /\b(for|extends|inside|into|in|with|the)\s+keystroke\b(?!s)/i.test(d) || /\bkeystroke\s+(extension|provider|palette|command palette|menu)\b/i.test(d)
}

function parseCatalog(text) {
  var data
  try { data = JSON.parse(String(text || "")) } catch (e) { return [] }
  var plugins = data && Array.isArray(data.plugins) ? data.plugins : []
  var out = []
  for (var i = 0; i < plugins.length; i++) {
    var p = plugins[i]
    if (!p || typeof p !== "object" || p.sourceType === "builtin") continue
    if (!namesKeystroke(p)) continue
    var repo = gitUrl(p.repo)
    if (!repo || p.installAvailable === false) continue
    out.push({ id: safeString(p.id, 120).toLowerCase(), name: safeString(p.name, 80) || p.id, description: safeString(p.description, 300),
               author: safeString(p.author, 80), repo: repo, tags: Array.isArray(p.tags) ? p.tags.slice(0, 5) : [], source: "marketplace",
               verified: p.verificationStatus === "verified" })
  }
  return out
}

// One list to discover from: the index first, the marketplace filling in what
// the index does not know, keyed by plugin id and then by repository.
function discover(indexEntries, catalogEntries) {
  var out = [], seenId = ({}), seenRepo = ({})
  var all = (indexEntries || []).concat(catalogEntries || [])
  for (var i = 0; i < all.length; i++) {
    var e = all[i], slug = repoSlug(e.repo)
    if (seenId[e.id] || seenRepo[slug]) continue
    seenId[e.id] = true; seenRepo[slug] = true
    out.push(e)
  }
  return out
}

// Installed extensions from the Omarchy registry: every plugin carrying the
// marker, loaded or not. isEnabled(id): Omarchy's own switch (shell.json);
// enabledIn(id): Keystroke's (keystroke.json); git: { id: { head, remote,
// remoteHead } } from the last update check.
function installed(installedPlugins, isEnabled, enabledIn, git) {
  var out = []
  for (var id in installedPlugins || {}) {
    var m = installedPlugins[id]
    if (!m || typeof m !== "object" || !m[MARKER] || typeof m[MARKER] !== "object") continue
    var g = git && git[id] ? git[id] : null
    out.push({ id: id, name: safeString(m.name, 80) || id, version: safeString(m.version, 64), description: safeString(m.description, 300),
               author: safeString(m.author, 80), homepage: safeString(m.homepage, 512), apiVersion: m[MARKER].apiVersion,
               loaded: isEnabled ? !!isEnabled(id) : false, enabled: enabledIn ? !!enabledIn(id) : false,
               git: g ? g.git !== false : true, remote: g ? g.remote : "", checked: !!(g && g.fetched),
               updateAvailable: !!(g && g.head && g.remoteHead && g.head !== g.remoteHead) })
  }
  out.sort(function(a, b) { return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : 1 })
  return out
}

// ------------------------------------------------------------------ commands

function pluginsDir(home) { return home + "/.config/omarchy/plugins" }
function bin(omarchyPath, name) { return omarchyPath + "/bin/" + name }

function installArgv(omarchyPath, url) { return [bin(omarchyPath, "omarchy-plugin-add"), url, "--yes", "--enable"] }
function updateArgv(omarchyPath, id) { return [bin(omarchyPath, "omarchy-plugin-update"), id, "--yes"] }
function removeArgv(omarchyPath, id) { return [bin(omarchyPath, "omarchy-plugin-remove"), id, "--yes"] }

// One fetch per git-managed extension; prints `id \t HEAD \t remote HEAD \t remote url`
// (empty fields for a folder that is not a git checkout) and never merges.
// Ids come as arguments, never through the script text.
var CHECK_SCRIPT = 'dir="$1"; shift; for id in "$@"; do d="$dir/$id"; ' +
  'if [ ! -d "$d/.git" ]; then printf "%s\\t\\t\\t\\n" "$id"; continue; fi; ' +
  'remote=$(git -C "$d" remote get-url origin 2>/dev/null); head=$(git -C "$d" rev-parse HEAD 2>/dev/null); ' +
  'if git -C "$d" fetch --quiet origin HEAD 2>/dev/null; then fetched=$(git -C "$d" rev-parse FETCH_HEAD 2>/dev/null); else fetched=""; fi; ' +
  'printf "%s\\t%s\\t%s\\t%s\\n" "$id" "$head" "$fetched" "$remote"; done'

function checkArgv(home, ids) {
  return ["env", "GIT_TERMINAL_PROMPT=0", "GIT_SSH_COMMAND=ssh -oBatchMode=yes", "bash", "-c", CHECK_SCRIPT, "keystroke-extensions", pluginsDir(home)].concat(ids || [])
}

function parseCheck(text) {
  var out = ({}), lines = String(text || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var parts = lines[i].split("\t")
    if (parts.length < 4 || !parts[0]) continue
    out[parts[0]] = { git: !!parts[1], head: parts[1], remoteHead: parts[2], remote: parts[3], fetched: !!parts[2] }
  }
  return out
}

// omarchy-plugin-add reports what it installed: "Added <id> into <folder>".
function parseAdded(output) {
  var m = /(?:^|\n)Added (\S+) into /.exec(String(output || ""))
  return m ? m[1] : ""
}

function fetchArgv(url) { return ["curl", "-fsSL", "--max-time", "20", "--", url] }

// Jobs run detached from the palette: omarchy-plugin-add/update/remove ask
// the shell to rescan its plugins, and a rescan destroys and recreates every
// plugin instance, this provider included. The wrapper records the job in
// <dir>/job.json, runs the command, writes <dir>/result.json (job, exit code,
// output) and, for anything but a check, tells the user through a
// notification; whichever provider instance is alive next reads the result.
var JOB_SCRIPT = 'dir="$1"; job="$2"; notify="$3"; label="$4"; shift 4; mkdir -p "$dir"; printf "%s" "$job" > "$dir/job.json"; ' +
  '"$@" > "$dir/log" 2>&1; code=$?; ' +
  'jq -n --arg code "$code" --rawfile log "$dir/log" --argjson job "$job" \'{job: $job, code: ($code | tonumber), output: $log}\' > "$dir/result.tmp" && mv "$dir/result.tmp" "$dir/result.json"; ' +
  'rm -f "$dir/job.json"; ' +
  'if [ -n "$label" ] && [ -x "$notify" ]; then if [ "$code" = 0 ]; then "$notify" -g "󰏓" "Keystroke" "$label"; else "$notify" -g "󰀦" "Keystroke" "$label failed: $(tail -n 1 "$dir/log")"; fi; fi'

function jobArgv(dir, job, omarchyPath, argv) {
  var done = job.kind === "check" ? "" : String(job.done || job.label || "")
  return ["bash", "-c", JOB_SCRIPT, "keystroke-extension-job", dir, JSON.stringify(job), bin(omarchyPath, "omarchy-notification-send"), done].concat(argv)
}

function parseResult(text) {
  var data
  try { data = JSON.parse(String(text || "")) } catch (e) { return null }
  if (!data || typeof data !== "object" || !data.job || typeof data.job !== "object") return null
  return { job: data.job, code: Number(data.code), output: String(data.output || "") }
}

// ---------------------------------------------------------------------- rows

function navRow(score) {
  return { id: "open", title: "Extensions", subtitle: "Install, update and manage community providers", icon: ICON, section: "Keystroke",
           verb: "Open", tier: "item", score: score, order: 8, keywords: "plugins store marketplace community install",
           description: "extensions plugins store marketplace community providers install update", action: navigate(KEY, "Extensions") }
}

function stateText(e) {
  if (!e.loaded) return "Not loaded"
  return e.enabled ? "On" : "Off"
}

function installedRow(e, scoped) {
  var state = e.updateAvailable ? "Update available" : stateText(e)
  var sub = (e.version ? "v" + e.version + " · " : "") + (e.loaded ? (e.enabled ? "Enabled" : "Installed, off in Keystroke") : "Installed, not loaded in omarchy-shell") + " · " + e.id
  return { id: "installed/" + e.id, title: e.name, subtitle: sub, icon: ICON, section: "Installed", verb: "Open", tier: "item", order: 0,
           accessory: state, keywords: e.id, description: e.description, badge: "plugin", path: scoped ? "" : "Extensions › " + e.name,
           action: navigate(KEY + "/" + e.id, e.name), altAction: e.enabled ? op("enable", { id: e.id, name: e.name, value: false }) : op("enable", { id: e.id, name: e.name, value: true }),
           hint: e.enabled ? "ctrl ↵ turn off" : "ctrl ↵ turn on" }
}

function discoverRow(e, order) {
  return { id: "discover/" + e.id, title: e.name, subtitle: (e.author ? e.author + " · " : "") + repoSlug(e.repo), icon: "", section: "Discover",
           verb: "Install", tier: "item", order: order, badge: e.source === "marketplace" ? "marketplace" : "index", keywords: e.id + " " + e.tags.join(" "),
           description: e.description, preview: e.description || e.name, previewLabel: "EXTENSION", previewDetail: e.repo,
           confirm: "Install " + e.name + " from " + e.repo + "? It runs unsandboxed in your shell with your permissions.",
           action: op("install", { id: e.id, name: e.name, url: e.repo }), altAction: { type: "url", url: e.repo }, hint: "ctrl ↵ repository" }
}

function urlRow(url) {
  return { id: "install-url", title: "Install from " + url, subtitle: "Clones the repository, validates the manifest, enables the plugin", icon: "",
           section: "Install", verb: "Install", tier: "answer", score: 100, order: 0,
           confirm: "Install a plugin from " + url + "? It runs unsandboxed in your shell with your permissions.",
           action: op("install", { id: "", name: url, url: url }) }
}

function jobRow(job) {
  return { id: "job", title: job.label, subtitle: job.detail || "Working…", icon: "", section: "Working", verb: "", tier: "answer", score: 200, order: -10,
           disabled: true, action: { type: "noop" } }
}

// The Extensions screen. state: { installed, discover, job, fetching, checked, error, marketplace }
function screenRows(query, state) {
  var q = String(query || "").trim(), rows = [], i
  if (state.job) rows.push(jobRow(state.job))
  var url = q ? gitUrl(q) : ""
  if (url && q.indexOf("/") > 0) rows.push(urlRow(url))
  var inst = state.installed || [], disc = state.discover || []
  var installedIds = ({})
  for (i = 0; i < inst.length; i++) { installedIds[inst[i].id] = true; rows.push(installedRow(inst[i], true)) }
  if (!q && !inst.length)
    rows.push({ id: "none", title: "No extensions installed", subtitle: "Pick one below, or type a git URL such as owner/repo", icon: ICON, section: "Installed",
                verb: "", tier: "item", score: 1, order: 0, disabled: true, action: { type: "noop" } })
  var updates = 0
  for (i = 0; i < inst.length; i++) if (inst[i].updateAvailable) updates++
  rows.push({ id: "check", title: updates ? "Update all (" + updates + ")" : "Check for updates", subtitle: state.checked ? "Checked " + state.checked : "Fetches every git-managed extension without merging",
              icon: "", section: "Actions", verb: "Run", tier: "item", order: 1, keywords: "update upgrade check fetch", description: "update upgrade refresh check",
              action: updates ? op("update-all") : op("check") })
  rows.push({ id: "refresh", title: "Refresh catalog", subtitle: state.fetching ? "Fetching…" : (state.error ? state.error : "Keystroke index" + (state.marketplace ? " and the Omarchy marketplace" : "")),
              icon: "", section: "Actions", verb: "Run", tier: "item", order: 2, keywords: "refresh reload catalog index marketplace", description: "refresh reload catalog index marketplace",
              action: op("refresh") })
  var n = 0
  for (i = 0; i < disc.length; i++) {
    if (installedIds[disc[i].id]) continue
    rows.push(discoverRow(disc[i], 10 + n++))
  }
  if (!q) for (i = 0; i < rows.length; i++) if (rows[i].score === undefined) rows[i].score = 1
  return rows
}

// One extension's screen.
function detailRows(query, e, state) {
  var rows = []
  if (state && state.job && state.job.id === e.id) rows.push(jobRow(state.job))
  var loadedSchema = { key: "loaded", type: "boolean" }
  rows.push({ id: e.id + "/enabled", title: "Enabled", subtitle: e.loaded ? "Include this extension's results in Keystroke" : "Turning it on also loads the plugin into omarchy-shell",
              icon: "", section: e.name, verb: "Toggle", tier: "item", order: 0, accessory: e.enabled ? "On" : "Off", keywords: "enable disable on off",
              action: op("enable", { id: e.id, name: e.name, value: !e.enabled }) })
  rows.push({ id: e.id + "/loaded", title: "Loaded in omarchy-shell", subtitle: e.loaded ? "The plugin's service is running in your shell" : "Not loaded: omarchy plugin enable " + e.id,
              icon: "", section: e.name, verb: "Toggle", tier: "item", order: 1, accessory: e.loaded ? "On" : "Off", keywords: "load unload shell omarchy",
              action: op("load", { id: e.id, name: e.name, value: !e.loaded }) })
  rows.push({ id: e.id + "/settings", title: "Settings", subtitle: "Keystroke Settings › " + e.name, icon: "󰒓", section: e.name, verb: "Open", tier: "item", order: 2,
              action: navigate("settings/" + e.id, e.name) })
  if (e.git) {
    rows.push({ id: e.id + "/update", title: e.updateAvailable ? "Update now" : "Check for updates",
                subtitle: e.updateAvailable ? "Fast-forwards to " + (e.remote || "origin") + " and validates the manifest" : (e.remote || "Git-managed"),
                icon: "", section: e.name, verb: "Run", tier: "item", order: 3, accessory: e.updateAvailable ? "Update available" : "",
                keywords: "update upgrade check", action: e.updateAvailable ? op("update", { id: e.id, name: e.name }) : op("check", { id: e.id }) })
  } else {
    rows.push({ id: e.id + "/local", title: "Not git-managed", subtitle: "Copied by hand; update it by replacing the folder", icon: "", section: e.name,
                verb: "", tier: "item", order: 3, disabled: true, action: { type: "noop" } })
  }
  if (e.homepage || e.remote)
    rows.push({ id: e.id + "/repo", title: "Open repository", subtitle: e.homepage || e.remote, icon: "", section: e.name, verb: "Open", tier: "item", order: 4,
                keywords: "repository github source homepage", action: { type: "url", url: e.homepage || e.remote } })
  rows.push({ id: e.id + "/remove", title: "Remove", subtitle: "Unloads the plugin and deletes " + e.id + " from ~/.config/omarchy/plugins", icon: "󰆴", section: e.name,
              verb: "Remove", tier: "item", order: 9, keywords: "remove uninstall delete",
              confirm: "Remove " + e.name + "? Its Keystroke settings stay in keystroke.json.", action: op("remove", { id: e.id, name: e.name }) })
  rows.push({ id: e.id + "/about", title: e.name + (e.version ? " v" + e.version : ""), subtitle: [e.author, e.description].filter(Boolean).join(" · ") || e.id, icon: ICON,
              section: "About", verb: "", tier: "item", order: 20, disabled: true, badge: "plugin", action: { type: "noop" } })
  var q = String(query || "").trim()
  if (!q) for (var i = 0; i < rows.length; i++) if (rows[i].score === undefined) rows[i].score = 1
  return rows
}

function scopeId(scope) {
  var s = String(scope || "")
  if (s === KEY) return ""
  return s.indexOf(KEY + "/") === 0 ? s.slice(KEY.length + 1) : null
}
