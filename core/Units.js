.pragma library

// Unit and temperature conversion in JS. IANA time zones need tzdata, which
// QML's JavaScript engine does not expose, so time queries are gated here
// (isTimeQuery) and resolved by helpers/timezone.py on demand.

var UNITS = [
  [1, "length", "m meter meters metre metres"], [0.01, "length", "cm centimeter centimeters"],
  [0.001, "length", "mm millimeter millimeters"], [1000, "length", "km kilometer kilometers"],
  [0.3048, "length", "ft foot feet"], [0.0254, "length", "in inch inches"],
  [0.9144, "length", "yd yard yards"], [1609.344, "length", "mi mile miles"],
  [1, "mass", "kg kilogram kilograms"], [0.001, "mass", "g gram grams"],
  [0.45359237, "mass", "lb lbs pound pounds"], [0.028349523125, "mass", "oz ounce ounces"],
  [1, "time", "s sec second seconds"], [60, "time", "min minute minutes"],
  [3600, "time", "h hr hour hours"], [86400, "time", "d day days"],
  [1, "volume", "l liter liters litre litres"], [0.001, "volume", "ml milliliter milliliters"],
  [3.785411784, "volume", "gal gallon gallons"],
  [1, "data", "b byte bytes"], [1000, "data", "kb"], [1e6, "data", "mb"], [1e9, "data", "gb"],
  [1024, "data", "kib"], [1048576, "data", "mib"], [1073741824, "data", "gib"],
  [1, "speed", "m/s"], [1 / 3.6, "speed", "km/h kph"], [0.44704, "speed", "mph"]
]
var LOOKUP = {}
for (var u = 0; u < UNITS.length; u++) {
  var aliases = UNITS[u][2].split(" ")
  for (var a = 0; a < aliases.length; a++) LOOKUP[aliases[a]] = { factor: UNITS[u][0], dimension: UNITS[u][1] }
}
var TEMPERATURES = { c: "c", celsius: "c", f: "f", fahrenheit: "f", k: "k", kelvin: "k" }
var UNIT_RE = /^\s*(-?\d+(?:\.\d+)?)\s*([\w\/°]+)\s+(?:in|to)\s+([\w\/°]+)\s*$/i
var TIME_RE = /^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+(?:in|from)\s+(.+?)(?:\s+to\s+(.+?))?(?:\s+on\s+(\d{4}-\d{2}-\d{2}))?\s*$/i

// Returns { value, unit } or throws Error.
function convert(text) {
  var m = UNIT_RE.exec(String(text || ""))
  if (!m) throw new Error("Not a unit conversion")
  var value = parseFloat(m[1])
  var source = m[2].toLowerCase().replace(/^°/, ""), target = m[3].toLowerCase().replace(/^°/, "")
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

function isTimeQuery(text) {
  return TIME_RE.test(String(text || ""))
}

function detailFor(unit) {
  return ["gal", "gallon", "gallons", "kb", "mb", "gb"].indexOf(unit) !== -1
    ? "US liquid gallons · decimal KB/MB/GB" : "Unit conversion"
}

function formatValue(value) {
  var n = Number(Number(value).toPrecision(10))
  return String(n)
}
