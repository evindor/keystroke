import QtQuick
import QtTest
import "../core/Coffee.js" as Coffee

TestCase {
    name: "Coffee"
    property var settings: ({ preventIdle: true, preventSleep: true, showInBar: true, decaffeinatePausesSchedules: false })
    property double now: new Date(2026, 9, 26, 14, 0, 0).getTime()   // Monday, 26 Oct 2026, 14:00 local

    function test_durations() {
        compare(Coffee.parseDuration("30m"), { seconds: 1800, rest: "" })
        compare(Coffee.parseDuration("1h30m").seconds, 5400)
        compare(Coffee.parseDuration("1h 30m 15s").seconds, 5415)
        compare(Coffee.parseDuration("0:45").seconds, 45)
        compare(Coffee.parseDuration("1:30:00").seconds, 5400)
        compare(Coffee.parseDuration("90", true).seconds, 5400)
        compare(Coffee.parseDuration("90", false), null)
        compare(Coffee.parseDuration("5pm", true), null)
        compare(Coffee.readDuration("30m tea", true).rest, "tea")
        compare(Coffee.describeDuration(5415), "1 h 30 min 15 s")
        compare(Coffee.describeDuration(600), "10 min")
        compare(Coffee.describeDuration(0), "0 s")
        compare(Coffee.countdown(59.2), "1:00")
        compare(Coffee.countdown(3661), "1:01:01")
    }

    function test_clocks() {
        compare(Coffee.parseClock("5pm"), { hours: 17, minutes: 0, seconds: 0 })
        compare(Coffee.parseClock("12am").hours, 0)
        compare(Coffee.parseClock("12pm").hours, 12)
        compare(Coffee.parseClock("17:30").hours, 17)
        compare(Coffee.parseClock("17:30").minutes, 30)
        compare(Coffee.parseClock("24:00"), null)
        compare(Coffee.parseClock("9:60"), null)
        compare(Coffee.parseClock("tomorrow"), null)
    }

    function test_until() {
        var five = Coffee.parseUntil("5pm", now)
        compare(new Date(five.atMs).getHours(), 17)
        compare(five.kind, "until")
        var passed = Coffee.parseUntil("1pm", now)
        compare(new Date(passed.atMs).getDate(), 27)   // already past, so tomorrow
        var morning = Coffee.parseUntil("tomorrow 8am", now)
        compare(new Date(morning.atMs).getDate(), 27)
        compare(new Date(morning.atMs).getHours(), 8)
        var inThirty = Coffee.parseUntil("in 30m", now)
        compare(inThirty.seconds, 1800)
        compare(inThirty.atMs, now + 1800 * 1000)
        var midnight = Coffee.parseUntil("midnight", now)
        compare(new Date(midnight.atMs).getDate(), 27)
        compare(new Date(midnight.atMs).getHours(), 0)
        compare(Coffee.parseUntil("soon", now), null)
    }

    function test_days() {
        compare(Coffee.parseDays("weekdays"), [1, 2, 3, 4, 5])
        compare(Coffee.parseDays("weekends"), [0, 6])
        compare(Coffee.parseDays("Mon,Thu"), [1, 4])
        compare(Coffee.parseDays("Monday to Friday"), [1, 2, 3, 4, 5])
        compare(Coffee.parseDays("every day except Tuesday"), [0, 1, 3, 4, 5, 6])
        compare(Coffee.parseDays("Saturday and Sunday"), [0, 6])
        compare(Coffee.parseDays("daily"), [0, 1, 2, 3, 4, 5, 6])
        compare(Coffee.parseDays(""), [])
        compare(Coffee.daySummary([1, 2, 3, 4, 5]), "Weekdays")
        compare(Coffee.daySummary([0, 6]), "Weekends")
        compare(Coffee.daySummary([0, 1, 2, 3, 4, 5, 6]), "Every day")
    }

    function test_schedules() {
        var s = Coffee.parseSchedule("Mon,Thu 09:00-14:00")
        compare(s.days, [1, 4])
        compare(s.from, "09:00")
        compare(s.to, "14:00")
        compare(s.id, "14-0900-1400")
        compare(Coffee.describeSchedule(s), "Mon, Thu 09:00-14:00")

        var weekdays = Coffee.parseSchedule("weekdays 9am-5pm")
        compare(weekdays.days, [1, 2, 3, 4, 5])
        compare(weekdays.from, "09:00")
        compare(weekdays.to, "17:00")

        var except = Coffee.parseSchedule("every day except Tuesday from 13:00 to 20:00")
        compare(except.days, [0, 1, 3, 4, 5, 6])
        compare(except.from, "13:00")
        compare(except.to, "20:00")

        var all = Coffee.parseSchedule("from 10:00 to 16:30")
        compare(all.days, [0, 1, 2, 3, 4, 5, 6])
        compare(Coffee.parseSchedule("Mon 14:00-09:00"), null)
        compare(Coffee.parseSchedule("Mon"), null)
    }

    function test_windows() {
        var s = Coffee.parseSchedule("Mon,Thu 09:00-14:00")
        verify(Coffee.inWindow(s, new Date(2026, 9, 26, 10, 0)))
        verify(!Coffee.inWindow(s, new Date(2026, 9, 26, 15, 0)))
        verify(!Coffee.inWindow(s, new Date(2026, 9, 27, 10, 0)))
        var paused = { id: s.id, days: s.days, from: s.from, to: s.to, paused: true }
        compare(Coffee.activeSchedule([paused], new Date(2026, 9, 26, 10, 0)), null)
        compare(Coffee.activeSchedule([s], new Date(2026, 9, 26, 10, 0)).id, s.id)
    }

    function test_root_and_main_rows() {
        var state = { active: false, mode: "manual", endsAt: 0, pattern: "", label: "", scheduleId: "", idleOwned: false, schedules: [], now: now }
        var root = Coffee.rootRows("coffee", state, "coffee")
        compare(root.length, 1)
        compare(root[0].action, { type: "navigate", scope: "coffee", title: "Coffee" })

        var open = Coffee.mainRows("", state, settings, "coffee", now)
        compare(open[0].action.type, "navigate")
        var on = Coffee.mainRows("on", state, settings, "coffee", now)
        compare(on[0].action, { type: "coffee-start", mode: "manual" })
        var off = Coffee.mainRows("off", state, settings, "coffee", now)
        compare(off[0].action.type, "coffee-stop")
        var toggle = Coffee.mainRows("toggle", state, settings, "coffee", now)
        compare(toggle[0].action.type, "coffee-toggle")

        var thirty = Coffee.mainRows("30m", state, settings, "coffee", now)
        compare(thirty[0].action.type, "coffee-start")
        compare(thirty[0].action.mode, "for")
        compare(thirty[0].action.seconds, 1800)

        var five = Coffee.mainRows("5pm", state, settings, "coffee", now)
        compare(five[0].action.mode, "until")
        compare(new Date(five[0].action.atMs).getHours(), 17)

        var whileApp = Coffee.mainRows("while Firefox", state, settings, "coffee", now)
        compare(whileApp[0].action, { type: "coffee-start", mode: "while", pattern: "Firefox" })

        var add = Coffee.mainRows("schedule add Mon,Thu 09:00-14:00", state, settings, "coffee", now)
        compare(add[0].action.type, "coffee-schedule-add")
        compare(add[0].action.schedule.days, [1, 4])
    }

    function test_duration_and_time_rows() {
        var state = { active: false, mode: "manual", endsAt: 0, pattern: "", label: "", scheduleId: "", idleOwned: false, schedules: [], now: now }
        var forRows = Coffee.forRows("", state, settings, "coffee", now)
        verify(forRows.length > 3)
        var forThirty = Coffee.forRows("30m tea", state, settings, "coffee", now)
        compare(forThirty[0].action.seconds, 1800)
        compare(forThirty[0].subtitle, "tea")
        var badFor = Coffee.forRows("soon", state, settings, "coffee", now)
        verify(badFor[0].disabled)

        var untilRows = Coffee.untilRows("", state, settings, "coffee", now)
        verify(untilRows.length > 3)
        var untilFive = Coffee.untilRows("5pm", state, settings, "coffee", now)
        compare(untilFive[0].action.mode, "until")
        var untilIn = Coffee.untilRows("in 30m", state, settings, "coffee", now)
        compare(untilIn[0].action.mode, "for")
        compare(untilIn[0].action.seconds, 1800)
        var badUntil = Coffee.untilRows("soon", state, settings, "coffee", now)
        verify(badUntil[0].disabled)

        var whileRows = Coffee.whileRows("", state, settings, "coffee", now)
        verify(whileRows[0].disabled)
        var whileApp = Coffee.whileRows("Firefox", state, settings, "coffee", now)
        compare(whileApp[0].action.pattern, "Firefox")
    }

    function test_screen_rows() {
        var state = { active: false, mode: "manual", endsAt: 0, pattern: "", label: "", scheduleId: "", idleOwned: false, schedules: [], now: now }
        var idle = Coffee.screenRows(state, settings, "coffee", "", now)
        compare(idle[0].title, "Not caffeinated")
        verify(idle.some(function(r) { return r.action.type === "coffee-start" }))

        var running = { active: true, mode: "for", endsAt: now + 9 * 60 * 1000, pattern: "", label: "", scheduleId: "", idleOwned: true, schedules: [], now: now }
        var active = Coffee.screenRows(running, settings, "coffee", "", now)
        compare(active[0].title, "Caffeinated for 9 min more")
        verify(active.some(function(r) { return r.action.type === "coffee-stop" }))
        verify(active.some(function(r) { return r.action.type === "coffee-extend" }))
        verify(active[0].subtitle.indexOf("screen lock paused by Coffee") >= 0)

        var manual = { active: true, mode: "manual", endsAt: 0, pattern: "", label: "", scheduleId: "", idleOwned: true, schedules: [], now: now }
        var manualRows = Coffee.screenRows(manual, settings, "coffee", "", now)
        verify(!manualRows.some(function(r) { return r.action.type === "coffee-extend" }))
    }

    function test_schedule_rows() {
        var s = Coffee.parseSchedule("Mon,Thu 09:00-14:00")
        var state = { active: false, mode: "manual", endsAt: 0, pattern: "", label: "", scheduleId: "", idleOwned: false, schedules: [s], now: now }
        var list = Coffee.scheduleRows("list", state, settings, "coffee", now)
        compare(list[0].action.type, "navigate")
        compare(list[0].action.scope, "coffee/schedule/" + s.id)
        verify(list.some(function(r) { return r.action.type === "query" }))

        var add = Coffee.scheduleRows("add Mon,Thu 09:00-14:00", state, settings, "coffee", now)
        compare(add[0].action.type, "coffee-schedule-add")
        compare(add[0].action.schedule.id, s.id)

        var pause = Coffee.scheduleRows("pause " + s.id, state, settings, "coffee", now)
        compare(pause[0].action, { type: "coffee-schedule-pause", id: s.id })
        var resume = Coffee.scheduleRows("resume " + s.id, state, settings, "coffee", now)
        compare(resume[0].action, { type: "coffee-schedule-resume", id: s.id })
        var remove = Coffee.scheduleRows("delete " + s.id, state, settings, "coffee", now)
        compare(remove[0].action, { type: "coffee-schedule-delete", id: s.id })
        var bad = Coffee.scheduleRows("add nope", state, settings, "coffee", now)
        verify(bad[0].disabled)
    }

    function test_schedule_detail() {
        var s = Coffee.parseSchedule("Mon,Thu 09:00-14:00")
        var state = { active: false, mode: "manual", endsAt: 0, pattern: "", label: "", scheduleId: "", idleOwned: false, schedules: [s], now: now }
        var rows = Coffee.scheduleDetailRows(s.id, state, settings, "coffee", now)
        compare(rows[0].title, "Mon, Thu 09:00-14:00")
        compare(rows[1].action.type, "coffee-schedule-pause")
        compare(rows[2].action.type, "coffee-schedule-delete")
        compare(rows[3].action.type, "navigate")
        var missing = Coffee.scheduleDetailRows("missing", state, settings, "coffee", now)
        verify(missing[0].disabled)
        compare(missing[1].action.type, "navigate")
    }
}
