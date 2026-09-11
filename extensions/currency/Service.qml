import QtQuick
import Quickshell
import Quickshell.Io
import "core/Currency.js" as Currency

// Currency: convert amounts between currencies from the palette.
//
// Keystroke creates this object when the extension is turned on, injects
// `shell`, `extension` and `omarchyPath`, reads `provider`, and destroys it
// when the extension is turned off. The rates are the ECB reference rates
// from Frankfurter, fetched with curl the first time a conversion is asked
// for on a given day (after 04:00 local time) and kept in
// ~/.cache/keystroke/currency/rates.json; offline, the last table answers
// and says how old it is. Nothing runs in the background and nothing runs
// before the first conversion. In automatic mode the explicit targets the
// user names are counted in ~/.local/state/keystroke/currency/usage.json.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var host: null            // the palette, captured from ctx on each query and activation
  property var settings: ({ preferredCurrency: "", targetMode: "preferred" })
  readonly property string key: extension && extension.id ? String(extension.id) : "currency"
  readonly property string home: Quickshell.env("HOME")
  readonly property string cacheDir: (Quickshell.env("XDG_CACHE_HOME") || root.home + "/.cache") + "/keystroke/currency"
  readonly property string stateDir: (Quickshell.env("XDG_STATE_HOME") || root.home + "/.local/state") + "/keystroke/currency"
  readonly property string localeCurrency: Qt.locale().currencySymbol(Locale.CurrencyIsoCode)

  property var cache: null           // the table, once read from disk or downloaded
  property bool cacheRead: false     // the file has been looked at (found or not)
  property var counts: ({})
  property bool fetching: false
  property double failedAt: 0
  property string error: ""

  readonly property var provider: ({
    apiVersion: 1,
    name: Currency.NAME,
    icon: Currency.ICON,
    color: Currency.COLOR,
    description: "Currency conversion with daily rates from Frankfurter",
    patterns: [
      { id: "symbol", regex: "^\\s*[$€£¥₺₹₩₽₴₪฿]\\s*\\d|^\\s*\\d[\\d.,]*\\s*[$€£¥₺₹₩₽₴₪฿]", flags: "", boost: 12, example: "$100 in try" },
      { id: "code", regex: "^\\s*\\d[\\d.,]*\\s*[a-z]{3}\\b", flags: "i", boost: 10, example: "100 usd to eur" }
    ],
    settings: [
      { key: "preferredCurrency", type: "string", label: "Preferred currency", "default": "",
        description: "Target for amounts that name none, like 129usd: a code such as EUR. Empty uses your locale's currency" },
      { key: "targetMode", type: "enum", label: "Target for amounts that name none", "default": "preferred", options: ["preferred", "automatic"],
        optionLabels: { preferred: "Preferred currency", automatic: "The one I convert to most" },
        description: "Automatic counts the targets you name (100 usd to eur) and uses the most frequent one" }
    ],
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) }
  })

  function attach(ctx) {
    if (ctx && ctx.host) root.host = ctx.host
    if (ctx && ctx.settings) root.settings = ctx.settings
  }

  // ------------------------------------------------------------------ files
  readonly property FileView cacheFile: FileView {
    path: root.cacheDir + "/rates.json"
    printErrors: false
    atomicWrites: true
    onLoaded: { root.cache = Currency.readCache(text()); root.cacheRead = true; root.settle() }
    onLoadFailed: { root.cacheRead = true; root.settle() }
  }
  readonly property FileView usageFile: FileView {
    path: root.stateDir + "/usage.json"
    printErrors: false
    atomicWrites: true
    onLoaded: root.counts = Currency.readCounts(text())
  }

  // ------------------------------------------------------------------ fetch
  // One curl at a time. stdout and the exit code arrive in either order, so
  // the fetch is over only when both have.
  property bool bodyDone: false
  property string body: ""
  property int exitCode: -1
  property string stderrText: ""
  readonly property Process fetcher: Process {
    stdout: StdioCollector { onStreamFinished: root.fetched(text) }
    stderr: StdioCollector { onStreamFinished: root.stderrText = text }
    onExited: function(code) { root.exited(code) }
  }
  function startFetch() {
    root.bodyDone = false
    root.body = ""
    root.exitCode = -1
    root.stderrText = ""
    root.fetching = true
    fetcher.command = Currency.fetchArgv(root.cacheDir, root.stateDir)
    fetcher.running = true
  }
  function fetched(text) {
    root.body = String(text)
    root.bodyDone = true
    if (root.exitCode >= 0) root.finish()
  }
  function exited(code) {
    root.exitCode = code
    if (root.bodyDone) root.finish()
  }
  // Both halves are in: judge the answer once, so every outcome (a bad exit,
  // an empty body, an unreadable table) records a failure and waits RETRY_MS.
  function finish() {
    var table = root.exitCode === 0 && root.body.trim() ? Currency.parseResponse(root.body, new Date().toISOString()) : null
    if (table) {
      root.cache = table
      root.error = ""
      root.failedAt = 0
      cacheFile.setText(JSON.stringify(table) + "\n")
    } else {
      if (root.exitCode !== 0) {
        var why = root.stderrText.trim().split("\n")[0].slice(0, 120)
        root.error = "curl exited with code " + root.exitCode + (why ? ": " + why : "")
      } else root.error = root.body.trim() ? "Frankfurter's answer could not be read" : "Frankfurter answered nothing"
      root.failedAt = Date.now()
      if (root.host && root.cache === null) root.host.errorMessage = "Currency: " + root.error
    }
    root.fetching = false
    root.settle()
  }
  function settle() {
    if (root.host && root.host.opened) root.host.requery()
  }

  // --------------------------------------------------------------- learning
  // In automatic mode an explicit target counts after a short dwell on its
  // row (or on activation), once per palette session.
  property string pendingTarget: ""
  property var seenTargets: ({})
  readonly property Timer dwell: Timer {
    interval: 1200
    onTriggered: if (root.host && root.host.opened) root.learn(root.pendingTarget)
  }
  readonly property Connections hostWatch: Connections {
    target: root.host
    ignoreUnknownSignals: true
    function onOpenedChanged() { dwell.stop(); root.seenTargets = ({}) }
  }
  function learn(c) {
    if (!c || root.seenTargets[c] || String(root.settings.targetMode) !== "automatic") return
    root.seenTargets[c] = true
    root.counts = Currency.bump(root.counts, c)
    usageFile.setText(JSON.stringify({ version: 1, counts: root.counts }) + "\n")
  }

  // ------------------------------------------------------------------ query
  function query(ctx) {
    root.attach(ctx)
    dwell.stop()
    if (ctx.scope) return []
    var q = String(ctx.query || "").trim()
    if (!q) return []
    var now = Date.now()
    var target = Currency.preferredTarget(root.settings, root.counts, root.cache, root.localeCurrency)
    var conversion = Currency.parse(q, target)
    if (!conversion || !Currency.known(conversion.base, root.cache) || !Currency.known(conversion.quote, root.cache)) return []
    if (root.cacheRead && Currency.shouldFetch(root.cache, now, root.fetching, root.failedAt)) root.startFetch()
    var waiting = !root.cacheRead || root.fetching
    if (!root.cache && waiting) ctx.pending()
    var rows = Currency.rows(conversion, root.cache, { fetching: waiting, error: root.error }, q, now)
    if (rows.length && rows[0].currencyTarget && String(root.settings.targetMode) === "automatic" && !root.seenTargets[rows[0].currencyTarget]) {
      root.pendingTarget = rows[0].currencyTarget
      dwell.restart()
    }
    return rows
  }

  function activate(row, ctx) {
    root.attach(ctx)
    if (row.currencyTarget) root.learn(row.currencyTarget)
    return ctx.alternate && row.altAction ? row.altAction : row.action
  }

  Component.onDestruction: { if (fetcher.running) fetcher.signal(15) }
}
