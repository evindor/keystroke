import QtQuick
import Quickshell
import "core/Timer.js" as TimerModel

// Timer: the reference extension for the Keystroke command palette.
//
// This file is the whole extension at runtime. Keystroke creates it inside
// omarchy-shell when the user turns the extension on, injects `shell`,
// `extension` (the parsed extension.json plus id and dir) and `omarchyPath`,
// reads `provider`, and destroys the object when the extension is turned off.
// The object outlives the palette window, so timers keep counting after the
// window closes; a notification fires when one ends. State is in memory
// only: restarting omarchy-shell clears the timers.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var host: null            // the palette, captured from ctx on each query
  property var timers: []
  property var settings: ({ defaultMinutes: 5, notify: true })
  property double now: Date.now()
  readonly property string key: extension && extension.id ? String(extension.id) : "timer"

  readonly property var provider: ({
    apiVersion: 1,
    name: "Timer",
    icon: "󰔛",
    color: "#e5c07b",
    description: "Countdown timers with a notification when they end",
    prefix: "timer",
    settings: [
      { key: "defaultMinutes", type: "number", label: "Default length (minutes)", "default": 5, min: 1, max: 720, integer: true,
        description: "Used by `timer tea` when no duration is given" },
      { key: "notify", type: "boolean", label: "Notify when a timer ends", "default": true }
    ],
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) },
    opened: function() { root.now = Date.now() }
  })

  // One tick per second while anything is running: fires notifications and
  // refreshes the countdown when the palette shows this extension's screen.
  readonly property Timer clock: Timer {
    interval: 1000
    repeat: true
    running: root.timers.length > 0
    onTriggered: {
      root.now = Date.now()
      var keep = [], done = []
      for (var i = 0; i < root.timers.length; i++) (root.timers[i].endsAt <= root.now ? done : keep).push(root.timers[i])
      if (done.length) {
        root.timers = keep
        for (var d = 0; d < done.length; d++) root.finish(done[d])
      }
      var h = root.host
      if (h && h.opened && h.scope === root.key) h.requery()
    }
  }

  function finish(timer) {
    if (root.settings.notify === false) return
    Quickshell.execDetached([root.omarchyPath + "/bin/omarchy-notification-send", "-g", "󰔛",
                             timer.label ? "Timer: " + timer.label : "Timer done", TimerModel.describe(timer.seconds) + " are up"])
  }

  function query(ctx) {
    root.host = ctx.host
    root.settings = ctx.settings
    var scoped = ctx.scope === root.key
    if (ctx.scope && !scoped) return []
    root.now = Date.now()
    return TimerModel.rows(ctx.query, root.timers, ctx.settings, root.now, scoped, root.key)
  }

  function activate(row, ctx) {
    var effect = ctx.alternate && row.altAction ? row.altAction : row.action
    if (!effect) return effect
    if (effect.type === "timer-start") {
      root.timers = root.timers.concat([TimerModel.make(effect.seconds, effect.label, Date.now())])
      // Return an ordinary effect: the palette closes and a toast confirms.
      return { type: "compound", actions: [
        { type: "notify", glyph: "󰔛", headline: "Timer started", body: TimerModel.describe(effect.seconds) + (effect.label ? " · " + effect.label : "") },
        { type: "close" } ] }
    }
    if (effect.type === "timer-cancel") {
      root.timers = root.timers.filter(function(t) { return t.id !== effect.id })
      return { type: "noop" }
    }
    return effect
  }
}
