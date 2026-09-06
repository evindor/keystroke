.pragma library

// Spoken commands. Two layers, both host-owned:
//
// 1. normalize(): what the transcript becomes as a query. Whisper writes
//    prose ("Launch Chrome."), the matcher wants terms ("chrome"): trailing
//    punctuation goes, so does a leading launcher verb ("open", "go to") and
//    the little words that never name anything ("the", "please"). Whatever
//    survives is AND-ed by the fuzzy matcher as usual.
//
// 2. The catalog and the request for a local llama-server (Gemma 4 E2B in
//    the reference setup). The system prompt lists every row the palette
//    could activate, numbered; the model answers with one number or NONE,
//    constrained by a grammar so nothing else can come back. The system
//    prompt is built deterministically from the catalog so llama-server's
//    prefix cache serves it: only the few tokens of the spoken command are
//    processed per request, which is what makes an answer take ~0.15 s.

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

// One line per row, short enough to keep the prompt small and stable:
// "12. Google Chrome — Web Browser". Details are cut at DETAIL_MAX so an
// app with a paragraph for a comment does not blow up the prompt.
var DETAIL_MAX = 48

function detailOf(item) {
  var d = String(item.detail || "").replace(/\s+/g, " ").trim()
  if (d.length > DETAIL_MAX) d = d.slice(0, DETAIL_MAX - 1).replace(/\s+\S*$/, "") + "…"
  return d
}

function catalogText(items) {
  var lines = []
  for (var i = 0; i < items.length; i++) {
    var d = detailOf(items[i])
    lines.push((i + 1) + ". " + String(items[i].title || "").replace(/\s+/g, " ").trim() + (d ? " — " + d : ""))
  }
  return lines.join("\n")
}

var RULES = [
  "You route spoken commands from a desktop command palette to one item of the catalog below.",
  "Answer with the item number only. If nothing fits, answer NONE.",
  "The command was transcribed from speech, so expect small errors: match by meaning and by sound (\"Krum\" is Chrome, \"luck the screen\" is lock the screen).",
  "\"open\", \"launch\", \"start\" and a name mean the application or menu entry with that name.",
  "\"settings\", \"preferences\" or \"options\" for something mean its settings entry.",
  "Requests about the screen, power, sound, network, display or the desktop mean the matching action or system entry.",
  "Never invent an item that is not listed."
].join("\n")

function systemPrompt(items) {
  return RULES + "\n\nCatalog:\n" + catalogText(items)
}

// Up to four digits: catalogs are a few hundred rows, never ten thousand.
var GRAMMAR = 'root ::= ("NONE" | [1-9] [0-9]{0,3})'

function requestBody(items, transcript) {
  return {
    model: "keystroke",
    temperature: 0,
    max_tokens: 6,
    cache_prompt: true,
    chat_template_kwargs: { enable_thinking: false },
    grammar: GRAMMAR,
    messages: [
      { role: "system", content: systemPrompt(items) },
      { role: "user", content: String(transcript || "").trim() }
    ]
  }
}

// Same system prompt, throwaway user turn: processing it once puts the
// catalog in llama-server's prefix cache before the first real command.
function warmBody(items) {
  var body = requestBody(items, "warm up")
  body.max_tokens = 1
  return body
}

// { index: 1-based row number or 0, none: true when the model said NONE }.
// Anything unparseable counts as no answer.
function parseAnswer(responseText, count) {
  var content = ""
  try {
    var data = JSON.parse(String(responseText || ""))
    var choice = data && data.choices && data.choices[0]
    content = choice && choice.message ? String(choice.message.content || "") : ""
  } catch (e) { return { index: 0, none: false } }
  var t = content.trim()
  if (/^NONE\b/i.test(t)) return { index: 0, none: true }
  var m = /^(\d{1,4})\b/.exec(t)
  var n = m ? Number(m[1]) : 0
  if (!(n >= 1 && n <= count)) return { index: 0, none: false }
  return { index: n, none: false }
}

// Cheap stamp for "did the catalog change": length plus a rolling hash of
// the titles, enough to decide whether to warm the cache again.
function stamp(items) {
  var h = 5381
  for (var i = 0; i < items.length; i++) {
    var s = String(items[i].title || "") + "|" + String(items[i].detail || "")
    for (var j = 0; j < s.length; j++) h = ((h * 33) ^ s.charCodeAt(j)) | 0
  }
  return items.length + ":" + (h >>> 0).toString(16)
}
