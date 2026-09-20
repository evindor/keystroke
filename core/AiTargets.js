.pragma library

// Hand a prompt to an assistant without the clipboard. Every link below was
// verified on 2026-09-06 (Omarchy 4.0.2) by opening it and reading the window:
//
//   claude-desktop 1.40609.1   claude://claude.ai/new?q=<prompt>&surface=chat
//                              opens a new chat with the prompt in the composer.
//                              It is the link Anthropic's own GNOME search
//                              provider builds (resources/gnome-search-provider/
//                              searchProvider.js, LaunchSearch). The app rejects
//                              a q that starts with "/" (slash commands), so a
//                              leading slash is padded with a space.
//                              claude://code/new?q=<prompt> starts a Claude Code
//                              session the same way.
//   openai-codex-desktop       The Linux "ChatGPT" app is the Codex app.
//   26.901                     codex://threads/new?prompt=<prompt> opens a new
//                              Codex thread in the current project with the
//                              prompt in the composer. It is the link OpenAI's
//                              own login page uses. Handing it a chatgpt.com URL
//                              only opens a signed-out tab in its embedded
//                              browser, so browser mode uses the real browser.
//   chatgpt.com                ?prompt= prefills; ?q= sends immediately.
//   claude.ai                  /new?q= prefills; there is no auto-send form.
//   cursor 3.21.9              cursor://anysphere.cursor-deeplink/prompt?text=
//                              prefills the composer; the app never sends it
//                              (Cursor's deeplink reference, limit 10,000 chars).
//                              &workspace= is not in that reference; it is kept
//                              because the contributor saw 3.21.9 honour it.
//                              Open with `cursor --open-url` when the binary is
//                              on PATH, otherwise xdg-open via the scheme handler.
//   agent (Cursor CLI)         positional prompt; --workspace <path> before it
//                              (Cursor CLI parameter reference). The name is
//                              generic, so detection also checks that the binary
//                              resolves inside a cursor install.
//
// Nothing here runs at query time except string building; activation is always
// an explicit Enter.

var MAX_PROMPT = 2000

// A leading "/" is padded because Claude's URL validator refuses it; a leading
// "-" because the CLIs would parse a one-word prompt such as "-p" or "--yolo"
// as an option. The prompt is otherwise passed through untouched.
function clip(prompt) {
  var text = String(prompt === undefined || prompt === null ? "" : prompt).trim().slice(0, MAX_PROMPT)
  var first = text.charAt(0)
  return first === "/" || first === "-" ? " " + text : text
}

function encode(prompt) { return encodeURIComponent(clip(prompt)) }

function claudeDesktopUrl(prompt) { return "claude://claude.ai/new?q=" + encode(prompt) + "&surface=chat" }
function claudeCodeUrl(prompt) { return "claude://code/new?q=" + encode(prompt) }
function codexDesktopUrl(prompt) { return "codex://threads/new?prompt=" + encode(prompt) }
function claudeWebUrl(prompt) { return "https://claude.ai/new?q=" + encode(prompt) }
function chatgptWebUrl(prompt, autoSend) { return "https://chatgpt.com/?" + (autoSend ? "q=" : "prompt=") + encode(prompt) }
function googleUrl(query) { return "https://www.google.com/search?q=" + encodeURIComponent(String(query || "").trim()).replace(/%20/g, "+") }

function folderOf(workspace) { return workspace === undefined || workspace === null ? "" : String(workspace).trim() }

function cursorPromptUrl(prompt, workspace) {
  var folder = folderOf(workspace)
  return "cursor://anysphere.cursor-deeplink/prompt?text=" + encode(prompt) + (folder ? "&workspace=" + encodeURIComponent(folder) : "")
}

// Prefer the app's own launcher when it is on PATH (the scheme handler may not
// be registered in mimeapps.list); otherwise let xdg-open resolve the scheme.
// `args` go between the binary and the URL (Cursor wants --open-url).
function openLink(bin, url, available, args) {
  return available && available[bin] ? { type: "exec", argv: [bin].concat(args || [], [url]) } : { type: "url", url: url }
}

