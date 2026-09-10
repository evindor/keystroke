import QtQuick
import QtTest
import "../core/Commands.js" as Commands

TestCase {
    name: "Commands"

    property var translate: ({ id: "translate", prefix: "tr", title: "Translate", summary: "Translate text into your target languages",
                               args: [{ name: "to", hint: "a language code or name", optional: true }, { name: "text", hint: "what to translate", rest: true }],
                               examples: ["tr bonjour", "tr fr good morning"] })
    property var timer: ({ id: "timer", prefix: "timer", title: "Set a timer", summary: "Countdown with a notification",
                           args: [{ name: "duration", hint: "10m, 1h30m or minutes" }, { name: "name", hint: "a label", optional: true, rest: true }],
                           examples: ["timer 10m tea"] })
    property var emoji: ({ id: "emoji", prefix: ":", title: "Emoji", summary: "Find an emoji by name", args: [{ name: "feeling", hint: "smile, cat, party", rest: true }], examples: [":smile"] })
    property var help: ({ id: "help", prefix: "/", title: "What can I type?", summary: "Every command", args: [{ name: "command", hint: "filter", optional: true, rest: true }] })

    function compiled(c) { return Commands.compile([c]).commands[0] }
    function index(overrides) {
        var o = overrides || {}
        return Commands.buildIndex([
            { key: "commands", name: "Commands", commands: [compiled(help)] },
            { key: "emoji", name: "Emoji Picker", icon: "☺", commands: [compiled(emoji)], override: o.emoji },
            { key: "timer", name: "Timer", commands: [compiled(timer)], override: o.timer },
            { key: "translate", name: "Translate", iconSource: "file:///icon.svg", commands: [compiled(translate)], override: o.translate }
        ])
    }

    function test_compile_normalises_and_reports() {
        var c = Commands.compile([translate, emoji,
            { id: "nope" },                                        // no prefix
            { prefix: "two words", title: "Bad" },                  // whitespace
            { prefix: "x", title: "Untitled" }.title ? { prefix: "x" } : null,   // no title
            { prefix: "r", title: "Rest first", args: [{ name: "a", rest: true }, { name: "b" }] },
            { prefix: "n", title: "Nameless", args: [{ hint: "x" }] },
            "junk",
            { prefix: "ok", title: "Fine", args: [{ name: "one two", hint: 12 }], examples: ["", "e1", "e2", "e3", "e4", "e5"] }
        ])
        compare(c.commands.map(function(x) { return x.id }), ["translate", "emoji", "ok"])
        compare(c.commands[0].sigil, false)
        compare(c.commands[1].sigil, true)
        compare(c.commands[0].args.length, 2)
        compare(c.commands[0].args[0], { name: "to", hint: "a language code or name", optional: true, rest: false })
        compare(c.commands[2].args[0].name, "one-two")
        compare(c.commands[2].examples, ["e1", "e2", "e3", "e4"])
        compare(c.errors.length, 6)
        verify(c.errors[0].indexOf("nope: prefix") === 0, c.errors[0])
        verify(c.errors[3].indexOf("only the last argument") > 0, c.errors[3])
        verify(c.errors[4].indexOf("argument 0 needs a name") > 0, c.errors[4])
        compare(Commands.compile(undefined).commands, [])
        compare(Commands.compile("x").errors, ["commands must be an array"])
        var many = []
        for (var i = 0; i < 12; i++) many.push({ prefix: "p" + i, title: "P" + i })
        compare(Commands.compile(many).commands.length, Commands.MAX_COMMANDS)
    }

    function test_prefix_rules() {
        compare(Commands.cleanPrefix(" TR "), "tr")
        compare(Commands.cleanPrefix("~"), "~")
        compare(Commands.cleanPrefix("::"), "::")
        compare(Commands.cleanPrefix("t r"), "")
        compare(Commands.cleanPrefix("-x"), "")
        compare(Commands.cleanPrefix("abcdefghijklmnopq"), "")
        compare(Commands.cleanPrefix(""), "")
        compare(Commands.isSigil("/"), true)
        compare(Commands.isSigil("tr"), false)
        compare(Commands.isSigil("a:"), false)
        var s = Commands.prefixSchema([compiled(translate)])
        compare(s.key, "prefix"); compare(s.type, "string"); compare(s["default"], "tr")
        compare(Commands.effective(compiled(translate), "xl", 0).prefix, "xl")
        compare(Commands.effective(compiled(translate), "bad prefix", 0).prefix, "tr")
        compare(Commands.effective(compiled(translate), "xl", 1).prefix, "tr")     // only the first command is renamed
        compare(Commands.effective(compiled(emoji), "e", 0).sigil, false)
    }

    function test_usage_and_typed() {
        compare(Commands.usage(compiled(translate)), "tr [to] <text>")
        compare(Commands.usage(compiled(timer)), "timer <duration> [name]")
        compare(Commands.usage(compiled(emoji)), ":<feeling>")
        compare(Commands.usage(compiled({ prefix: "ext", title: "Extensions" })), "ext")
        compare(Commands.typed(compiled(translate)), "tr ")
        compare(Commands.typed(compiled(emoji)), ":")
    }

    function test_index_and_conflicts() {
        var ix = index()
        compare(ix.items.map(function(i) { return i.command.prefix }), ["/", ":", "timer", "tr"])
        compare(ix.conflicts, [])
        var renamed = index({ timer: "tr" })
        compare(renamed.items.map(function(i) { return i.command.prefix }), ["/", ":", "tr"])
        compare(renamed.items[2].key, "timer")
        compare(renamed.conflicts, [{ key: "translate", prefix: "tr", with: "timer" }])
        compare(index({ emoji: "em" }).items[1].command.sigil, false)
    }

    function test_match() {
        var items = index().items
        var m = Commands.match(items, "tr hello world")
        compare(m.key, "translate"); compare(m.prefix, "tr"); compare(m.rest, "hello world"); compare(m.exclusive, true)
        compare(Commands.match(items, "TR Hello").rest, "Hello")
        compare(Commands.match(items, "tr").rest, "")
        compare(Commands.match(items, "tr ").rest, "")
        compare(Commands.match(items, "tr  two").rest, " two")
        compare(Commands.match(items, "trap"), null)
        compare(Commands.match(items, "  timer 10m tea").rest, "10m tea")
        compare(Commands.match(items, ":smile").key, "emoji")
        compare(Commands.match(items, ":smile").rest, "smile")
        compare(Commands.match(items, ":smile").exclusive, true)
        compare(Commands.match(items, ":").rest, "")
        compare(Commands.match(items, "/").key, "commands")
        compare(Commands.match(items, "/tr").rest, "tr")
        compare(Commands.match(items, "chrome"), null)
        compare(Commands.match(items, ""), null)
        compare(Commands.match([], "tr x"), null)
        // The longest prefix wins when one is a prefix of another.
        var both = Commands.buildIndex([{ key: "a", name: "A", commands: [compiled({ prefix: "t", title: "T" })] }, { key: "b", name: "B", commands: [compiled({ prefix: "tr", title: "TR" })] }]).items
        compare(Commands.match(both, "tr x").key, "b")
        compare(Commands.match(both, "t x").key, "a")
    }

    function test_placeholders_follow_the_caret() {
        var tr = compiled(translate)
        compare(Commands.placeholders(tr, ""), { ghost: "[to] <text>", index: 0, arg: tr.args[0] })
        compare(Commands.placeholders(tr, "fr").ghost, " <text>")
        compare(Commands.placeholders(tr, "fr").index, 0)
        compare(Commands.placeholders(tr, "fr ").ghost, "<text>")
        compare(Commands.placeholders(tr, "fr ").index, 1)
        compare(Commands.placeholders(tr, "fr hello").ghost, "")
        compare(Commands.placeholders(tr, "fr hello").index, 1)
        compare(Commands.placeholders(tr, "fr hello world ").ghost, "")     // the rest argument swallows everything
        compare(Commands.placeholders(tr, "fr hello world ").index, 1)
        var tm = compiled(timer)
        compare(Commands.placeholders(tm, "10m").ghost, " [name]")
        compare(Commands.placeholders(tm, "10m tea").ghost, "")
        var em = compiled(emoji)
        compare(Commands.placeholders(em, "").ghost, "<feeling>")
        compare(Commands.placeholders(em, "smi").ghost, "")
        var bare = compiled({ prefix: "ext", title: "Extensions" })
        compare(Commands.placeholders(bare, ""), { ghost: "", index: -1, arg: null })
        var three = compiled({ prefix: "x", title: "X", args: [{ name: "a" }, { name: "b" }, { name: "c" }] })
        compare(Commands.placeholders(three, "1 2 ").ghost, "<c>")
        compare(Commands.placeholders(three, "1 2 3").ghost, "")
        compare(Commands.placeholders(three, "1 2 3 4").index, -1)
    }

    function test_ghost_text_for_the_field() {
        var items = index().items
        compare(Commands.ghost(Commands.match(items, "tr"), "tr"), " [to] <text>")
        compare(Commands.ghost(Commands.match(items, "tr "), "tr "), "[to] <text>")
        compare(Commands.ghost(Commands.match(items, "tr fr"), "tr fr"), " <text>")
        compare(Commands.ghost(Commands.match(items, ":"), ":"), "<feeling>")
        compare(Commands.ghost(Commands.match(items, "tr fr hello"), "tr fr hello"), "")
        compare(Commands.ghost(null, "x"), "")
    }

    function test_hint_line() {
        var items = index().items
        compare(Commands.hintLine(Commands.match(items, "tr")), "Translate · to: a language code or name (optional)")
        compare(Commands.hintLine(Commands.match(items, "tr fr ")), "Translate · text: what to translate")
        compare(Commands.hintLine(Commands.match(items, "tr fr hello")), "Translate · text: what to translate")
        compare(Commands.hintLine(Commands.match(items, "timer 10m tea")), "Set a timer · name: a label (optional)")
        compare(Commands.hintLine(Commands.match(items, ":")), "Emoji · feeling: smile, cat, party")
        compare(Commands.hintLine(null), "")
        var bare = Commands.buildIndex([{ key: "e", name: "E", commands: [compiled({ prefix: "ext", title: "Extensions", summary: "Turn them on" })] }]).items
        compare(Commands.hintLine(Commands.match(bare, "ext")), "Extensions · Turn them on")
    }

    function test_rows() {
        var items = index().items
        var help = Commands.helpRows(items, "")
        compare(help.map(function(r) { return r.title }), ["Emoji", "Set a timer", "Translate"])   // "/" itself is not listed
        compare(help[2].subtitle, "tr [to] <text> · Translate text into your target languages")
        compare(help[2].accessory, "tr")
        compare(help[2].action, { type: "query", text: "tr " })
        compare(help[0].action, { type: "query", text: ":" })
        compare(help[2].iconSource, "file:///icon.svg")
        verify(help[0].score > help[1].score)
        compare(Commands.helpRows(items, "tr")[0].score, undefined)   // the matcher ranks a filtered list
        var suggest = Commands.suggestRows(items, "trans")
        compare(suggest.length, 1)
        compare(suggest[0].title, "Translate")
        compare(suggest[0].hint, "tab types tr")
        verify(suggest[0].score > 0)
        compare(Commands.suggestRows(items, "").length, 0)
        compare(Commands.suggestRows(items, "zzzz").length, 0)
        compare(Commands.suggestRows(items, "emoji")[0].action.text, ":")
    }

    function test_usage_rows_and_notice() {
        var rows = Commands.usageRows([compiled(translate)], "", "settings/translate")
        compare(rows.map(function(r) { return r.id }), ["usage/translate", "usage/translate/arg/to", "usage/translate/arg/text", "usage/translate/example/0", "usage/translate/example/1", "usage/prefix"])
        compare(rows[0].title, "tr [to] <text>")
        compare(rows[0].action, { type: "query", text: "tr " })
        compare(rows[1].title, "[to]  a language code or name")
        compare(rows[1].subtitle, "Optional")
        compare(rows[2].title, "<text>  what to translate")
        compare(rows[2].subtitle, "Required · the rest of the line")
        verify(rows[1].disabled && rows[2].disabled)
        compare(rows[3].title, "tr bonjour")
        compare(rows[3].verb, "Try")
        compare(rows[3].action, { type: "query", text: "tr bonjour" })
        compare(rows[5].accessory, "tr")
        compare(rows[5].action, { type: "navigate", scope: "settings/translate/prefix", title: "Prefix" })
        var off = Commands.usageRows([compiled(translate)], "xl", "")
        compare(off[0].title, "xl [to] <text>")
        compare(off[0].action.text, "xl ")
        verify(off[5].disabled)
        compare(Commands.usageRows([], "", "settings/x"), [])
        compare(Commands.enabledNotice("Translate", [compiled(translate)], ""), "Translate is on · type tr [to] <text>, or find it by name")
        compare(Commands.enabledNotice("Plain", [], ""), "Plain is on")
    }
}
