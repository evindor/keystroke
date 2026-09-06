.pragma library

// Speech normalization applies only to local search, never AI prompts or clipboard.
var VERB = /^(?:please\s+)?(?:can you\s+|could you\s+)?(?:launch|open up|open|run|start|go to|goto|show me|show|find|search for|search|look up|toggle|turn on|turn off|switch to|switch)\s+/i
var STOP = { the: true, a: true, an: true, my: true, please: true, up: true }
var TRAIL = /[\s.,!?;:…]+$/
var LEAD = /^[\s.,!?;:…"'“”‘’]+/

function normalize(transcript) {
  var t = String(transcript || "").replace(/\s+/g, " ").trim().replace(TRAIL, "").replace(LEAD, "")
  if (!t) return ""
  var verbless = t.replace(VERB, "")
  var words = verbless.split(" ").filter(function(w) { return w && !STOP[w.toLowerCase().replace(TRAIL, "")] })
  var out = words.join(" ").replace(TRAIL, "").trim()
  return out || t
}
