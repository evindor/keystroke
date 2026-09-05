from urllib.parse import quote_plus
from flint.api import row, command


def ai_action(provider, mode, query):
    if mode == "cli":
        # Prompts are literal argv, never interpolated shell code.
        return command("omarchy-launch-terminal", "codex" if provider == "chatgpt" else "claude", "--", query)
    if mode == "browser":
        # Explicit activation opens a new conversation; the prompt is copied
        # for review rather than relying on an undocumented auto-send URL.
        launch = {"type": "url", "url": "https://chatgpt.com/" if provider == "chatgpt" else "https://claude.ai/new"}
    else:
        launch = (command("chatgpt") if provider == "chatgpt" else
                  command("claude-desktop", "claude://claude.ai/new?surface=chat&source=desktop_action"))
    return {"type": "compound", "actions": [{"type": "copy", "text": query}, launch]}


async def query(ctx):
    if ctx.scope or not ctx.query.strip():
        return []
    q, mode = ctx.query.strip(), ctx.settings["mode"]
    results = [row("google", "Search Google", q, "󰊭", score=2, section="Continue with", verb="Search",
                   action={"type": "url", "url": "https://www.google.com/search?q=" + quote_plus(q)})]
    for provider, name, icon in [("chatgpt", "ChatGPT", "󰭹"), ("claude", "Claude", "󰛄")]:
        subtitle = ("New CLI session · prompt passed as an argument" if mode == "cli" else
                    ("Desktop app" if mode == "desktop" else "Browser") + " · prompt copied, paste to start")
        if provider == "chatgpt" and mode == "desktop":
            subtitle = "Desktop app · prompt copied; choose New chat and paste"
        results.append(row(provider, "Start a new chat in " + name, subtitle, icon,
            score=3 if provider == ctx.settings["provider"] else 2, section="Continue with",
            action=ai_action(provider, mode, q), verb="Open " + name))
    return results
