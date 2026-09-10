import QtQuick
import QtTest
import "../core/Timer.js" as TimerModel

TestCase {
    name: "Timer"
    property var settings: ({ defaultMinutes: 5, notify: true })
    property double now: new Date(2026, 8, 6, 14, 0, 0).getTime()

    function test_durations() {
        compare(TimerModel.parse("timer 10m tea", 5), { seconds: 600, label: "tea", prefixed: true })
        compare(TimerModel.parse("Timer 1h30m", 5).seconds, 5400)
        compare(TimerModel.parse("timer 1h 30m 15s", 5).seconds, 5415)
        compare(TimerModel.parse("timer 90", 5).seconds, 5400)
        compare(TimerModel.parse("timer 1.5h", 5).seconds, 5400)
        compare(TimerModel.parse("timer 0:45", 5).seconds, 45)
        compare(TimerModel.parse("timer 1:30:00 bread", 5), { seconds: 5400, label: "bread", prefixed: true })
        compare(TimerModel.parse("countdown 2 minutes", 5).seconds, 120)
        compare(TimerModel.parse("remind me in 20 min stand up", 5), { seconds: 1200, label: "stand up", prefixed: true })
        compare(TimerModel.parse("timer tea", 7), { seconds: 420, label: "tea", prefixed: true, defaulted: true })
        compare(TimerModel.parse("timer", 5).seconds, 300)
        compare(TimerModel.parse("timer 10 years", 5), { seconds: 600, label: "years", prefixed: true })   // a bare number is minutes; the rest is the label
        compare(TimerModel.parse("timer 10000h", 5), null)   // more than a week is refused
    }

    function test_unprefixed_queries_need_a_unit() {
        compare(TimerModel.parse("10 min tea", 5), { seconds: 600, label: "tea", prefixed: false })
        compare(TimerModel.parse("45s", 5).seconds, 45)
        compare(TimerModel.parse("10", 5), null)
        compare(TimerModel.parse("2m in feet", 5), { seconds: 120, label: "in feet", prefixed: false })   // an item row, ranked below the converter's answer
        compare(TimerModel.parse("chrome", 5), null)
        compare(TimerModel.parse("", 5), null)
        compare(TimerModel.parse("sqrt(144)", 5), null)
    }

    function test_formatting() {
        compare(TimerModel.describe(5415), "1 h 30 min 15 s")
        compare(TimerModel.describe(600), "10 min")
        compare(TimerModel.describe(0), "0 s")
        compare(TimerModel.countdown(59.2), "1:00")
        compare(TimerModel.countdown(3661), "1:01:01")
        compare(TimerModel.endsAt(now, 600), "14:10")
    }

    function test_rows_at_the_root_and_in_scope() {
        var key = "timer"
        var empty = TimerModel.rows("", [], settings, now, false, key)
        compare(empty.length, 1)
        compare(empty[0].title, "Timers")
        compare(empty[0].action, { type: "navigate", scope: key, title: "Timers" })

        var start = TimerModel.rows("timer 10m tea", [], settings, now, false, key)
        compare(start[0].title, "Start a 10 min timer: tea")
        compare(start[0].tier, "answer")
        compare(start[0].action, { type: "timer-start", seconds: 600, label: "tea" })
        compare(start[0].subtitle, "Ends at 14:10")
        compare(TimerModel.rows("10m tea", [], settings, now, false, key)[0].tier, "item")
        compare(TimerModel.rows("chrome", [], settings, now, false, key).length, 0)

        var t = TimerModel.make(600, "tea", now - 60000)
        var running = TimerModel.rows("", [t], settings, now, true, key)
        compare(running.length, 1)
        compare(running[0].title, "tea")
        compare(running[0].accessory, "9:00")
        compare(running[0].action, { type: "timer-cancel", id: t.id })
        verify(running[0].confirm.indexOf("Cancel the tea timer") === 0)
        var root = TimerModel.rows("", [t], settings, now, false, key)
        compare(root.map(function(r) { return r.id }), ["running/" + t.id, "open"])
        compare(root[1].accessory, "1")
        var hint = TimerModel.rows("", [], settings, now, true, key)
        compare(hint[0].title, "No timers running")
        verify(hint[0].disabled)
    }
}
