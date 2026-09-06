.pragma library
.import "Match.js" as Match

// File and folder search under the home folder, on top of `fd` (Omarchy's
// base package set ships it next to ripgrep and plocate). Everything here is
// pure: the provider owns the process, this module decides what to run and
// what to show.
//
// Why fd, per query, rather than an index: a gitignore-respecting walk of a
// home folder is tens of milliseconds and a bounded query returns in about
// ten, so spawning per keystroke (debounced by the host) is cheaper than
// keeping hundreds of thousands of paths in the QML heap and scoring them in
// JavaScript. fd's `--max-results` stops the walk early, and the words of the
// query are AND-ed as literal substrings, which is what people expect from a
// file search: the last word has to be in the name itself, earlier words may
// sit anywhere in the path ("docs readme", "bindings lua"). Without that rule
// one matching folder floods the list with its children. Fuzzy scoring is
// applied afterwards, to the bounded candidate set, to decide the top rows.

var MIN_QUERY = 2          // one letter matches half the disk and ranks nothing
var CANDIDATES = 400       // fd stops after this many hits; the best `limit` survive
var SCOPED_LIMIT = 60      // inside the Files screen the root limit does not apply
var WEIGHT = 0.55          // files rank below apps and Omarchy entries with the same score
var FLOOR = 12             // fd already confirmed a substring match; keep the row

var IMAGE = { png: 1, jpg: 1, jpeg: 1, webp: 1, gif: 1, bmp: 1, svg: 1, avif: 1 }
var ICONS = {
  image: "󰋩", pdf: "󰈦", archive: "󰀼", audio: "󰈣", video: "󰈫",
  code: "󰈙", text: "󰈙", file: "󰈔", folder: "󰉋"
}
var KIND = {
  pdf: "pdf", zip: "archive", tar: "archive", gz: "archive", xz: "archive", zst: "archive", "7z": "archive", rar: "archive",
  mp3: "audio", flac: "audio", ogg: "audio", wav: "audio", m4a: "audio", opus: "audio",
  mp4: "video", mkv: "video", webm: "video", mov: "video", avi: "video",
  md: "text", txt: "text", json: "text", yaml: "text", yml: "text", toml: "text", conf: "text", ini: "text", csv: "text",
  js: "code", ts: "code", py: "code", rs: "code", go: "code", c: "code", h: "code", cpp: "code", sh: "code", qml: "code", html: "code", css: "code", lua: "code"
}

function words(query) {
  return String(query || "").trim().split(/\s+/).filter(function(w) { return w.length > 0 })
}

// Null when there is nothing worth asking fd: too short, or both kinds off.
function cacheKey(query, settings) {
  var ws = words(query)
  if (!ws.length || ws.join("").length < MIN_QUERY) return null
  if (!settings.files && !settings.folders) return null
  return ws.join(" ").toLowerCase() + "\n" + (settings.files ? "f" : "") + (settings.folders ? "d" : "") + (settings.hidden ? "h" : "")
}

function escapeRegex(word) {
  return word.replace(/[.*+?^${}()|[\]\\\/-]/g, "\\$&")
}

// Literal argv, no shell: the query lands in fd's own arguments. The words
// are regex-escaped literals; the last one is anchored to the final path
// segment. Extra words go through `--and=` and the anchored one comes after
// `--`, so a word that starts with a dash is never read as a flag.
function argv(query, home, settings) {
  var ws = words(query)
  var out = ["fd", "--ignore-case", "--full-path", "--color", "never", "--absolute-path",
             "--base-directory", home, "--max-results", String(CANDIDATES)]
  if (settings.hidden) out.push("--hidden", "--exclude", ".git")
  if (settings.files && !settings.folders) out.push("--type", "f")
  if (settings.folders && !settings.files) out.push("--type", "d")
  for (var i = 0; i < ws.length - 1; i++) out.push("--and=" + escapeRegex(ws[i]))
  out.push("--", "[^/]*" + escapeRegex(ws[ws.length - 1]) + "[^/]*$")
  return out
}

