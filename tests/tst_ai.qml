import QtQuick
import QtTest
import "../core/AiTargets.js" as Ai

TestCase {
    name: "AiTargets"
    property var all: ({ "claude-desktop": true, "chatgpt": true, "claude": true, "codex": true, "cursor": true, "agent": true })

    function test_links_carry_the_prompt() {
        compare(Ai.claudeDesktopUrl("what is 2+2?"), "claude://claude.ai/new?q=what%20is%202%2B2%3F&surface=chat")
        compare(Ai.codexDesktopUrl("fix the bug"), "codex://threads/new?prompt=fix%20the%20bug")
        compare(Ai.claudeWebUrl("hi"), "https://claude.ai/new?q=hi")
        compare(Ai.chatgptWebUrl("hi", false), "https://chatgpt.com/?prompt=hi")
        compare(Ai.chatgptWebUrl("hi", true), "https://chatgpt.com/?q=hi")
        compare(Ai.googleUrl("two words"), "https://www.google.com/search?q=two+words")
    }
    function test_slash_commands_are_padded_and_prompts_bounded() {
        // Claude's URL validator refuses a q that starts with "/".
        compare(Ai.claudeDesktopUrl("/clear"), "claude://claude.ai/new?q=%20%2Fclear&surface=chat")
        var long = new Array(3000).join("a")
        verify(decodeURIComponent(Ai.codexDesktopUrl(long).split("prompt=")[1]).length === Ai.MAX_PROMPT)
    }
    function test_desktop_mode_uses_the_apps_own_launchers() {
        var c = Ai.plan("claude", "desktop", false, all, "hello")
        compare(c.target, "claude-desktop")
        compare(c.effect.type, "exec")
        compare(c.effect.argv[0], "claude-desktop")
        compare(c.effect.argv[1], "claude://claude.ai/new?q=hello&surface=chat")
        var g = Ai.plan("chatgpt", "desktop", false, all, "hello")
        compare(g.title, "Ask Codex")
        compare(g.effect.argv, ["chatgpt", "codex://threads/new?prompt=hello"])
    }
    function test_missing_targets_fall_back_to_the_browser_and_say_so() {
        var c = Ai.plan("claude", "desktop", false, {}, "hello")
        compare(c.target, "claude-web")
        compare(c.effect, { type: "url", url: "https://claude.ai/new?q=hello" })
        verify(c.subtitle.indexOf("not installed") > 0)
        var g = Ai.plan("chatgpt", "cli", true, {}, "hello")
        compare(g.target, "chatgpt-web")
        compare(g.effect.url, "https://chatgpt.com/?q=hello")
        verify(g.subtitle.indexOf("sends your prompt") > 0)
    }
    function test_cli_mode_passes_the_prompt_as_a_literal_argument() {
        var payload = "--help $(touch /tmp/no) `id` \"quoted\""
        var c = Ai.plan("claude", "cli", false, all, payload)
        compare(c.effect.argv, ["omarchy-launch-terminal", "claude", payload])
        compare(Ai.plan("chatgpt", "cli", false, all, "x").effect.argv[1], "codex")
    }
    function test_scheme_handler_fallback_when_binary_missing() {
        compare(Ai.openLink("claude-desktop", "claude://x", {}), { type: "url", url: "claude://x" })
    }
    function test_cursor_desktop_deeplink_carries_prompt_and_workspace() {
        compare(Ai.cursorPromptUrl("fix tests", ""), "cursor://anysphere.cursor-deeplink/prompt?text=fix%20tests")
        compare(Ai.cursorPromptUrl("hi", "/home/x/code"), "cursor://anysphere.cursor-deeplink/prompt?text=hi&workspace=%2Fhome%2Fx%2Fcode")
        var d = Ai.cursorPlan("desktop", all, "hello", "")
        compare(d.target, "cursor-desktop")
        compare(d.effect.argv, ["cursor", "--open-url", "cursor://anysphere.cursor-deeplink/prompt?text=hello"])
    }
    function test_cursor_cli_passes_prompt_and_workspace_as_literal_argv() {
        var payload = "explain $(rm -rf /)"
        var c = Ai.cursorPlan("cli", all, payload, "/tmp/ws")
        compare(c.effect.argv, ["omarchy-launch-terminal", "agent", "--workspace", "/tmp/ws", payload])
        var missing = Ai.cursorPlan("cli", { cursor: true }, "x", "")
        compare(missing.target, "cursor-desktop")
        verify(missing.subtitle.indexOf("CLI not installed") > 0)
    }
}