// One row plan per assistant. `available` maps binary name -> true for
// claude-desktop, chatgpt (Codex app), claude (CLI) and codex (CLI).
function plan(assistant, mode, autoSend, available, prompt) {
  var avail = available || {}
  var claude = assistant === "claude"
  if (mode === "cli") {
    var cli = claude ? "claude" : "codex"
    if (avail[cli])
      return { id: assistant, target: cli + "-cli", title: claude ? "Ask Claude Code" : "Ask Codex",
               subtitle: "Terminal · new " + cli + " session with your prompt", verb: "Open terminal",
               effect: { type: "exec", argv: ["omarchy-launch-terminal", cli, clip(prompt)] } }
  }
  if (mode === "desktop") {
    if (claude && avail["claude-desktop"])
      return { id: assistant, target: "claude-desktop", title: "Ask Claude",
               subtitle: "Claude desktop · new chat, prompt ready to send", verb: "Open Claude",
               effect: openLink("claude-desktop", claudeDesktopUrl(prompt), avail) }
    if (!claude && avail["chatgpt"])
      return { id: assistant, target: "codex-desktop", title: "Ask Codex",
               subtitle: "Codex desktop · new thread, prompt ready to send", verb: "Open Codex",
               effect: openLink("chatgpt", codexDesktopUrl(prompt), avail) }
  }
  var why = mode === "browser" ? "" : (mode === "cli" ? " · CLI not installed" : " · desktop app not installed")
  if (claude)
    return { id: assistant, target: "claude-web", title: "Ask Claude",
             subtitle: "claude.ai · prompt ready to send" + why, verb: "Open Claude",
             effect: { type: "url", url: claudeWebUrl(prompt) } }
  return { id: assistant, target: "chatgpt-web", title: "Ask ChatGPT",
           subtitle: "chatgpt.com · " + (autoSend ? "sends your prompt" : "prompt ready to send") + why, verb: "Open ChatGPT",
           effect: { type: "url", url: chatgptWebUrl(prompt, autoSend) } }
}

// Cursor CLI (`agent`) and Cursor desktop (`cursor --open-url` deeplink).
// `available` maps agent, cursor -> true when detected. Cursor has no web
// composer, so this is the one plan that can be null: nothing installed.
function cursorPlan(mode, available, prompt, workspace) {
  var avail = available || {}
  var folder = folderOf(workspace)
  if (mode === "cli" && avail.agent) {
    var argv = ["omarchy-launch-terminal", "agent"]
    if (folder) argv.push("--workspace", folder)
    argv.push(clip(prompt))
    return { id: "cursor", target: "cursor-agent-cli", title: "Ask Cursor Agent",
             subtitle: "Terminal · agent with your prompt", verb: "Open terminal",
             effect: { type: "exec", argv: argv } }
  }
  if (avail.cursor) {
    var why = mode === "cli" ? " · CLI not installed" : (mode === "browser" ? " · no browser hand-off" : "")
    return { id: "cursor", target: "cursor-desktop", title: "Ask Cursor",
             subtitle: "Cursor · prompt ready in the composer" + why, verb: "Open Cursor",
             effect: openLink("cursor", cursorPromptUrl(prompt, folder), avail, ["--open-url"]) }
  }
  return null
}

var ASSISTANTS = ["chatgpt", "claude", "cursor"]
var ICONS = { google: "󰊭", chatgpt: "󰭹", claude: "󰛄", cursor: "󰨞" }

// The preferred assistant first, then the others in their fixed order; an
// unknown preference means the default.
function order(preferred) {
  var first = ASSISTANTS.indexOf(preferred) >= 0 ? preferred : ASSISTANTS[0]
  return [first].concat(ASSISTANTS.filter(function(a) { return a !== first }))
}

// The "Continue with" rows for one query: Google, then every assistant that
// has a plan. Scores keep the preferred one first and every assistant above
// Google (2); the ranking stays within the fallback tier.
function rows(settings, available, prompt) {
  var s = settings || {}
  var out = [{ id: "google", title: "Search Google", subtitle: prompt, icon: ICONS.google, section: "Continue with",
               verb: "Search", tier: "fallback", score: 2, action: { type: "url", url: googleUrl(prompt) } }]
  var seq = order(s.provider)
  for (var i = 0; i < seq.length; i++) {
    var a = seq[i]
    var p = a === "cursor" ? cursorPlan(s.mode, available, prompt, s.cursorWorkspace)
                           : plan(a, a === "chatgpt" ? "browser" : s.mode, s.autoSend === true, available, prompt)
    if (!p) continue
    out.push({ id: p.id, title: p.title, subtitle: p.subtitle, icon: ICONS[a], section: "Continue with",
               verb: p.verb, tier: "fallback", score: 3 - i * 0.25, action: p.effect,
               preview: prompt, previewLabel: "PROMPT", previewDetail: "Opens with this prompt in the composer" })
  }
  return out
}
