import QtQuick
import Quickshell
import Quickshell.Io
import "core/Coffee.js" as Coffee

// Coffee: keep the screen and the computer awake, for a while or on a
// schedule. The sleep inhibitor is a systemd-inhibit child; the idle clock is
// Omarchy's own stay-awake switch, parked through bin/coffee so a stay-awake
// the user set themselves is never cleared by Coffee.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  readonly property string home: Quickshell.env("HOME")
  property var host: null            // the palette, captured from ctx on each query and activation
  property var settings: ({ preventIdle: true, preventSleep: true, showInBar: true, decaffeinatePausesSchedules: false })
  property double now: Date.now()
  readonly property string key: extension && extension.id ? String(extension.id) : "coffee"
  readonly property string omarchyBin: (root.omarchyPath ? root.omarchyPath : "/usr/share/omarchy") + "/bin"
  readonly property string helper: extension && extension.dir ? String(extension.dir) + "/bin/coffee" : String(Qt.resolvedUrl("bin/coffee")).replace(/^file:\/\//, "")
  readonly property string stateDir: root.home + "/.local/state/keystroke/coffee"
  readonly property string statePath: root.stateDir + "/state.json"

  property bool active: false
  property string mode: "manual"     // manual | for | until | while | schedule
  property double endsAt: 0
  property string pattern: ""
  property string label: ""
  property string scheduleId: ""
  property bool idleOwned: false
  property var schedules: []
  property bool schedulesRead: false
  property bool schedulesDirty: false
  property bool staleSweepDone: false
  property bool idleStarting: false
  property bool idleOffPending: false
  property bool idleOnPending: false
  property bool inhibitorStopping: false
  property bool inhibitorPending: false
  property string pendingWatch: ""
  property string error: ""

  readonly property var provider: ({
    apiVersion: 1,
    name: Coffee.NAME,
    icon: Coffee.ICON,
    color: Coffee.COLOR,
    description: "Keep the computer awake on demand: coffee 30m, coffee 5pm, coffee while Firefox",
    settings: [
      { key: "preventIdle", type: "boolean", label: "Pause Omarchy's idle clock", "default": true,
        description: "Stops the screen from locking while caffeinated. Coffee only restores a stay-awake it set itself" },
      { key: "preventSleep", type: "boolean", label: "Block system sleep", "default": true,
        description: "Holds a systemd sleep and idle inhibitor, including while the lid is closed" },
      { key: "showInBar", type: "boolean", label: "Show Coffee in the bar", "default": true,
        description: "A coffee cup and a countdown next to the menu button while caffeinated" },
      { key: "decaffeinatePausesSchedules", type: "boolean", label: "Decaffeinate pauses a schedule", "default": false,
        description: "When off, decaffeinate while a schedule is running asks you to pause the schedule instead" }
    ],
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) },
    opened: function() { root.now = Date.now(); root.publish() }
  })

  // ---------------------------------------------------------------- snapshots
  function snapshot() {
    return { active: root.active, mode: root.mode, endsAt: root.endsAt, pattern: root.pattern,
             label: root.label, scheduleId: root.scheduleId, idleOwned: root.idleOwned,
             schedules: root.schedules, now: root.now }
  }

  function attach(ctx) {
    if (ctx && ctx.host) root.host = ctx.host
    if (ctx && ctx.settings) root.settings = ctx.settings
    root.publish()
  }

  // -------------------------------------------------------------------- query
  function query(ctx) {
    root.attach(ctx)
    var scope = String(ctx.scope || "")
    if (scope && scope !== root.key && scope.indexOf(root.key + "/") !== 0) return []
    root.now = Date.now()
    if (scope === root.key) return Coffee.screenRows(root.snapshot(), root.settings, root.key, "", root.now)
    if (scope.indexOf(root.key + "/schedule/") === 0) {
      return Coffee.scheduleDetailRows(scope.slice((root.key + "/schedule/").length), root.snapshot(), root.settings, root.key, root.now)
    }
    if (scope) return []
    if (ctx.command) {
      var id = String(ctx.command.id || ""), rest = String(ctx.command.rest || "")
      if (id === "caffeinate") return Coffee.mainRows("on", root.snapshot(), root.settings, root.key, root.now)
      if (id === "decaffeinate") return Coffee.mainRows("off", root.snapshot(), root.settings, root.key, root.now)
      if (id === "coffee-status") return Coffee.mainRows("status", root.snapshot(), root.settings, root.key, root.now)
      if (id === "coffee-for") return Coffee.forRows(rest, root.snapshot(), root.settings, root.key, root.now)
      if (id === "coffee-until") return Coffee.untilRows(rest, root.snapshot(), root.settings, root.key, root.now)
      if (id === "coffee-while") return Coffee.whileRows(rest, root.snapshot(), root.settings, root.key, root.now)
      if (id === "coffee-schedule") return Coffee.scheduleRows(rest, root.snapshot(), root.settings, root.key, root.now)
      return Coffee.mainRows(rest, root.snapshot(), root.settings, root.key, root.now)
    }
    return Coffee.rootRows(ctx.query, root.snapshot(), root.key)
  }

  // ---------------------------------------------------------------- activation
  function activate(row, ctx) {
    root.attach(ctx)
    var effect = ctx.alternate && row.altAction ? row.altAction : row.action
    if (!effect) return effect
    if (effect.type === "coffee-start") return root.startFromEffect(effect)
    if (effect.type === "coffee-stop") return root.stopFromEffect(ctx)
    if (effect.type === "coffee-toggle") return root.active ? root.stopFromEffect(ctx) : root.startFromEffect({ mode: "manual" })
    if (effect.type === "coffee-schedule-add") {
      if (!root.addSchedule(effect.schedule)) return { type: "noop" }
      return root.closeWith("Schedule added", Coffee.describeSchedule(effect.schedule))
    }
    if (effect.type === "coffee-schedule-pause") {
      if (!root.pauseSchedule(effect.id)) return { type: "noop" }
      return root.afterScheduleChange(ctx, "Schedule paused", root.scheduleLabel(effect.id))
    }
    if (effect.type === "coffee-schedule-resume") {
      if (!root.resumeSchedule(effect.id)) return { type: "noop" }
      return root.afterScheduleChange(ctx, "Schedule resumed", root.scheduleLabel(effect.id))
    }
    if (effect.type === "coffee-schedule-delete") return root.confirmScheduleDelete(effect.id, ctx)
    if (effect.type === "coffee-extend") return root.extendFromEffect(effect.seconds)
    return effect
  }

  function inDetail(ctx) {
    var scope = String((ctx && ctx.scope) || (root.host && root.host.scope) || "")
    return scope.indexOf(root.key + "/schedule/") === 0
  }

  function afterScheduleChange(ctx, headline, body) {
    if (root.inDetail(ctx)) {
      if (root.host && typeof root.host.requery === "function") root.host.requery()
      return { type: "noop" }
    }
    return root.closeWith(headline, body)
  }

  // The palette confirms before it performs a row's effect, but schedules are
  // changed here in activate(), so the prompt has to be raised here too.
  function confirmScheduleDelete(id, ctx) {
    var h = root.host
    var label = root.scheduleLabel(id)
    if (!h || !label) return { type: "noop" }
    var detail = root.inDetail(ctx)
    h.confirmPending = {
      message: "Delete the " + label + " schedule?",
      detail: "You can add it again at any time.",
      confirmText: "Delete",
      cancelText: "Keep",
      run: function() {
        var gone = root.scheduleLabel(id)
        if (!root.deleteSchedule(id)) return
        if (detail && typeof h.goBack === "function") h.goBack()
        else if (typeof h.cancel === "function") h.cancel()
        root.autoNotify("Schedule deleted", gone)
      }
    }
    return { type: "noop" }
  }

  function extendFromEffect(seconds) {
    if (!root.active || (root.mode !== "for" && root.mode !== "until")) return { type: "noop" }
    var add = Math.max(1, Number(seconds || 0)) * 1000
    root.now = Date.now()
    root.endsAt = Math.max(root.endsAt, root.now) + add
    root.publish()
    root.refreshPalette()
    return root.closeWith("Coffee extended", root.startBody())
  }

  function notifyEffect(headline, body) {
    return { type: "notify", glyph: Coffee.ICON, headline: headline, body: body }
  }

  function closeWith(headline, body) {
    return { type: "compound", actions: [root.notifyEffect(headline, body), { type: "close" }] }
  }

  function startBody() {
    if (root.mode === "for") return "For " + Coffee.describeDuration(Math.max(0, (root.endsAt - root.now) / 1000)) + (root.label ? " · " + root.label : "")
    if (root.mode === "until") return "Until " + Coffee.clockLabel(root.endsAt)
    if (root.mode === "while") return "While " + root.pattern + " runs"
    if (root.mode === "schedule") return root.label || "A schedule is running"
    return "The screen can stay on and the computer can stay awake until you decaffeinate"
  }

  function startFromEffect(effect) {
    var mode = String(effect.mode || "manual")
    if (mode === "while" && !String(effect.pattern || "").trim()) return { type: "noop" }
    var opts = { seconds: effect.seconds, atMs: effect.atMs, pattern: effect.pattern,
                 label: effect.label, scheduleId: effect.scheduleId, notify: false }
    if (!root.startInternal(mode, opts)) return { type: "noop" }
    return root.closeWith("Coffee is on", root.startBody())
  }

  function stopFromEffect(ctx) {
    if (!root.active) return { type: "noop" }
    if (root.mode === "schedule" && root.settings.decaffeinatePausesSchedules !== true) {
      if (root.host) root.host.statusMessage = "Schedule running · pause the schedule first"
      return { type: "noop" }
    }
    if (root.mode === "schedule" && root.scheduleId) root.pauseSchedule(root.scheduleId)
    root.stopInternal(false)
    return root.closeWith("Coffee is off", "The screen can lock and the computer can sleep again")
  }

  // ---------------------------------------------------------------- lifecycle
  function startInternal(mode, opts) {
    opts = opts || {}
    if (root.settings.preventIdle === false && root.settings.preventSleep === false) {
      if (root.host) root.host.errorMessage = "Coffee: turn on at least one prevention setting"
      return false
    }
    var keepIdle = root.idleOwned
    root.stopInternal(false, true)
    root.active = true
    root.mode = mode
    root.endsAt = 0
    root.pattern = ""
    root.label = ""
    root.scheduleId = ""
    root.now = Date.now()
    if (mode === "for") root.endsAt = root.now + Math.max(1, Number(opts.seconds || 0)) * 1000
    else if (mode === "until") root.endsAt = Number(opts.atMs || 0)
    else if (mode === "while") root.pattern = String(opts.pattern || "")
    else if (mode === "schedule") { root.scheduleId = String(opts.scheduleId || ""); root.label = String(opts.label || "") }
    if (opts.label && mode !== "schedule" && mode !== "until") root.label = String(opts.label || "")
    root.error = ""

    if (root.settings.preventSleep !== false) root.startInhibitor()
    else root.stopInhibitor()

    if (root.settings.preventIdle !== false) {
      if (keepIdle) root.idleOwned = true
      else if (!root.idleProcess.running) root.startIdleOn()
    } else {
      root.requestIdleOff()
    }

    if (mode === "while" && root.pattern) root.startWatch(root.pattern)
    root.publish()
    if (opts.notify !== false) root.autoNotify("Coffee is on", root.startBody())
    return true
  }

  function stopInternal(notify, keepIdle) {
    var wasActive = root.active
    root.active = false
    root.mode = "manual"
    root.endsAt = 0
    root.pattern = ""
    root.label = ""
    root.scheduleId = ""
    root.pendingWatch = ""
    if (!keepIdle) root.stopInhibitor()
    if (root.watcher.running) root.watcher.signal(15)
    if (!keepIdle) root.requestIdleOff()
    root.publish()
    if (notify && wasActive) root.autoNotify("Coffee is off", "The screen can lock and the computer can sleep again")
  }

  // ------------------------------------------------------------------- clock
  readonly property Timer clock: Timer {
    interval: 1000
    repeat: true
    running: root.active && (root.mode === "for" || root.mode === "until")
    onTriggered: {
      root.now = Date.now()
      if (root.active && (root.mode === "for" || root.mode === "until") && root.now >= root.endsAt) {
        var doneMode = root.mode
        root.stopInternal(false)
        root.autoNotify("Coffee finished", doneMode === "until" ? "The time you named has passed" : "The timer ended; the computer can sleep again")
      }
      root.publish()
      root.refreshPalette()
    }
  }

  readonly property Timer scheduleClock: Timer {
    interval: 30000
    repeat: true
    running: root.schedules.length > 0 || (root.active && root.mode === "schedule")
    onTriggered: {
      root.now = Date.now()
      root.evaluateSchedules(false)
      root.publish()
      root.refreshPalette()
    }
  }

  function refreshPalette() {
    var h = root.host
    if (!h || !h.opened || typeof h.requery !== "function") return
    var scope = String(h.scope || "")
    if (scope === root.key || scope.indexOf(root.key + "/") === 0) h.requery()
  }

  // --------------------------------------------------------------- schedules
  function maybeEvaluate() {
    if (root.schedulesRead && root.staleSweepDone) root.evaluateSchedules(false)
  }

  function evaluateSchedules(silent) {
    if (!root.schedulesRead || !root.staleSweepDone) return
    root.now = Date.now()
    if (root.active && root.mode === "schedule") {
      var current = root.scheduleById(root.scheduleId)
      if (!current || current.paused || !Coffee.inWindow(current, new Date(root.now))) {
        var ended = root.label
        root.stopInternal(false)
        if (!silent) root.autoNotify("Schedule ended", ended || "Coffee's schedule is no longer running")
      }
      return
    }
    if (root.active) return
    var due = Coffee.activeSchedule(root.schedules, new Date(root.now))
    if (due) root.startInternal("schedule", { scheduleId: due.id, label: Coffee.describeSchedule(due), notify: !silent })
  }

  function scheduleById(id) {
    for (var i = 0; i < root.schedules.length; i++) if (root.schedules[i].id === id) return root.schedules[i]
    return null
  }

  function scheduleLabel(id) {
    var s = root.scheduleById(id)
    return s ? Coffee.describeSchedule(s) : ""
  }

  function normalizeSchedule(s) {
    if (!s || typeof s !== "object" || !s.days || s.days.length === undefined) return null
    if (!/^\d{2}:\d{2}$/.test(String(s.from || "")) || !/^\d{2}:\d{2}$/.test(String(s.to || ""))) return null
    if (Coffee.clockMinutes(s.from) < 0 || Coffee.clockMinutes(s.to) <= Coffee.clockMinutes(s.from)) return null
    var days = []
    for (var i = 0; i < s.days.length; i++) {
      var d = Number(s.days[i])
      if (d >= 0 && d < 7 && days.indexOf(d) < 0) days.push(d)
    }
    if (!days.length) return null
    days.sort(function(a, b) { return a - b })
    return { id: Coffee.scheduleId(days, s.from, s.to), days: days, from: String(s.from), to: String(s.to), paused: s.paused === true }
  }

  function addSchedule(s) {
    var n = root.normalizeSchedule(s)
    if (!n) return false
    var out = []
    for (var i = 0; i < root.schedules.length; i++) if (root.schedules[i].id !== n.id) out.push(root.schedules[i])
    out.push(n)
    root.schedules = out
    root.schedulesDirty = true
    root.saveSchedules()
    root.evaluateSchedules(true)
    root.publish()
    return true
  }

  function pauseSchedule(id) {
    var s = root.scheduleById(id)
    if (!s) return false
    var out = []
    for (var i = 0; i < root.schedules.length; i++) {
      var x = root.schedules[i]
      out.push(x.id === id ? { id: x.id, days: x.days, from: x.from, to: x.to, paused: true } : x)
    }
    root.schedules = out
    root.schedulesDirty = true
    root.saveSchedules()
    if (root.active && root.mode === "schedule" && root.scheduleId === id) root.stopInternal(false)
    root.evaluateSchedules(true)
    root.publish()
    return true
  }

  function resumeSchedule(id) {
    var s = root.scheduleById(id)
    if (!s) return false
    var out = []
    for (var i = 0; i < root.schedules.length; i++) {
      var x = root.schedules[i]
      out.push(x.id === id ? { id: x.id, days: x.days, from: x.from, to: x.to, paused: false } : x)
    }
    root.schedules = out
    root.schedulesDirty = true
    root.saveSchedules()
    root.evaluateSchedules(true)
    root.publish()
    return true
  }

  function deleteSchedule(id) {
    var found = false, out = []
    for (var i = 0; i < root.schedules.length; i++) {
      if (root.schedules[i].id === id) found = true
      else out.push(root.schedules[i])
    }
    if (!found) return false
    root.schedules = out
    root.schedulesDirty = true
    root.saveSchedules()
    if (root.active && root.mode === "schedule" && root.scheduleId === id) root.stopInternal(false)
    root.evaluateSchedules(true)
    root.publish()
    return true
  }

  readonly property FileView stateFile: FileView {
    path: root.statePath
    printErrors: false
    atomicWrites: true
    onLoaded: root.readState(text())
    onLoadFailed: { root.schedulesRead = true; root.maybeEvaluate() }
  }

  function readState(text) {
    root.schedulesRead = true
    if (root.schedulesDirty) { root.maybeEvaluate(); return }
    try {
      var data = JSON.parse(text)
      var list = data && data.schedules ? data.schedules : []
      var out = []
      for (var i = 0; i < list.length; i++) {
        var s = root.normalizeSchedule(list[i])
        if (s) out.push(s)
      }
      root.schedules = out
    } catch (e) {
      root.error = "Saved schedules could not be read"
    }
    root.maybeEvaluate()
  }

  function saveSchedules() {
    Quickshell.execDetached(["mkdir", "-p", root.stateDir])
    try {
      root.stateFile.setText(JSON.stringify({ version: 1, schedules: root.schedules }, null, 2) + "\n")
    } catch (e) {
      root.error = "Schedules could not be saved"
    }
  }

  // ---------------------------------------------------------------- inhibitor
  readonly property Process inhibitor: Process {
    onExited: function(code) {
      var wasStopping = root.inhibitorStopping
      root.inhibitorStopping = false
      if (root.inhibitorPending) {
        root.inhibitorPending = false
        root.startInhibitor()
        return
      }
      if (wasStopping) return
      if (root.active) {
        root.stopInternal(false)
        root.autoNotify("Coffee stopped", "The system sleep inhibitor exited unexpectedly")
      }
    }
  }

  function startInhibitor() {
    if (root.inhibitor.running) {
      if (root.inhibitorStopping) root.inhibitorPending = true
      return
    }
    root.inhibitor.command = ["systemd-inhibit", "--what=idle:sleep:handle-lid-switch",
      "--who=Keystroke Coffee", "--why", "Coffee keeps the computer awake",
      "--mode=block", "sleep", "infinity"]
    root.inhibitor.running = true
  }

  function stopInhibitor() {
    root.inhibitorPending = false
    if (!root.inhibitor.running) return
    root.inhibitorStopping = true
    root.inhibitor.signal(15)
  }

  // -------------------------------------------------------------------- watch
  readonly property Process watcher: Process {
    onExited: function(code) {
      if (root.pendingWatch) {
        var next = root.pendingWatch
        root.pendingWatch = ""
        root.startWatch(next)
        return
      }
      if (!root.active || root.mode !== "while") return
      var gone = root.pattern
      root.stopInternal(false)
      root.autoNotify("Coffee stopped", gone + " is no longer running")
    }
  }

  function startWatch(pattern) {
    if (root.watcher.running) {
      root.pendingWatch = pattern
      root.watcher.signal(15)
      return
    }
    root.watcher.command = [root.helper, "watch", pattern]
    root.watcher.running = true
  }

  // --------------------------------------------------------------------- idle
  readonly property Process idleProcess: Process {
    stdout: SplitParser { onRead: function(line) { root.idleReport(line) } }
    stderr: SplitParser { onRead: function(line) { console.log("coffee: " + line) } }
    onExited: function(code) {
      root.idleStarting = false
      if (root.idleOffPending) {
        root.idleOffPending = false
        if (root.active && root.settings.preventIdle !== false) root.idleOnPending = true
        root.idleOffNow()
      }
    }
  }

  readonly property Process idleOffProcess: Process {
    onExited: function(code) {
      if (root.idleOnPending) {
        root.idleOnPending = false
        if (root.active && root.settings.preventIdle !== false) root.startIdleOn()
      }
    }
  }

  readonly property Process staleIdleSweep: Process {
    command: [root.helper, "idle-off"]
    onExited: function(code) { root.staleSweepDone = true; root.maybeEvaluate() }
  }

  function idleReport(line) {
    var report = String(line || "").trim()
    if (report === "owned") root.idleOwned = true
    else if (report === "already") root.idleOwned = false
    else if (report === "unavailable") {
      root.idleOwned = false
      root.error = "Omarchy's idle clock could not be paused"
      if (root.host) root.host.errorMessage = "Coffee: " + root.error
    }
    root.publish()
  }

  function startIdleOn() {
    if (root.idleProcess.running) return
    if (root.idleOffProcess.running) { root.idleOnPending = true; return }
    root.idleStarting = true
    root.idleProcess.command = [root.helper, "idle-on"]
    root.idleProcess.running = true
  }

  function requestIdleOff() {
    if (root.idleProcess.running) {
      root.idleOffPending = true
      return
    }
    root.idleOffNow()
  }

  function idleOffNow() {
    if (root.idleOffProcess.running) return
    root.idleOwned = false
    root.idleOffProcess.command = [root.helper, "idle-off"]
    root.idleOffProcess.running = true
  }

  // --------------------------------------------------------------------- bar
  function publish() {
    var h = root.host
    if (!h || typeof h.setBarItem !== "function") return
    if (!root.active || root.settings.showInBar === false) {
      h.setBarItem(root.key, null)
      return
    }
    var detail = root.barDetail()
    h.setBarItem(root.key, {
      text: (Coffee.ICON + " " + detail).slice(0, 40),
      tooltip: Coffee.statusTitle(root.snapshot(), root.now) + " · " + Coffee.statusDetail(root.snapshot(), root.now, root.settings),
      payload: { scope: root.key, title: Coffee.NAME }
    })
  }

  function barDetail() {
    if (root.mode === "for" || root.mode === "until") return Coffee.countdown(Math.max(0, (root.endsAt - root.now) / 1000))
    if (root.mode === "while") return root.pattern
    if (root.mode === "schedule") return "sched"
    return "on"
  }

  function autoNotify(headline, body) {
    Quickshell.execDetached([root.omarchyBin + "/omarchy-notification-send", "-g", Coffee.ICON, headline, body])
  }

  // --------------------------------------------------------------- settings
  function applySettings() {
    if (!root.active) { root.publish(); return }
    if (root.settings.preventIdle === false && root.settings.preventSleep === false) {
      root.stopInternal(true)
      return
    }
    if (root.settings.preventSleep !== false) root.startInhibitor()
    else root.stopInhibitor()
    if (root.settings.preventIdle !== false) {
      if (!root.idleOwned && !root.idleProcess.running) root.startIdleOn()
    } else root.requestIdleOff()
    root.publish()
  }

  readonly property Connections hostWatch: Connections {
    target: root.host
    ignoreUnknownSignals: true
    function onConfigChanged() {
      var h = root.host
      if (!h || typeof h.providerSettings !== "function") return
      root.settings = h.providerSettings(root.key)
      root.applySettings()
      root.evaluateSchedules(true)
    }
  }

  readonly property Timer staleSweepTimeout: Timer {
    interval: 3000
    running: !root.staleSweepDone
    onTriggered: { root.staleSweepDone = true; root.maybeEvaluate() }
  }

  Component.onCompleted: {
    Quickshell.execDetached(["mkdir", "-p", root.stateDir])
    root.staleIdleSweep.running = true
  }

  Component.onDestruction: {
    if (root.inhibitor.running) root.inhibitor.signal(15)
    if (root.watcher.running) root.watcher.signal(15)
    if (root.idleProcess.running) root.idleProcess.signal(15)
    Quickshell.execDetached([root.helper, "idle-off"])
    var h = root.host
    if (h && typeof h.setBarItem === "function") h.setBarItem(root.key, null)
  }
}
