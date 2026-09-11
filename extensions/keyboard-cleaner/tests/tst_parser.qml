import QtQuick
import QtTest
import "../core/Parser.js" as Parser

TestCase {
    name: "Parser"
    property var settings: ({ defaultSeconds: 30, blockPointer: true })
    property var state: ({ key: "keyboard-cleaner", blockPointer: true })

    function compiled() {
        return Parser.PATTERNS.map(function(p) { return { id: p.id, re: new RegExp(p.regex, p.flags || "") } })
    }
    function matches(text) {
        return compiled().filter(function(p) { return p.re.test(text) }).map(function(p) { return p.id })
    }

    function test_patterns_compile_and_carry_examples_that_match_themselves() {
        for (var i = 0; i < Parser.PATTERNS.length; i++) {
            var p = Parser.PATTERNS[i]
            verify(p.example.length > 0, p.id + " has an example")
            verify(p.boost > 0 && p.boost <= 30, p.id + " boost in range")
            verify(compiled()[i].re.test(p.example), p.id + " example matches its own pattern: " + p.example)
        }
    }

    function test_patterns_recognise_block_shapes() {
        verify(matches("block 30s").indexOf("verb-seconds") >= 0)
        verify(matches("clean 2 minutes").indexOf("verb-minutes") >= 0)
        verify(matches("wash 45 seconds").indexOf("verb-seconds") >= 0)
        verify(matches("block").indexOf("verb-only") >= 0)
        verify(matches("30s").indexOf("bare-seconds") >= 0)
        verify(matches("5m").indexOf("bare-minutes") >= 0)
    }

    function test_patterns_leave_unrelated_queries_alone() {
        var plain = ["firefox", "open settings", "clean the house", "wipe", "readme", "timer 10m tea", "ext", "screenshot", "git status", "hello world", "2m in feet"]
        for (var i = 0; i < plain.length; i++) compare(matches(plain[i]).filter(function(id) { return id.indexOf("bare") !== 0 }), [], plain[i])
    }

    function test_command_rest() {
        compare(Parser.parseCommand("30s", settings), { verb: "wipe", seconds: 30, label: "", defaulted: false, clamped: false })
        compare(Parser.parseCommand("2m touchpad too", settings), { verb: "wipe", seconds: 120, label: "touchpad too", defaulted: false, clamped: false })
        compare(Parser.parseCommand("90", settings).seconds, 90)              // a bare number after the prefix is seconds
        compare(Parser.parseCommand("1m30s", settings).seconds, 90)
        compare(Parser.parseCommand("2 minutes", settings).seconds, 120)
        compare(Parser.parseCommand("", settings), { verb: "wipe", seconds: 30, label: "", defaulted: true, clamped: false })
        compare(Parser.parseCommand("kitchen", settings), { verb: "wipe", seconds: 30, label: "kitchen", defaulted: true, clamped: false })
        compare(Parser.parseCommand("", { defaultSeconds: 45 }).seconds, 45)
        compare(Parser.parseCommand("", {}).seconds, 30)
        compare(Parser.parseCommand("1h", settings), { verb: "wipe", seconds: 300, label: "", defaulted: false, clamped: true })
        compare(Parser.parseCommand("0s", settings).seconds, 1)
    }

    function test_query_verbs() {
        compare(Parser.parseQuery("block 30s", settings), { verb: "block", seconds: 30, label: "", defaulted: false, clamped: false })
        compare(Parser.parseQuery("Clean 2 minutes", settings).seconds, 120)
        compare(Parser.parseQuery("wash 45 seconds keys", settings), { verb: "wash", seconds: 45, label: "keys", defaulted: false, clamped: false })
        compare(Parser.parseQuery("   block   15   m   ", settings), { verb: "block", seconds: 300, label: "", defaulted: false, clamped: true })
        compare(Parser.parseQuery("block", settings), { verb: "block", seconds: 30, label: "", defaulted: true, clamped: false })
        compare(Parser.parseQuery("wipe 30s", settings).seconds, 30)          // older hosts without declared commands
        compare(Parser.parseQuery("clean the house", settings), null)
        compare(Parser.parseQuery("blocker", settings), null)
    }

    function test_query_bare_durations() {
        compare(Parser.parseQuery("30s", settings), { verb: "", seconds: 30, label: "", defaulted: false, clamped: false })
        compare(Parser.parseQuery("5m", settings).seconds, 300)
        compare(Parser.parseQuery("2m in feet", settings), null)
        compare(Parser.parseQuery("30", settings), null)
        compare(Parser.parseQuery("firefox", settings), null)
        compare(Parser.parseQuery("", settings), null)
        compare(Parser.parseQuery("  ", settings), null)
    }

    function test_describe_duration() {
        compare(Parser.describeDuration(30), "30 seconds")
        compare(Parser.describeDuration(1), "1 second")
        compare(Parser.describeDuration(60), "1 minute")
        compare(Parser.describeDuration(90), "1 minute 30 seconds")
        compare(Parser.describeDuration(120), "2 minutes")
        compare(Parser.describeDuration(0), "0 seconds")
        compare(Parser.shortDuration(30), "30s")
        compare(Parser.shortDuration(60), "1m")
        compare(Parser.shortDuration(90), "1m 30s")
        compare(Parser.shortDuration(0), "0s")
    }

    function test_block_argv_is_literal_and_bounded() {
        compare(Parser.blockArgv("/x/bin/keyboard-cleaner", 30, true), ["/x/bin/keyboard-cleaner", "--seconds", "30"])
        compare(Parser.blockArgv("/x/bin/keyboard-cleaner", 30, false), ["/x/bin/keyboard-cleaner", "--seconds", "30", "--keep-pointer"])
        compare(Parser.blockArgv("/x/bin/keyboard-cleaner", 9999, true)[2], "300")
    }

    function test_helper_reports() {
        compare(Parser.parseReport('{"blocked": 3, "devices": ["a"], "seconds": 30, "until": 1789079797.7}'), { blocked: 3, until: 1789079797.7 })
        compare(Parser.parseReport('{"error": "hyprctl is not installed; this extension needs Hyprland"}'), { error: "hyprctl is not installed; this extension needs Hyprland" })
        compare(Parser.parseReport('{"restored": true}'), {})
        compare(Parser.parseReport("Traceback (most recent call last):"), null)
        compare(Parser.parseReport(""), null)
        compare(Parser.parseReport("[1]"), {})
    }

    function test_rows_at_the_root() {
        var viaCommand = Parser.rows("wipe 30s", "30s", false, settings, false, state)
        compare(viaCommand.length, 1)
        compare(viaCommand[0].tier, "answer")
        compare(viaCommand[0].title, "Block input for 30 seconds")
        compare(viaCommand[0].action, { type: "block", seconds: 30, label: "" })
        verify(viaCommand[0].confirm === undefined)

        var alt = Parser.rows("block 2m", null, true, settings, false, state)
        compare(alt.length, 1)
        compare(alt[0].tier, "fallback")
        compare(alt[0].score, 1)
        verify(alt[0].confirm.indexOf("Block input for 2 minutes?") === 0)

        compare(Parser.rows("firefox", null, false, settings, false, state), [])
        var empty = Parser.rows("", null, false, settings, false, state)
        compare(empty.length, 1)
        compare(empty[0].action.type, "navigate")
    }

    function test_rows_on_the_extension_screen() {
        var listing = Parser.rows("", null, false, settings, true, state)
        compare(listing.map(function(r) { return r.action.seconds }), [15, 30, 60])
        verify(listing[0].score > listing[1].score)
        var typed = Parser.rows("45s", null, true, settings, true, state)
        compare(typed[0].action.seconds, 45)
        compare(typed.length, 4)
        verify(typed[1].score === undefined)   // the matcher filters the fixed rows against the query
    }

    function test_row_wording_follows_the_pointer_setting() {
        var keys = Parser.rows("wipe", "", false, settings, false, { key: "keyboard-cleaner", blockPointer: false })
        verify(keys[0].subtitle.indexOf("Disables the keyboard for") === 0)
        verify(keys[0].subtitle.indexOf("default length") > 0)
        var clamped = Parser.rows("wipe 1h", "1h", false, settings, false, state)
        verify(clamped[0].subtitle.indexOf("cut to the 5 minute maximum") > 0)
    }
}
