.pragma library

// The two Hyprland bindings that make "hold the hotkey to dictate" work. They
// live in the user's ~/.config/hypr/bindings.lua inside a marked block that
// Keystroke Settings › Voice writes and rewrites; everything outside the
// markers is left alone.
//
// Hyprland fires a long-press bind (`o`) once the key has been down for the
// keyboard repeat delay, whichever order the keys are released in later, so
// it is the tap-versus-hold decision. The release bind (`r`) only fires
// while the modifier is still held; the palette also watches for the
// modifier's own release, so lifting the chord in either order ends the
// recording.

var BEGIN = "-- >>> keystroke voice: hold the palette hotkey to dictate (written by Keystroke Settings › Voice)"
var END = "-- <<< keystroke voice"
var HOLD = "omarchy-shell shell call omarchy.menu voiceHold '{}'"
var RELEASE = "omarchy-shell shell call omarchy.menu voiceRelease '{}'"

function parseKeys(text) {
  var out = [], parts = String(text || "").split(",")
  for (var i = 0; i < parts.length; i++) {
    var k = parts[i].trim().replace(/\s+/g, " ")
    if (k && out.indexOf(k) < 0) out.push(k)
  }
  return out
}

function lua(s) { return "\"" + String(s).replace(/\\/g, "\\\\").replace(/"/g, "\\\"") + "\"" }

function block(keys) {
  var lines = [BEGIN]
  var combos = parseKeys(Array.isArray(keys) ? keys.join(",") : keys)
  for (var i = 0; i < combos.length; i++) {
    lines.push("o.bind(" + lua(combos[i]) + ", nil, " + lua(HOLD) + ", { long_press = true })")
    lines.push("o.bind(" + lua(combos[i]) + ", nil, " + lua(RELEASE) + ", { release = true })")
  }
  lines.push(END)
  return lines.join("\n")
}

function find(text) {
  var s = String(text || "")
  var a = s.indexOf(BEGIN)
  if (a < 0) return null
  var b = s.indexOf(END, a)
  if (b < 0) return { start: a, end: s.length, body: s.slice(a) }
  var end = b + END.length
  return { start: a, end: end, body: s.slice(a, end) }
}

// "missing" | "outdated" | "installed"
function status(text, keys) {
  var hit = find(text)
  if (!hit) return "missing"
  return hit.body === block(keys) ? "installed" : "outdated"
}

function apply(text, keys) {
  var s = String(text || "")
  var hit = find(s)
  var fresh = block(keys)
  if (hit) return s.slice(0, hit.start) + fresh + s.slice(hit.end)
  if (s.length && s.charAt(s.length - 1) !== "\n") s += "\n"
  if (s.length) s += "\n"
  return s + fresh + "\n"
}

function remove(text) {
  var s = String(text || "")
  var hit = find(s)
  if (!hit) return s
  var before = s.slice(0, hit.start).replace(/\n+$/, "\n")
  var after = s.slice(hit.end).replace(/^\n+/, "")
  return before + after
}