// fd prints one absolute path per line; directories carry a trailing slash.
function parse(output, home) {
  var lines = String(output || "").split("\n"), out = []
  var prefix = home.replace(/\/+$/, "") + "/"
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i]
    if (!line) continue
    var dir = line.charAt(line.length - 1) === "/"
    var abs = dir ? line.slice(0, -1) : line
    if (abs.indexOf(prefix) !== 0 || abs.length === prefix.length) continue
    out.push({ path: abs, rel: abs.slice(prefix.length), dir: dir })
  }
  return out
}

function baseName(rel) {
  var slash = rel.lastIndexOf("/")
  return slash >= 0 ? rel.slice(slash + 1) : rel
}

function parentOf(rel) {
  var slash = rel.lastIndexOf("/")
  return slash >= 0 ? rel.slice(0, slash) : ""
}

function extensionOf(name) {
  var dot = name.lastIndexOf(".")
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : ""
}

function kindOf(entry) {
  if (entry.dir) return "folder"
  var ext = extensionOf(baseName(entry.rel))
  if (IMAGE[ext]) return "image"
  return KIND[ext] || "file"
}

function tilde(rel) { return rel ? "~/" + rel : "~" }

// fd matched the absolute path, so a word like "home" or the user name hits
// everything; re-check below the home folder: the last word in the name, the
// others anywhere in the relative path.
function matchesRelative(entry, ws) {
  var hay = entry.rel.toLowerCase()
  if (baseName(hay).indexOf(ws[ws.length - 1].toLowerCase()) < 0) return false
  for (var i = 0; i < ws.length - 1; i++) if (hay.indexOf(ws[i].toLowerCase()) < 0) return false
  return true
}

function score(query, entry) {
  var s = Match.match(query, baseName(entry.rel), "", entry.rel)
  return s ? Math.max(FLOOR, Math.round(s * WEIGHT)) : FLOOR
}

function openEffect(entry) { return { type: "exec", argv: ["xdg-open", entry.path] } }

// Omarchy's own launchers wrap terminals the same way; a file opens a
// terminal in its folder.
function terminalEffect(entry) {
  var dir = entry.dir ? entry.path : entry.path.slice(0, entry.path.lastIndexOf("/"))
  return { type: "exec", argv: ["setsid", "uwsm-app", "--", "xdg-terminal-exec", "--dir=" + dir] }
}

function row(query, entry, order) {
  var name = baseName(entry.rel), kind = kindOf(entry)
  var parent = tilde(parentOf(entry.rel))
  return {
    id: entry.rel, title: name, subtitle: parent + (entry.dir ? " · Folder" : ""), icon: ICONS[kind], section: "Files",
    verb: entry.dir ? "Open folder" : "Open", tier: "item", score: score(query, entry), order: order, remember: true,
    hint: "ctrl ↵ terminal", action: openEffect(entry), altAction: terminalEffect(entry),
    preview: tilde(entry.rel), previewLabel: entry.dir ? "FOLDER" : "FILE", previewImage: kind === "image" ? entry.path : "",
    previewDetail: entry.dir ? "↵ opens in your file manager · Ctrl+↵ opens a terminal here"
                             : "↵ opens with the default app · Ctrl+↵ opens a terminal in " + parent
  }
}

// The best `limit` rows out of fd's candidates. Scoring happens here, on a
// few hundred entries at most, never on the whole tree.
function rows(query, entries, settings, scoped) {
  var ws = words(query), limit = scoped ? SCOPED_LIMIT : settings.limit
  var out = []
  for (var i = 0; i < entries.length; i++) {
    var e = entries[i]
    if (e.dir ? !settings.folders : !settings.files) continue
    if (!matchesRelative(e, ws)) continue
    out.push(row(query, e, i))
  }
  out.sort(function(a, b) { return b.score - a.score || a.order - b.order })
  return out.slice(0, limit)
}
