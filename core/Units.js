.pragma library

// Unit and temperature conversion in JS. IANA time zones need tzdata, which
// QML's JavaScript engine does not expose, so time queries are gated here
// (isTimeQuery) and resolved by helpers/timezone.py on demand. The gate only
// has to be time-shaped: the helper owns the grammar and rejects the rest.

// [factor, dimension, aliases, counterpart]. The counterpart is the other
// system's everyday unit, the target for a quantity typed without one
// ("35 lb"). Metres have none because Timer reads a bare "10m" as minutes;
// time, data and millilitres have none because nothing everyday pairs with them.
var UNITS = [
  [1, "length", "m meter meters metre metres"], [0.01, "length", "cm centimeter centimeters", "in"],
  [0.001, "length", "mm millimeter millimeters", "in"], [1000, "length", "km kilometer kilometers", "mi"],
  [0.3048, "length", "ft foot feet", "m"], [0.0254, "length", "in inch inches", "cm"],
  [0.9144, "length", "yd yard yards", "m"], [1609.344, "length", "mi mile miles", "km"],
  [1, "mass", "kg kilogram kilograms", "lb"], [0.001, "mass", "g gram grams", "oz"],
  [0.45359237, "mass", "lb lbs pound pounds", "kg"], [0.028349523125, "mass", "oz ounce ounces", "g"],
  [1, "time", "s sec second seconds"], [60, "time", "min minute minutes"],
  [3600, "time", "h hr hour hours"], [86400, "time", "d day days"],
  [1, "volume", "l liter liters litre litres", "gal"], [0.001, "volume", "ml milliliter milliliters"],
  [3.785411784, "volume", "gal gallon gallons", "l"],
  [1, "data", "b byte bytes"], [1000, "data", "kb"], [1e6, "data", "mb"], [1e9, "data", "gb"],
  [1024, "data", "kib"], [1048576, "data", "mib"], [1073741824, "data", "gib"],
  [1, "speed", "m/s", "km/h"], [1 / 3.6, "speed", "km/h kph", "mph"], [0.44704, "speed", "mph", "km/h"]
]
var LOOKUP = {}
for (var u = 0; u < UNITS.length; u++) {
  var aliases = UNITS[u][2].split(" ")
  for (var a = 0; a < aliases.length; a++) LOOKUP[aliases[a]] = { factor: UNITS[u][0], dimension: UNITS[u][1], counterpart: UNITS[u][3] || "" }
}
var TEMPERATURES = { c: "c", celsius: "c", f: "f", fahrenheit: "f", k: "k", kelvin: "k" }
var TEMPERATURE_COUNTERPARTS = { c: "f", f: "c" }
var UNIT_RE = /^\s*(-?\d+(?:\.\d+)?)\s*([\w\/°]+)(?:\s+(?:in|to)\s+([\w\/°]+))?\s*$/i
// "tomorrow", "next monday", "sep 6", "6 sep 2027", "2026-09-06", each with
// an optional "on" before and "at" after, ahead of the time.
var DATE_PREFIX_RE = /^\s*(?:on\s+)?(?:today|tonight|tomorrow|tmrw|tmr|yesterday|(?:next\s+|this\s+)?(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+[a-z]{3,9}(?:\s+\d{4})?|[a-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)\s+(?:at\s+)?/i
// 10am, 10:30pm, 10.30, 1530, noon, midnight at the start of the query.
var TIME_TOKEN_RE = /^\s*(?:\d{1,2}(?:[:.][0-5]\d)?\s*(?:a\.?m\.?|p\.?m\.?)(?![a-z])|\d{1,2}[:.][0-5]\d(?![\d.])|(?:[01]\d|2[0-3])[0-5]\d(?!\d)|noon|midday|midnight)(?![a-z])/i
var BARE_HOUR_RE = /^\s*\d{1,2}\s+(?:in|from|at)\s+\S/i
var NOW_RE = /^\s*(?:(?:what(?:'s|\s+is)?\s+(?:the\s+)?)?(?:current\s+|local\s+)?time(?:\s+is\s+it)?(?:\s+(?:right\s+)?now)?|now|(?:the\s+)?date)\s+(?:in|at|for|of)\s+\S/i
var ZONE_TIME_RE = /^\s*\S.*\s+(?:time|now)\s*$/i

// Returns { value, unit } or throws Error. Without a target ("35 lb") the
// source's counterpart is used.
function convert(text) {
  var m = UNIT_RE.exec(String(text || ""))
  if (!m) throw new Error("Not a unit conversion")
  var value = parseFloat(m[1])
  var source = m[2].toLowerCase().replace(/^°/, "")
  var target = m[3] ? m[3].toLowerCase().replace(/^°/, "") : counterpart(source)
  if (!target) throw new Error("No target unit")
  if (TEMPERATURES[source] && TEMPERATURES[target]) {
    source = TEMPERATURES[source]; target = TEMPERATURES[target]
    var celsius = source === "f" ? (value - 32) * 5 / 9 : source === "k" ? value - 273.15 : value
    if (celsius < -273.15) throw new Error("Below absolute zero")
    var out = target === "f" ? celsius * 9 / 5 + 32 : target === "k" ? celsius + 273.15 : celsius
    return { value: out, unit: "°" + target.toUpperCase() }
  }
  var s = LOOKUP[source], t = LOOKUP[target]
  if (!s || !t) throw new Error("Unknown unit")
  if (s.dimension !== t.dimension) throw new Error("Incompatible dimensions")
  return { value: value * s.factor / t.factor, unit: target }
}

function counterpart(unit) {
  if (TEMPERATURES[unit]) return TEMPERATURE_COUNTERPARTS[TEMPERATURES[unit]] || ""
  return LOOKUP[unit] ? LOOKUP[unit].counterpart : ""
}

// True for anything that looks like "<time> <zone...>", "10 in <zone>",
// "now in <zone>" or "<zone> time". Deliberately loose: a false positive
// costs one helper run per distinct query, a false negative hides the answer.
function isTimeQuery(text) {
  var t = String(text || "")
  if (NOW_RE.test(t) || ZONE_TIME_RE.test(t) || BARE_HOUR_RE.test(t)) return true
  var undated = t.replace(DATE_PREFIX_RE, "")
  var m = TIME_TOKEN_RE.exec(undated)
  return !!m && undated.slice(m[0].length).trim().length > 0
}

function detailFor(unit) {
  return ["gal", "gallon", "gallons", "kb", "mb", "gb"].indexOf(unit) !== -1
    ? "US liquid gallons · decimal KB/MB/GB" : "Unit conversion"
}

function formatValue(value) {
  var n = Number(Number(value).toPrecision(10))
  return String(n)
}
