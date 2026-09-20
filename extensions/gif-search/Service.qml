import QtQuick
import Quickshell
import Quickshell.Io
import "core/Gifs.js" as Gifs

QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  readonly property string key: extension && extension.id ? extension.id : "gif-search"
  property string term: ""
  property int page: 0
  property var items: []
  property bool more: false
  property bool active: false
  property bool loading: false
  property string message: ""
  property int revision: 0
  property int requestedRevision: -1
  property string body: ""
  property bool bodyDone: false
  property int exitCode: -1
  property bool copying: false
  property bool copyBodyDone: false
  property int copyExit: -1
  property string copyBody: ""
  property var settings: ({ defaultAction: "image", closeAfterCopy: false })
  property int session: 0
  property int copySession: -1
  signal copySucceeded()

  readonly property var provider: ({
    apiVersion: 1, name: "GIF Search", icon: Gifs.ICON, color: "#c678dd",
    description: "Search GIPHY and copy GIFs", view: view,
    settings: [
      { key: "defaultAction", type: "enum", label: "Default action", "default": "image",
        options: ["image", "link"], optionLabels: { image: "Copy image", link: "Copy link" },
        description: "Enter uses this action; Ctrl+Enter uses the other" },
      { key: "closeAfterCopy", type: "boolean", label: "Close after copy", "default": false }
    ],
    query: function(ctx) { return Gifs.rows(ctx, root.key) },
    activate: function(row, ctx) {
      root.settings = ctx.settings || ({ defaultAction: "image", closeAfterCopy: false })
      root.session++
      root.active = true
      root.term = row.action.term || ""
      root.page = 0
      root.refresh()
      return { type: "provider-view", provider: root.key }
    }
  })
  readonly property Component view: Component { GifView { service: root } }
  readonly property Timer debounce: Timer { interval: 300; onTriggered: root.fetch() }
  readonly property Process request: Process {
    stdout: StdioCollector { onStreamFinished: { root.body = text; root.bodyDone = true; root.finish() } }
    onExited: function(code) { root.exitCode = code; root.finish() }
  }

  function search(text) {
    var next = String(text).trim().slice(0, 300)
    if (next === term) return
    term = next
    page = 0
    refresh()
  }
  function turnPage(delta) {
    if (loading || (delta > 0 && !more) || (delta < 0 && page === 0)) return
    page += delta
    refresh()
  }
  function refresh() {
    revision++
    items = []
    more = false
    message = ""
    loading = true
    debounce.restart()
  }
  function fetch() {
    if (!active || request.running) return
    requestedRevision = revision
    body = ""
    bodyDone = false
    exitCode = -1
    request.command = Gifs.searchArgv(term, page)
    request.running = true
  }
  function finish() {
    if (!bodyDone || exitCode < 0) return
    if (!active) return
    if (requestedRevision !== revision) { debounce.restart(); return }
    loading = false
    try {
      if (exitCode !== 0) throw new Error("Could not reach GIPHY. Check your connection and retry.")
      var result = Gifs.parse(body)
      items = result.items
      more = result.more
      message = items.length ? "" : "No GIFs found. Try another search."
    } catch (error) { message = error.message }
  }
  function dismiss() {
    active = false
    revision++
    debounce.stop()
    items = []
    loading = false
  }

  readonly property Process clipboard: Process {
    stdout: StdioCollector { onStreamFinished: { root.copyBody = text; root.copyBodyDone = true; root.copied() } }
    onExited: function(code) { root.copyExit = code; root.copied() }
  }
  function copy(item, link) {
    if (!item || copying) return
    copying = true
    copySession = session
    message = link ? "Copying link..." : "Copying GIF..."
    copyBodyDone = false
    copyExit = -1
    copyBody = ""
    clipboard.command = ["python3", decodeURIComponent(String(Qt.resolvedUrl("bin/copy.py")).replace(/^file:\/\//, "")), link ? "link" : "gif", item.url]
    clipboard.running = true
  }
  function copied() {
    if (!copyBodyDone || copyExit < 0) return
    copying = false
    message = copyExit === 0 ? "Copied to clipboard" : (copyBody.trim() || "Could not copy to the clipboard")
    if (copyExit === 0 && active && copySession === session) copySucceeded()
  }
  Component.onDestruction: {
    debounce.stop()
    if (request.running) request.signal(15)
    if (clipboard.running) clipboard.signal(15)
  }
}
