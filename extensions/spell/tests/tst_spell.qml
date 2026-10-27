import QtQuick
import QtTest
import "../core/Spell.js" as Spell

TestCase {
    name: "Spell"

    // A tiny hand-verifiable dictionary, in the shipped file's shape, with
    // the interesting lines for the parse in it: a BOM, a duplicate, an
    // apostrophe word, a hyphen, garbage and an over-long word.
    readonly property string fixture: [
        "\uFEFFthe 500",
        "them 400",
        "there 300",
        "these 200",
        "they 100",
        "hello 100",
        "hello 40",           // repeated, keeps the higher frequency
        "hello2 60",          // a digit; normalizes into hello
        "help 90",
        "held 80",
        "an 60",
        "and 50",
        "a 70",
        "don't 40",
        "can\u2019t 30",      // a curly apostrophe
        "e-mail 45",
        "baggage 150",
        "badge 140",
        "bandage 130",
        "",                   // blank line
        "word",               // no frequency
        "=~ 5",               // nothing but noise
        "supercalifragilisticexpialidocious 5"   // longer than the cap
    ].join("\n")
    readonly property var dict: Spell.parseDictionary(fixture)

    function test_parse_cleans_the_file() {
        compare(dict.words.length, 17)   // hello2 normalizes into hello, as does the second hello
        verify(dict.index["the"] !== undefined)          // the BOM did not cling to "the"
        verify(dict.index["don't"] !== undefined)
        verify(dict.index["can't"] !== undefined)        // the curly apostrophe became ASCII
        verify(dict.index["email"] !== undefined)
        verify(dict.index["hello"] !== undefined)
        compare(dict.freqs[dict.index["hello"]], 100)    // the duplicate kept its higher frequency
        verify(dict.index["supercalif"] === undefined)   // over the length cap, dropped as a whole
        verify(dict.index["=~"] === undefined)
    }

    function test_normalize() {
        compare(Spell.normalize("The"), "the")
        compare(Spell.normalize("  HELLO\u00A0 "), "hello")   // punctuation noise is dropped
        compare(Spell.normalize("hello2"), "hello")
        compare(Spell.normalize("don\u2019t"), "don't")
        compare(Spell.normalize("don''t"), "don't")
        compare(Spell.normalize("e-mail"), "email")
        compare(Spell.normalize("'the'"), "the")
        compare(Spell.normalize("123 ;;;"), "")
        // letters survive, digits are dropped, then the length cap lands
        compare(Spell.normalize("abcdefghijklmnopqrstuvwxyz0123456789").length, 26)
    }

    function test_parse_takes_the_first_token() {
        compare(Spell.parse("tresspass").word, "tresspass")
        compare(Spell.parse("tresspass extra words").raw, "tresspass")
        compare(Spell.parse("  Tresspass! ").word, "tresspass")
        compare(Spell.parse(""), null)
        compare(Spell.parse("   "), null)
    }

    function test_membership() {
        verify(Spell.isKnown(dict, "the"))
        verify(Spell.isKnown(dict, "THE"))
        verify(Spell.isKnown(dict, "don't"))
        verify(Spell.isKnown(dict, "don\u2019t"))   // membership goes through the same normalize
        verify(!Spell.isKnown(dict, "ther"))
        verify(!Spell.isKnown(null, "the"))
    }

    function test_distance() {
        compare(Spell.distance("", "", 2), 0)
        compare(Spell.distance("", "a", 2), 1)
        compare(Spell.distance("a", "b", 2), 1)
        compare(Spell.distance("hello", "hello", 2), 0)
        compare(Spell.distance("ab", "ba", 2), 1)          // a transposition counts as one
        compare(Spell.distance("helo", "hello", 2), 1)
        compare(Spell.distance("the", "th", 2), 1)
        compare(Spell.distance("kitten", "sitting", 5), 3) // past the cap it is measured exactly
        verify(Spell.distance("abc", "xyz", 2) > 2)        // early exit, reported as too far
        verify(Spell.distance("hello", "help", 2) === 2)
    }

    function test_suggestions_rank_by_distance_then_frequency() {
        // helo: hello at distance 1 (frequency 100), help 1 (90), held 1 (80)
        var s = Spell.suggest(dict, "helo", 8)
        compare(s.map(function(x) { return x.word }), ["hello", "help", "held"])
        // two suggestions only when the caller asks for two
        compare(Spell.suggest(dict, "helo", 2).length, 2)
        // ab: a at 1 (70), an at 1 (60), and at 2 (50)
        compare(Spell.suggest(dict, "ab", 8).map(function(x) { return x.word }), ["a", "an", "and"])
    }

    function test_head_typos_still_find_their_target() {
        // gello: the first letter is wrong, the second still matches hello's
        compare(Spell.suggest(dict, "gello", 8)[0].word, "hello")
        // elllo: a doubled head letter
        compare(Spell.suggest(dict, "elllo", 8)[0].word, "hello")
        // ello: the first letter was dropped; the query opens hello's second
        // letter bucket
        compare(Spell.suggest(dict, "ello", 8).map(function(x) { return x.word }), ["hello"])
    }

    function test_suggestions_are_deterministic_and_bounded() {
        var s = Spell.suggest(dict, "helo", 8)
        compare(Spell.suggest(dict, "helo", 8).map(function(x) { return x.word }), s.map(function(x) { return x.word }))
        compare(Spell.suggest(dict, "qxyz", 8), [])
        compare(Spell.suggest(dict, "", 8), [])
        compare(Spell.suggest(null, "helo", 8), [])
        // at most MAX_RESULTS rows, ever
        compare(Spell.suggest(dict, "ab", 2).length, 2)
    }

    function test_transport() {
        compare(Spell.splitStatus("BODY\n__STATUS__200"), { status: 200, body: "BODY" })
        compare(Spell.splitStatus("BODY\n__STATUS__503"), { status: 503, body: "BODY" })
        compare(Spell.splitStatus("BODY"), { status: 0, body: "BODY" })
        compare(Spell.splitStatus("BODY\n__STATUS__junk"), { status: 0, body: "BODY" })
        var argv = Spell.requestArgv("tresspass")
        compare(argv[0], "curl")
        verify(argv.indexOf("--max-time") >= 0)
        verify(argv[argv.length - 1].indexOf("sp=tresspass") > 0)   // literal argv, the word is one element
        verify(argv[argv.length - 1].indexOf("max=8") > 0)
        compare(argv[argv.length - 1].slice(0, 7), "https:/")
    }

    function test_parse_suggestions() {
        var body = '[{"word":"trespass","score":9},{"word":"press pass"},{"word":"trespasser"},{"word":""},{"word":"trespass"}]'
        compare(Spell.parseSuggestions(body, 8), ["trespass", "trespasser"])   // phrases and dupes drop
        compare(Spell.parseSuggestions(body, 1), ["trespass"])
        compare(Spell.parseSuggestions("[]", 8), [])           // an empty answer is valid
        compare(Spell.parseSuggestions('[{"word":""}]', 8), [])
        compare(Spell.parseSuggestions('{"bad":true}', 8), null)
        compare(Spell.parseSuggestions("not json", 8), null)
        compare(Spell.parseSuggestions("", 8), null)
    }

    function test_rows() {
        var key = "spell"
        // no word yet: a single hint row
        var hint = Spell.rows({ key: key, word: "", prefix: "ck" })
        compare(hint.length, 1)
        compare(hint[0].title, "Type a word to check")
        verify(hint[0].disabled)
        compare(hint[0].action, { type: "noop" })

        // spelled correctly: one row, the check mark, copy and paste
        var ans = Spell.rows({ key: key, word: "the", exact: true })
        compare(ans.length, 1)
        compare(ans[0].title, "the")
        compare(ans[0].accessory, Spell.CHECK)
        compare(ans[0].tier, "answer")
        compare(ans[0].action, { type: "copy", text: "the" })
        compare(ans[0].altAction, { type: "paste", text: "the" })

        // a misspelling: the network words first, capped, never the word itself,
        // every row with copy on Enter and paste on Ctrl+Enter
        var rows = Spell.rows({ key: key, word: "helo", raw: "helo", local: [{ word: "an" }],
                                net: { words: ["help", "helo", "held", "hello"] } })
        compare(rows.map(function(r) { return r.id }), [key + "/sug/help", key + "/sug/held", key + "/sug/hello"])
        compare(rows[0].accessory, Spell.SUGGESTED)      // the small label beside the top-ranked suggestion
        verify(!("accessory" in rows[1]))
        verify(!("accessory" in rows[2]))
        verify(rows.every(function(r) { return r.tier === "answer" }))
        verify(rows.every(function(r) { return r.action.type === "copy" && r.altAction.type === "paste" }))

        // pending: the local list answers, no failure row yet
        rows = Spell.rows({ key: key, word: "helo", local: [{ word: "hello" }, { word: "help" }], net: { pending: true } })
        compare(rows.length, 2)

        // no network result and nothing local: the word itself is still copied
        rows = Spell.rows({ key: key, word: "khx", raw: "khx", local: [], net: { pending: true } })
        compare(rows.length, 1)
        compare(rows[0].id, key + "/raw")
        compare(rows[0].title, "khx")

        // the offline list answered alone and the service said why
        rows = Spell.rows({ key: key, word: "helo", local: [{ word: "hello" }, { word: "help" }], net: { failed: true } })
        compare(rows.length, 3)
        compare(rows[2].id, key + "/status")
        verify(rows[2].disabled)
        rows = Spell.rows({ key: key, word: "helo", local: [{ word: "hello" }], net: { blocked: true } })
        verify(rows[1].title.indexOf("paused") > 0)

        // online off: no status row is ever added
        rows = Spell.rows({ key: key, word: "helo", local: [{ word: "hello" }], net: null })
        compare(rows.length, 1)

        // more than MAX_RESULTS suggestions are capped at eight
        var twelve = []
        for (var i = 0; i < 12; i++) twelve.push("w" + i)
        rows = Spell.rows({ key: key, word: "w", local: [], net: { words: twelve } })
        compare(rows.length, 8)
    }

    function test_real_dictionary() {
        var text = ""
        var xhr = new XMLHttpRequest()
        xhr.open("GET", "../assets/" + Spell.DICTIONARY_FILE)
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) text = xhr.responseText
        }
        xhr.send()
        for (var i = 0; i < 100 && !text; i++) wait(10)
        if (!text) skip("the dictionary file could not be read from the tests directory")
        var t0 = Date.now()
        var state = Spell.parseDictionary(text)
        console.info("parsed", state.words.length, "words in", (Date.now() - t0) + "ms")
        verify(state.words.length > 80000)
        verify(Spell.isKnown(state, "the"))
        verify(Spell.isKnown(state, "trespass"))
        var top = Spell.suggest(state, "tresspass", 8)
        verify(top.length >= 1)
        compare(top[0].word, "trespass")
        compare(top[0].distance, 1)
    }
}
