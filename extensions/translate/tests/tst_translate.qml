import QtQuick
import QtTest
import "../core/Translate.js" as T
import "Fixtures.js" as F

TestCase {
    name: "Translate"
    property var settings: T.defaults()
    property var targets: ["en", "fr"]

    // A cache stand-in: keys are from|to|text.
    function cacheOf(entries) {
        var c = {}
        for (var k in entries) c[k] = entries[k]
        return { lookup: function(text, from, to) { return c[T.cacheKey(text, from, to)] }, busy: function() { return false }, put: function(text, from, to, v) { c[T.cacheKey(text, from, to)] = v } }
    }
    function ctxFor(query, cache, extra) {
        var ctx = { query: query, scope: "", key: "translate", iconSource: "file:///icon.svg", settings: settings, targets: targets, matched: true,
                    selection: "", canSpeak: false, now: 1000, blockedUntil: 0, lookup: cache.lookup, busy: cache.busy }
        for (var k in (extra || {})) ctx[k] = extra[k]
        return ctx
    }
    function ids(rows) { return rows.map(function(r) { return r.id }) }

    function test_languages() {
        compare(T.resolve("fr"), "fr")
        compare(T.resolve("French"), "fr")
        compare(T.resolve("ua"), "uk")
        compare(T.resolve("chinese"), "zh-CN")
        compare(T.resolve("zh-cn"), "zh-CN")
        compare(T.resolve("Chinese (Traditional)"), "zh-TW")
        compare(T.resolve("portuguese"), "pt")
        compare(T.resolve("hebrew"), "iw")
        compare(T.resolve("klingon"), "")
        compare(T.resolve("auto"), "auto")
        compare(T.languageName("uk"), "Ukrainian")
        compare(T.languageName("auto"), "Detected")
        compare(T.languageName("xx"), "xx")
        compare(T.resolveTarget("it"), "")           // an English word, not Italian
        compare(T.resolveTarget("italian"), "it")
        compare(T.resolveTarget("auto"), "")
        compare(T.targetList("en,fr"), ["en", "fr"])
        compare(T.targetList("ua; French, en, en, bogus"), ["uk", "fr", "en"])
        compare(T.targetList(""), ["en"])
        compare(T.targetList("a,b,c,d,e,f,g,h").length <= T.MAX_TARGETS, true)
        compare(T.sourceCode({ source: "auto" }), "auto")
        compare(T.sourceCode({ source: "uk" }), "uk")
        compare(T.sourceCode({}), "auto")
    }

    function test_query_grammar() {
        compare(T.parse("tr bonjour", false), { text: "bonjour", to: "", explicit: false, prefixed: true, natural: false })
        compare(T.parse("Translate bonjour le monde", false).text, "bonjour le monde")
        compare(T.parse("tr fr good morning", false), { text: "good morning", to: "fr", explicit: true, prefixed: true, natural: false })
        compare(T.parse("tr french good morning", false).to, "fr")
        compare(T.parse("tr it is raining", false), { text: "it is raining", to: "", explicit: false, prefixed: true, natural: false })
        compare(T.parse("bonjour to english", false), { text: "bonjour", to: "en", explicit: true, prefixed: false, natural: true })
        compare(T.parse("how are you in Spanish", false), { text: "how are you", to: "es", explicit: true, prefixed: false, natural: true })
        compare(T.parse("tr bonjour to german", false), { text: "bonjour", to: "de", explicit: true, prefixed: true, natural: true })
        compare(T.parse("go to bed", false), null)          // "bed" is not a language
        compare(T.parse("log in it", false), null)          // an ambiguous code is not a target
        compare(T.parse("chrome", false), null)
        compare(T.parse("tr", false), { text: "", to: "", explicit: false, prefixed: true, natural: false })
        compare(T.parse("trap", false), null)
        compare(T.parse("", false), null)
        compare(T.parse("good morning", true), { text: "good morning", to: "", explicit: false, prefixed: false, natural: false })
        compare(T.parse("fr good morning", true).to, "fr")
        compare(T.parse("tr " + new Array(6000).join("x"), false).text.length, T.MAX_CHARS)
        compare(T.retryQuery("tr helo wrld", T.parse("tr helo wrld", false), "hello world"), "tr hello world")
        compare(T.retryQuery("translate fr helo", T.parse("translate fr helo", false), "hello"), "translate fr hello")
        compare(T.retryQuery("helo to french", T.parse("helo to french", false), "hello"), "hello to fr")
        compare(T.retryQuery("helo", T.parse("helo", true), "hello"), "hello")
        // The host stripped the prefix: the rest parses as prefixed text, and the retry keeps the user's prefix.
        compare(T.parse("fr good morning", false, true), { text: "good morning", to: "fr", explicit: true, prefixed: true, natural: false })
        compare(T.parse("", false, true), { text: "", to: "", explicit: false, prefixed: true, natural: false })
        compare(T.parse("bonjour to german", false, true).natural, true)
        compare(T.retryQuery("xl helo", T.parse("helo", false, true), "hello", "xl"), "xl hello")
    }

    function test_patterns_are_linear_and_match_the_examples() {
        for (var i = 0; i < T.PATTERNS.length; i++) {
            var p = T.PATTERNS[i], re = new RegExp(p.regex, p.flags || "")
            verify(p.regex.length < 400, p.id + " is short")
            verify(re.test(p.example), p.id + " matches its example")
        }
        compare(T.PATTERNS.length, 1)   // the prefix is a declared command in extension.json, recognised by the host
        var target = new RegExp(T.PATTERNS[0].regex, "i")
        verify(target.test("bonjour to english") && target.test("hi in fr") && !target.test("to english") && !target.test("bonjour to"))
    }

    function test_request_argv() {
        var argv = T.requestArgv("hello world", "auto", "fr", "")
        compare(argv[0], "curl")
        compare(argv.indexOf("--proxy"), -1)
        var url = argv[argv.length - 1]
        verify(url.indexOf("https://translate.google.com/translate_a/single?client=dict-chrome-ex&sl=auto&tl=fr&hl=fr&") === 0, url)
        verify(url.indexOf("&q=hello%20world") > 0, "text is percent-encoded")
        verify(url.indexOf("dt=bd") < 0, "no dictionary for a phrase")
        verify(url.indexOf("tk=") < 0, "no token")
        verify(T.requestArgv("hello", "auto", "es", "")[6].indexOf("&dt=bd") > 0, "dictionary for a single word")
        var proxied = T.requestArgv("x&y=1", "en", "de", "http://proxy:8080")
        compare(proxied.indexOf("--proxy"), 6)
        compare(proxied[7], "http://proxy:8080")
        verify(proxied[proxied.length - 1].indexOf("&q=x%26y%3D1") > 0, "ampersands in the text stay in the text")
        var longText = new Array(120).join("The quick brown fox jumps over the lazy dog. ")
        var post = T.requestArgv(longText, "auto", "de", "")
        compare(post[post.length - 3], "--data-urlencode")
        compare(post[post.length - 2], "q=" + longText)
        verify(post[post.length - 1].indexOf("&q=") < 0, "long text goes in the body, not the URL")
        compare(T.splitStatus("[[[\"x\"]]]\n__STATUS__200"), { status: 200, body: "[[[\"x\"]]]" })
        compare(T.splitStatus("\n__STATUS__429"), { status: 429, body: "" })
        compare(T.splitStatus(""), { status: 0, body: "" })
    }

    function test_parse_responses() {
        var brief = T.parseResponse(F.SHORT)
        compare(brief.text, "Bonjour le monde")
        compare(brief.source, "en")
        compare(brief.confirmed, "en")
        compare(brief.pronunciation, "")
        compare(brief.dictionary, [])
        compare(brief.correction, null)
        var ja = T.parseResponse(F.JAPANESE)
        compare(ja.text, "おはよう")
        compare(ja.pronunciation, "Ohayō")
        compare(ja.sourcePhonetic, "ˌɡo͝od ˈmôrniNG")
        var word = T.parseResponse(F.WORD)
        compare(word.text, "Hola")
        compare(word.dictionary[0].pos, "interjección")
        compare(word.dictionary[0].terms[0], "¡Hola!")
        verify(word.dictionary[0].terms.length <= 6)
        verify(T.dictionarySummary(word.dictionary).indexOf("interjección: ¡Hola!, ¡Caramba!") === 0)
        var typo = T.parseResponse(F.TYPO)
        compare(typo.correction, { text: "hello world", auto: false })
        var auto = T.parseResponse(F.AUTOCORRECT)
        compare(auto.correction, { text: "I received the package tomorrow", auto: true })
        compare(T.parseResponse(F.SAMELANG).text, "hello there")
        var uk = T.parseResponse(F.UKRAINIAN)
        compare(uk.text, "Good day")
        compare(uk.source, "uk")
        compare(uk.sourcePhonetic, "Dobryy denʹ")
        compare(T.parseResponse(F.MULTI).text, "Hallo. Wie geht es dir heute? Mir geht's gut.")
        var long = T.parseResponse(F.LONG)
        verify(long.text.indexOf("Der schnelle Braunfuchs") === 0 && long.text.length > 2000, "segments are joined in order")
        compare(T.parseResponse(F.RATE_LIMITED), null)
        compare(T.parseResponse("{}"), null)
        compare(T.parseResponse("[null]"), null)
        compare(T.parseResponse("[[[null,\"x\"]]]"), null)
        compare(T.parseResponse(""), null)
    }

    function test_needed_follows_the_detected_language() {
        var c = cacheOf({})
        var subject = { text: "hello there", from: "auto", to: "" }
        compare(ids(T.needed(subject, targets, settings, c.lookup, false)), ["autoenhello there"].map(function(k) { return k }).length === 1 ? [undefined] : [undefined])
        var first = T.needed(subject, targets, settings, c.lookup, false)
        compare(first.length, 1)
        compare(first[0].to, "en")
        // English typed against an English first target: the answer moves to French, then a reverse check.
        c.put("hello there", "auto", "en", T.parseResponse(F.SAMELANG))
        var second = T.needed(subject, targets, settings, c.lookup, false)
        compare(second.map(function(r) { return r.from + ">" + r.to }), ["auto>en", "auto>fr"])
        c.put("hello there", "auto", "fr", { text: "salut", source: "en", pronunciation: "", dictionary: [], correction: null })
        var third = T.needed(subject, targets, settings, c.lookup, false)
        compare(third.map(function(r) { return r.from + ">" + r.to + ":" + r.text }), ["auto>en:hello there", "auto>fr:hello there", "fr>en:salut"])
        // Minimal (a selection job) stops at the main translation.
        compare(T.needed(subject, targets, settings, c.lookup, true).length, 2)
        // An explicit target is the only one, plus the reverse.
        c.put("hello there", "auto", "de", { text: "hallo", source: "en", pronunciation: "", dictionary: [], correction: null })
        compare(T.needed({ text: "hello there", from: "auto", to: "de" }, targets, settings, c.lookup, false).map(function(r) { return r.from + ">" + r.to }), ["auto>de", "de>en"])
        // Too short: nothing.
        compare(T.needed({ text: "h", from: "auto", to: "" }, targets, settings, c.lookup, false), [])
        // An error on the first request stops the chain.
        var e = cacheOf({}); e.put("boom", "auto", "en", { error: "x", at: 0 })
        compare(T.needed({ text: "boom", from: "auto", to: "" }, targets, settings, e.lookup, false).length, 1)
    }

    function test_ordering_and_fallback() {
        compare(T.orderTargets(["en", "fr", "de"], "fr", false), ["en", "fr", "de"])
        compare(T.orderTargets(["en", "fr", "de"], "fr", true), ["en", "de", "fr"])
        compare(T.orderTargets(["en", "fr"], "", true), ["en", "fr"])
        compare(T.primaryTarget(["en", "fr"], "en"), "fr")
        compare(T.primaryTarget(["en", "fr"], "de"), "en")
        compare(T.primaryTarget(["en"], "en"), "en")
    }

    function test_resolve_subject_and_view_blocks() {
        var c = cacheOf({})
        c.put("Добрий день", "auto", "en", T.parseResponse(F.UKRAINIAN))
        c.put("Добрий день", "auto", "fr", { text: "Bonjour", source: "uk", pronunciation: "", dictionary: [], correction: null })
        c.put("Good day", "en", "uk", { text: "Гарного дня", source: "en", pronunciation: "Harnoho dnya", dictionary: [], correction: null })
        var v = T.resolveSubject({ text: "Добрий день", from: "auto", to: "" }, targets, settings, c.lookup, c.busy)
        compare(v.detected, "uk")
        compare(v.main.to, "en")
        compare(v.main.text, "Good day")
        compare(v.reverse.text, "Гарного дня")
        compare(v.extras.map(function(x) { return x.to + ":" + x.text }), ["fr:Bonjour"])
        var blocks = T.viewBlocks(v)
        compare(blocks.map(function(b) { return b.label }), ["English", "French", "Back to Ukrainian"])
        compare(blocks[2].pronunciation, "Harnoho dnya")
        // The language typed is echoed in the editor only, last when prioritised.
        var e = cacheOf({})
        e.put("hello there", "auto", "en", T.parseResponse(F.SAMELANG))
        e.put("hello there", "auto", "fr", { text: "salut", source: "en", pronunciation: "", dictionary: [], correction: null })
        e.put("hello there", "auto", "de", { text: "hallo", source: "en", pronunciation: "", dictionary: [], correction: null })
        e.put("salut", "fr", "en", { text: "hi", source: "fr", pronunciation: "", dictionary: [], correction: null })
        var three = ["en", "fr", "de"]
        var plain = T.resolveSubject({ text: "hello there", from: "auto", to: "" }, three, settings, e.lookup, e.busy)
        compare(plain.main.to, "fr")
        compare(T.viewBlocks(plain).map(function(b) { return b.label }), ["French", "English", "German", "Back to English"])
        var prioritised = T.resolveSubject({ text: "hello there", from: "auto", to: "" }, three, { prioritizeCrossLanguage: true }, e.lookup, e.busy)
        compare(T.viewBlocks(prioritised).map(function(b) { return b.label }), ["French", "German", "English", "Back to English"])
        compare(ids(T.rows(ctxFor("tr hello there", e, { targets: three }))), ["translate/main", "translate/reverse", "translate/extra/de", "translate/editor", "translate/web"])
        // Nothing cached yet: the main slot is pending.
        var empty = T.resolveSubject({ text: "Добрий день", from: "auto", to: "" }, targets, settings, cacheOf({}).lookup, function() { return true })
        verify(empty.main.pending && !empty.main.text)
        compare(T.viewBlocks(empty).length, 2)
        verify(T.viewBlocks(empty)[0].pending)
    }

    function test_rows_at_the_root() {
        var c = cacheOf({})
        var empty = T.rows(ctxFor("", c, { matched: false }))
        compare(ids(empty), ["open"])
        compare(empty[0].action, { type: "navigate", scope: "translate", title: "Translate" })
        compare(empty[0].iconSource, "file:///icon.svg")
        var withSelection = T.rows(ctxFor("", c, { matched: false, selection: "bonjour tout le monde" }))
        compare(ids(withSelection), ["open", "selection/view"])
        compare(withSelection[1].action, { type: "translate-view", text: "bonjour tout le monde", to: "" })
        compare(withSelection[1].altAction, { type: "translate-selection", text: "bonjour tout le monde", paste: false })
        // No pattern matched, not scoped: never answer.
        compare(T.rows(ctxFor("chrome", c, { matched: false })), [])
        compare(T.rows(ctxFor("tr bonjour", c, { matched: false })), [])
        // "tr" alone offers the selection and a hint.
        compare(ids(T.rows(ctxFor("tr", c, { selection: "salut" }))), ["selection/view", "selection/copy", "selection/paste", "hint"])
        compare(ids(T.rows(ctxFor("tr b", c))), ["hint"])
        // Nothing cached: a stable placeholder row.
        var pending = T.rows(ctxFor("tr bonjour", c))
        compare(ids(pending), ["translate/main"])
        compare(pending[0].title, "Translating…")
        verify(pending[0].disabled)
        // Rate-limited: one disabled answer.
        var blocked = T.rows(ctxFor("tr bonjour", c, { blockedUntil: 61000 }))
        compare(blocked[0].title, "Too many requests")
        verify(blocked[0].subtitle.indexOf("60 s") > 0)
    }

    function test_rows_with_answers() {
        var c = cacheOf({})
        c.put("hello world", "auto", "en", { text: "hello world", source: "en", pronunciation: "", dictionary: [], correction: null })
        c.put("hello world", "auto", "fr", T.parseResponse(F.SHORT))
        c.put("Bonjour le monde", "fr", "en", { text: "Hello World", source: "fr", pronunciation: "", dictionary: [], correction: null })
        var rows = T.rows(ctxFor("tr hello world", c))
        compare(ids(rows), ["translate/main", "translate/reverse", "translate/editor", "translate/web"])
        var main = rows[0]
        compare(main.title, "Bonjour le monde")
        compare(main.subtitle, "English → French")
        compare(main.tier, "answer")
        compare(main.verb, "Copy")
        compare(main.action, { type: "copy", text: "Bonjour le monde" })
        compare(main.altAction.type, "exec")
        compare(main.altAction.argv[main.altAction.argv.length - 1], "Bonjour le monde")
        compare(main.previewLabel, "FRENCH")
        compare(main.section, "Translate")
        compare(rows[1].title, "Hello World")
        compare(rows[1].subtitle.indexOf("Back to English"), 0)
        compare(rows[2].action, { type: "translate-view", text: "hello world", to: "" })
        compare(rows[3].action.type, "url")
        verify(rows[3].action.url.indexOf("https://translate.google.com/?sl=auto&tl=fr&text=hello%20world") === 0)
        // Paste as the default action swaps the effects.
        var pasted = T.rows(ctxFor("tr hello world", c, { settings: { targets: "en,fr", source: "auto", defaultAction: "paste" } }))[0]
        compare(pasted.verb, "Paste")
        compare(pasted.action.type, "exec")
        compare(pasted.altAction, { type: "copy", text: "Bonjour le monde" })
        // Speak appears only when asked for and mpv is there.
        var speak = T.rows(ctxFor("tr hello world", c, { canSpeak: true, settings: { targets: "en,fr", source: "auto", defaultAction: "copy", speak: true } }))
        verify(ids(speak).indexOf("translate/speak") >= 0)
        var s = speak.filter(function(r) { return r.id === "translate/speak" })[0]
        compare(s.action.argv.slice(0, 4), ["mpv", "--no-video", "--really-quiet", "--"])
        verify(s.action.argv[4].indexOf("https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=fr&q=Bonjour%20le%20monde") === 0)
        compare(ids(T.rows(ctxFor("tr hello world", c, { canSpeak: false, settings: { targets: "en,fr", source: "auto", defaultAction: "copy", speak: true } }))).indexOf("translate/speak"), -1)
        // A third target shows up as an extra row; the echo of the detected language never does.
        c.put("hello world", "auto", "de", { text: "Hallo Welt", source: "en", pronunciation: "", dictionary: [], correction: null })
        var three = T.rows(ctxFor("tr hello world", c, { targets: ["en", "fr", "de"] }))
        compare(ids(three), ["translate/main", "translate/reverse", "translate/extra/de", "translate/editor", "translate/web"])
        compare(three[2].title, "Hallo Welt")
        // An explicit target: only that one, plus the reverse.
        var explicit = T.rows(ctxFor("tr de hello world", c))
        compare(ids(explicit), ["translate/main", "translate/editor", "translate/web"])   // no reverse cached yet
        compare(explicit[0].title, "Hallo Welt")
        compare(explicit[0].subtitle, "English → German")
    }

    function test_rows_with_a_correction_and_dictionary() {
        var c = cacheOf({})
        c.put("helo wrld", "auto", "en", T.parseResponse(F.TYPO))
        var rows = T.rows(ctxFor("tr helo wrld", c))
        var correction = rows.filter(function(r) { return r.id === "translate/correction" })[0]
        compare(correction.title, "Did you mean: hello world")
        compare(correction.action, { type: "translate-retry", query: "tr hello world", text: "hello world" })
        var d = cacheOf({})
        d.put("hello", "auto", "en", { text: "hello", source: "en", pronunciation: "", dictionary: [], correction: null })
        d.put("hello", "auto", "fr", T.parseResponse(F.WORD))
        var main = T.rows(ctxFor("tr hello", d))[0]
        compare(main.title, "Hola")
        verify(main.previewDetail.indexOf("interjección: ¡Hola!") === 0)
    }

    function test_rows_in_scope_and_picker() {
        var c = cacheOf({})
        var scoped = T.rows(ctxFor("", c, { scope: "translate", matched: false, selection: "salut" }))
        compare(ids(scoped), ["selection/view", "selection/copy", "selection/paste", "hint", "targets"])
        compare(scoped[4].action, { type: "navigate", scope: "translate/targets", title: "Target languages" })
        compare(scoped[2].action, { type: "translate-selection", text: "salut", paste: true })
        // In scope the text needs no prefix and no pattern.
        compare(ids(T.rows(ctxFor("bonjour", c, { scope: "translate", matched: false }))), ["translate/main"])
        compare(T.rows(ctxFor("x", c, { scope: "other" })), [])
        var picker = T.rows(ctxFor("", c, { scope: "translate/targets" }))
        compare(picker.length, 249)
        compare(picker[0].title, "English")
        compare(picker[0].accessory, "✓")
        compare(picker[0].verb, "Remove")
        compare(picker[0].action, { type: "setting", path: ["providers", "translate"], key: "targets", value: "fr", schema: T.SETTINGS[0] })
        compare(picker[1].title, "French")
        verify(picker[0].score > picker[1].score && picker[1].score > picker[2].score)
        var german = picker.filter(function(r) { return r.id === "lang/de" })[0]
        compare(german.verb, "Add")
        compare(german.action.value, "en,fr,de")
        verify(german.keywords.indexOf("de") === 0)
        var ukrainian = picker.filter(function(r) { return r.id === "lang/uk" })[0]
        verify(ukrainian.keywords.indexOf("ua") > 0, "aliases are searchable: " + ukrainian.keywords)
        // Searching leaves the score to the host's matcher.
        compare(T.rows(ctxFor("germ", c, { scope: "translate/targets" }))[0].score, undefined)
        // The last target cannot be removed; a sixth cannot be added.
        var only = T.rows(ctxFor("", c, { scope: "translate/targets", targets: ["en"] }))[0]
        verify(only.disabled && only.action.type === "noop")
        var full = T.rows(ctxFor("", c, { scope: "translate/targets", targets: ["en", "fr", "de", "es", "it", "pt"] }))
        verify(full.filter(function(r) { return r.id === "lang/uk" })[0].disabled)
    }

    function test_effects_keep_user_text_out_of_command_strings() {
        var text = "$(rm -rf ~) `x` \"quoted\" & done"
        var argv = T.pasteArgv(text)
        compare(argv[0], "sh")
        compare(argv[1], "-c")
        verify(argv[2].indexOf(text) < 0, "the command string is a constant")
        compare(argv[argv.length - 1], text)
        compare(T.copyEffect(text), { type: "copy", text: text })
        verify(T.webUrl("a b&c", "auto", "fr").indexOf("text=a%20b%26c") > 0)
        compare(T.ttsUrl(new Array(400).join("x"), "fr").length < 300, true)
        compare(T.primaryEffects("x", { defaultAction: "copy" }).verb, "Copy")
        compare(T.primaryEffects("x", { defaultAction: "paste" }).verb, "Paste")
        compare(T.ellipsis("  a   very long   line of text  ", 12), "a very long…")
    }

    function test_settings_schema_is_complete() {
        var keys = T.SETTINGS.map(function(s) { return s.key })
        compare(keys, ["targets", "source", "defaultAction", "prioritizeCrossLanguage", "selection", "speak", "proxy"])
        for (var i = 0; i < T.SETTINGS.length; i++) {
            var s = T.SETTINGS[i]
            verify(s.label && s.type && s["default"] !== undefined, s.key + " is complete")
            if (s.type === "enum") verify(s.options.indexOf(s["default"]) >= 0, s.key + " default is an option")
        }
        compare(T.defaults().targets, "en,fr")
        verify(keys.indexOf("enabled") < 0, "enabled is the host's")
    }
}
