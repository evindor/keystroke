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
//                              prefills the composer (optional &workspace=).
//                              Open with `cursor --open-url` when the binary is
//                              on PATH, otherwise xdg-open via the scheme handler.
//   agent (cursor-agent)       positional prompt; optional --workspace before
//                              the prompt (verified with agent --help).
//
// Nothing here runs at query time except string building; activation is always
// an explicit Enter.

var MAX_PROMPT = 2000

function clip(prompt) {
  var text = String(prompt === undefined || prompt === null ? "" : prompt).trim().slice(0, MAX_PROMPT)
  return text.charAt(0) === "/" ? " " + text : text
}

function encode(prompt) { return encodeURIComponent(clip(prompt)) }

function claudeDesktopUrl(prompt) { return "claude://claude.ai/new?q=" + encode(prompt) + "&surface=chat" }
function claudeCodeUrl(prompt) { return "claude://code/new?q=" + encode(prompt) }
function codexDesktopUrl(prompt) { return "codex://threads/new?prompt=" + encode(prompt) }
function claudeWebUrl(prompt) { return "https://claude.ai/new?q=" + encode(prompt) }
function chatgptWebUrl(prompt, autoSend) { return "https://chatgpt.com/?" + (autoSend ? "q=" : "prompt=") + encode(prompt) }
function googleUrl(query) { return "https://www.google.com/search?q=" + encodeURIComponent(String(query || "").trim()).replace(/%20/g, "+") }

function cursorPromptUrl(prompt, workspace) {
  var params = "text=" + encode(prompt)
  var folder = workspace === undefined || workspace === null ? "" : String(workspace).trim()
  if (folder) params += "&workspace=" + encodeURIComponent(folder)
  return "cursor://anysphere.cursor-deeplink/prompt?" + params
}

function cursorOpenEffect(url, available) {
  return available && available.cursor ? { type: "exec", argv: ["cursor", "--open-url", url] } : { type: "url", url: url }
}

// Prefer the app's own launcher when it is on PATH (the scheme handler may not
// be registered in mimeapps.list); otherwise let xdg-open resolve the scheme.
function openLink(bin, url, available) {
  return available && available[bin] ? { type: "exec", argv: [bin, url] } : { type: "url", url: url }
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

// Cursor Agent CLI (`agent`) and Cursor desktop (`cursor --open-url` deeplink).
// `available` maps agent, cursor -> true when detected on PATH.
function cursorPlan(mode, available, prompt, workspace) {
  var avail = available || {}
  var folder = workspace === undefined || workspace === null ? "" : String(workspace).trim()
  if (mode === "cli") {
    if (avail.agent) {
      var argv = ["omarchy-launch-terminal", "agent"]
      if (folder) argv.push("--workspace", folder)
      argv.push(clip(prompt))
      return { id: "cursor", target: "cursor-agent-cli", title: "Ask Cursor Agent",
               subtitle: "Terminal · agent with your prompt", verb: "Open terminal",
               effect: { type: "exec", argv: argv } }
    }
  }
  if (mode === "desktop" || mode === "browser" || mode === "cli") {
    if (avail.cursor) {
      var why = mode === "cli" ? " · CLI not installed" : (mode === "browser" ? " · no browser hand-off" : "")
      return { id: "cursor", target: "cursor-desktop", title: "Ask Cursor",
               subtitle: "Cursor · prompt ready in the composer" + why, verb: "Open Cursor",
               effect: cursorOpenEffect(cursorPromptUrl(prompt, folder), avail) }
    }
  }
  return null
}
