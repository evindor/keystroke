import QtQuick
import QtTest
import "../core/Intent.js" as Intent
import "../core/Match.js" as Match

TestCase {
    name: "Intent"
    property var items: [
        { title: "Google Chrome", detail: "Web Browser" },
        { title: "Keystroke Settings", detail: "" },
        { title: "Night Light", detail: "Toggle › Display" },
        { title: "Lock Screen", detail: "System" }
    ]

    function test_transcripts_become_matcher_friendly_queries() {
        compare(Intent.normalize("Chrome."), "Chrome")
        compare(Intent.normalize("Launch Chrome."), "Chrome")
        compare(Intent.normalize("open up the settings, please"), "settings")
        compare(Intent.normalize("Turn on night light."), "night light")
        compare(Intent.normalize("Lock the screen!"), "Lock screen")
        compare(Intent.normalize("  Keystroke   settings.  "), "Keystroke settings")
        compare(Intent.normalize("Open."), "Open")          // a verb alone stays a query
        compare(Intent.normalize(""), "")
        compare(Intent.normalize("…"), "")
    }
    function test_normalized_transcripts_reach_the_fuzzy_matcher() {
        verify(Match.match("Chrome.", "Google Chrome", "browser", "", "") === 0)
        verify(Match.match(Intent.normalize("Chrome."), "Google Chrome", "browser", "", "") >= 99)
        verify(Match.match(Intent.normalize("Launch Chrome."), "Google Chrome", "browser", "", "") >= 99)
        verify(Match.match(Intent.normalize("Open Spotify"), "Spotify", "", "", "") >= 100)
    }
    function test_catalog_lines_are_numbered_and_short() {
        var text = Intent.catalogText(items)
        var lines = text.split("\n")
        compare(lines.length, 4)
        compare(lines[0], "1. Google Chrome — Web Browser")
        compare(lines[1], "2. Keystroke Settings")
        var long = Intent.catalogText([{ title: "X", detail: "one two three four five six seven eight nine ten eleven twelve thirteen" }])
        verify(long.length < 70, long)
        verify(long.indexOf("…") > 0)
    }
    function test_request_is_deterministic_and_constrained() {
        var a = Intent.requestBody(items, "launch chrome"), b = Intent.requestBody(items, "night light")
        compare(a.messages[0].content, b.messages[0].content)          // same prefix, cacheable
        compare(a.messages[1].content, "launch chrome")
        compare(a.temperature, 0)
        compare(a.cache_prompt, true)
        compare(a.chat_template_kwargs.enable_thinking, false)
        verify(a.grammar.indexOf("NONE") > 0)
        verify(a.messages[0].content.indexOf("4. Lock Screen — System") > 0)
        var w = Intent.warmBody(items)
        compare(w.messages[0].content, a.messages[0].content)
        compare(w.max_tokens, 1)
    }
    function test_answers_parse_to_a_row_or_nothing() {
        function reply(content) { return JSON.stringify({ choices: [{ message: { role: "assistant", content: content } }] }) }
        compare(Intent.parseAnswer(reply("3"), 4), { index: 3, none: false })
        compare(Intent.parseAnswer(reply(" 1\n"), 4), { index: 1, none: false })
        compare(Intent.parseAnswer(reply("NONE"), 4), { index: 0, none: true })
        compare(Intent.parseAnswer(reply("1 then 2"), 4), { index: 0, none: false })
        compare(Intent.parseAnswer(reply("NONE but 2"), 4), { index: 0, none: false })
        compare(Intent.parseAnswer(reply("01"), 4), { index: 0, none: false })
        compare(Intent.parseAnswer(reply("9"), 4), { index: 0, none: false })     // out of range
        compare(Intent.parseAnswer(reply("Google Chrome"), 4), { index: 0, none: false })
        compare(Intent.parseAnswer("not json", 4), { index: 0, none: false })
        compare(Intent.parseAnswer(JSON.stringify({ choices: [] }), 4), { index: 0, none: false })
    }
    function test_stamp_changes_with_the_catalog() {
        var s = Intent.stamp(items)
        compare(Intent.stamp(items.slice()), s)
        verify(Intent.stamp(items.slice(0, 3)) !== s)
        verify(Intent.stamp(items.concat([{ title: "Slack", detail: "" }])) !== s)
        var renamed = items.slice(); renamed[0] = { title: "Chromium", detail: "Web Browser" }
        verify(Intent.stamp(renamed) !== s)
    }
}
