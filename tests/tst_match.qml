import QtQuick
import QtTest
import "../core/Match.js" as Match
import "../core/Frecency.js" as Frecency

TestCase {
    name: "MatchAndRank"
    function test_word_matching_without_unrelated_fuzzy_results() {
        verify(Match.match("chrome", "Google Chrome") > 100)
        compare(Match.match("chrome", "Chromium"), 0)
        compare(Match.match("chrome", "Keystroke Settings", "preferences configuration"), 0)
        verify(Match.match("chrom", "Google Chrome") > Match.match("chrom", "Default browser", "Chrome"))
        verify(Match.match("chroe", "Google Chrome") > 0)
        compare(Match.match("cme", "Chrome"), 0)
        verify(Match.match("code", "Visual Studio Code") > 0)
        compare(Match.match("", "Anything"), 1)
        compare(Match.match("Calculator", "Calculator"), 120)
    }
    function test_tiers_dominate_scores_and_frecency() {
        var rows = [
            {title: "Search Google", tier: "fallback", score: 999},
            {title: "Google Chrome", tier: "item", score: 50, key: "chrome"},
            {title: "Chromium", tier: "item", score: 60},
            {title: "145", tier: "answer", score: 1}
        ]
        var ranked = Match.rank(rows, function(r) { return r.key === "chrome" ? 36 : 0 })
        compare(ranked.map(function(r) { return r.title }), ["145", "Google Chrome", "Chromium", "Search Google"])
        var unlearned = Match.rank(rows, null)
        compare(unlearned[1].title, "Chromium")
    }
    function test_frecency_halves_in_two_weeks_and_prunes() {
        var now = 1800000000
        var k = Frecency.key("apps", "chrome")
        compare(k.length, 32)
        var entries = Frecency.record({}, k, now)
        entries = Frecency.record(entries, k, now)
        compare(Frecency.weight(entries, k, now), 2)
        fuzzyCompare(Frecency.weight(entries, k, now + Frecency.HALF_LIFE), 1, 1e-9)
        var reparsed = Frecency.parse(Frecency.serialize(entries))
        fuzzyCompare(Frecency.weight(reparsed, k, now + Frecency.HALF_LIFE), 1, 1e-9)
        verify(Frecency.serialize(entries).indexOf("chrome") < 0)
        compare(Frecency.parse("{ broken"), ({}))
        verify(Frecency.bonus(entries, k, now) <= 36)
        compare(Frecency.bonus(entries, "", now), 0)
    }
}
