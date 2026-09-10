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
// window closes; a notification and a sound fire when one ends, and the
// soonest countdown shows next to the menu button in the bar through
// host.setBarItem. State is in memory only: restarting omarchy-shell clears
// the timers.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  readonly property string home: Quickshell.env("HOME")
  property var host: null            // the palette, captured from ctx on each query and activation
  property var timers: []
  property var settings: ({ defaultMinutes: 5, notify: true, sound: "chime", soundFile: "", showInBar: true })
  property double now: Date.now()
  readonly property string key: extension && extension.id ? String(extension.id) : "timer"

  readonly property var provider: ({
    apiVersion: 1,
    name: "Timer",
    icon: "󰔛",
    color: "#e5c07b",
    description: "Countdown timers with a sound, a notification and a countdown in the bar",
    prefix: "timer",
    settings: [
      { key: "defaultMinutes", type: "number", label: "Default length (minutes)", "default": 5, min: 1, max: 720, integer: true,
        description: "Used by `timer tea` when no duration is given" },
      { key: "sound", type: "enum", label: "Sound when a timer ends", "default": "chime", options: ["off", "chime", "drop", "alarm"],
        optionLabels: { off: "Off", chime: "Chime", drop: "Drop", alarm: "Alarm" },
        description: "Chime, Drop and Alarm are the freedesktop sounds in /usr/share/sounds; Custom sound file replaces the chosen one" },
      { key: "soundFile", type: "string", label: "Custom sound file", "default": "",
        description: "Path to an audio file played instead of the built-in sound; empty uses the choice above" },
      { key: "notify", type: "boolean", label: "Notify when a timer ends", "default": true },
      { key: "showInBar", type: "boolean", label: "Show the countdown in the bar", "default": true,
        description: "The soonest timer counts down next to the Keystroke menu button from the moment it starts" }
    ],
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) },
    opened: function() { root.now = Date.now() }
  })

  // One tick per second while anything is running: fires notifications and
  // sounds, refreshes the countdown in the bar and, when the palette shows
  // this extension's screen, the rows.
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
      root.publish()
      var h = root.host
      if (h && h.opened && h.scope === root.key) h.requery()
    }
  }

  // Settings are read from ctx on every query; a save while no query runs
  // (the bar switch flipped from the Settings screen) reaches us through
  // the host's configChanged.
  readonly property Connections hostWatch: Connections {
    target: root.host
    ignoreUnknownSignals: true
    function onConfigChanged() {
      var h = root.host
      if (!h || typeof h.providerSettings !== "function") return
      root.settings = h.providerSettings(root.key)
      root.publish()
    }
  }

  function attach(ctx) {
    if (ctx && ctx.host) root.host = ctx.host
    if (ctx && ctx.settings) root.settings = ctx.settings
  }

  // The bar shows the soonest timer while the setting is on; null clears it.
  function publish() {
    var h = root.host
    if (!h || typeof h.setBarItem !== "function") return
    h.setBarItem(root.key, root.settings.showInBar === false ? null : TimerModel.barItem(root.timers, root.now, root.key))
  }

  function finish(timer) {
    var argv = TimerModel.soundArgv(root.settings, root.home)
    if (argv) Quickshell.execDetached(argv)
    if (root.settings.notify === false) return
    Quickshell.execDetached([root.omarchyPath + "/bin/omarchy-notification-send", "-g", "󰔛",
                             timer.label ? "Timer: " + timer.label : "Timer done", TimerModel.describe(timer.seconds) + " are up"])
  }

  function query(ctx) {
    root.attach(ctx)
    var scoped = ctx.scope === root.key
    if (ctx.scope && !scoped) return []
    root.now = Date.now()
    // The host hands over the text after the declared prefix; the aliases in Timer.js still work without it.
    var viaCommand = !!ctx.command
    return TimerModel.rows(viaCommand ? ctx.command.rest : ctx.query, root.timers, ctx.settings, root.now, scoped, root.key, viaCommand)
  }

  function activate(row, ctx) {
    root.attach(ctx)
    var effect = ctx.alternate && row.altAction ? row.altAction : row.action
    if (!effect) return effect
    if (effect.type === "timer-start") {
      root.now = Date.now()
      root.timers = root.timers.concat([TimerModel.make(effect.seconds, effect.label, root.now)])
      root.publish()
      // Return an ordinary effect: the palette closes and a toast confirms.
      return { type: "compound", actions: [
        { type: "notify", glyph: "󰔛", headline: "Timer started", body: TimerModel.describe(effect.seconds) + (effect.label ? " · " + effect.label : "") },
        { type: "close" } ] }
    }
    if (effect.type === "timer-cancel") {
      root.timers = root.timers.filter(function(t) { return t.id !== effect.id })
      root.publish()
      return { type: "noop" }
    }
    return effect
  }

  Component.onDestruction: {
    var h = root.host
    if (h && typeof h.setBarItem === "function") h.setBarItem(root.key, null)
  }
}
