#!/usr/bin/env python3
"""Exercise the real palette with isolated HOME, a local GIPHY and fake clipboard."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

KEY = "abcdef0123456789abcdef0123456789"
REQUESTS = []
KEYS_SEEN = set()
RATINGS_SEEN = set()


def gif(index, term):
    return {"id": str(index), "title": term + " " + str(index),
            "images": {"original": {"url": "https://media.giphy.com/" + str(index) + ".gif"},
                       "preview_gif": {"url": "https://media.giphy.com/small.gif"}}}


class Giphy(BaseHTTPRequestHandler):
    def do_GET(self):
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        term = query.get("q", ["trending"])[0]
        offset = int(query.get("offset", ["0"])[0])
        REQUESTS.append("%s:%d" % (term, offset))
        KEYS_SEEN.add(query.get("api_key", [""])[0])
        RATINGS_SEEN.add(query.get("rating", [""])[0])
        if term == "slow":
            time.sleep(0.7)
        status = 500 if term == "error" else 429 if term == "ratelimit" else 200
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if status != 200:
            self.wfile.write(json.dumps({"meta": {"status": status}}).encode())
            return
        data = [] if term == "empty" else [gif(offset + i, term) for i in range(24)]
        self.wfile.write(json.dumps({"data": data,
                                     "pagination": {"offset": offset, "count": 24, "total_count": 48}}).encode())

    def log_message(self, *args):
        pass


root = Path(__file__).resolve().parents[3]
server = ThreadingHTTPServer(("127.0.0.1", 0), Giphy)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d/v1/gifs/" % server.server_address[1]

with tempfile.TemporaryDirectory(prefix="keystroke-gifs-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__", "experiments"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text().replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))
    # Local preview avoids any media requests during the offscreen test.
    preview = work / "preview.gif"
    preview.write_bytes(base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"))
    if os.environ.get("KEYSTROKE_GIF_PREVIEW"):
        shutil.copyfile(os.environ["KEYSTROKE_GIF_PREVIEW"], preview)
    view = project / "extensions/gif-search/GifView.qml"
    view.write_text(view.read_text().replace("source: tile.modelData.preview", "source: " + json.dumps(preview.as_uri())))
    helper = project / "extensions/gif-search/bin/copy.py"
    helper.write_text(helper.read_text().replace("import subprocess", "import subprocess\nimport io").replace(
        "urllib.request.build_opener(MediaRedirect).open(url, timeout=20)",
        'type("Fixture", (io.BytesIO,), {"headers": {}})(b"GIF89a\\x00\\xff")'))
    fake = work / "bin"
    fake.mkdir()
    wl = fake / "wl-copy"
    wl.write_text("#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\nPath(" + repr(str(work / "copied")) + ").write_bytes(sys.stdin.buffer.read())\n")
    wl.chmod(0o755)
    (work / ".config/omarchy").mkdir(parents=True)
    (work / ".config/omarchy/keystroke.json").write_text('{"version":1,"matching":{"mode":"off"}}')
    capture = os.environ.get("KEYSTROKE_CAPTURE_DIR", "")
    if capture:
        Path(capture).mkdir(parents=True, exist_ok=True)
    (work / "shell.qml").write_text('''import QtQuick
import QtTest
import Quickshell
import "project"
ShellRoot {
 id: test
 property int stage: 0
 property int ticks: 0
 property int failures: 0
 property var svc: null
 property var input: null
 property var grid: null
 property string key: ''' + json.dumps(KEY) + '''
 property TestCase keyboard: TestCase { when: false }
 function find(object, name) {
   if (object.objectName === name) return object
   var children = object.children || []
   for (var i = 0; i < children.length; i++) { var found = find(children[i], name); if (found) return found }
   return null
 }
 function check(ok, message) { if (!ok) { failures++; console.log("FAIL", message) } }
 function config(enabled, apiKey) {
   return JSON.stringify({version:1, matching:{mode:"off"},
     providers:{"gif-search":{enabled:enabled, prefix:"reaction", apiKey:apiKey, rating:"pg-13"}}})
 }
 // The view reads settings once, at activate; keep the key when overriding.
 function withKey(extra) {
   var out = { apiKey: test.key, rating: "pg-13" }
   for (var k in extra) out[k] = extra[k]
   return out
 }
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 Timer { interval: 100; repeat: true; running: true; onTriggered: {
   switch (test.stage) {
   case 0:
     if (!palette.registry.manifests["gif-search"]) return
     check(!palette.registry.services["gif-search"], "off by default")
     palette.applyConfigText(config(true, "")); test.stage++; return
   case 1:
     var entry = palette.registry.services["gif-search"]
     if (!entry || !entry.instance) return
     test.svc = entry.instance
     palette.open(JSON.stringify({query:"reaction happy"})); test.stage++; return
   case 2:
     var noKey = palette.rows.findIndex(function(r) { return r.id === "gif-search-open" })
     if (noKey < 0) return
     check(palette.rows[noKey].verb === "Set up", "root row asks for setup while the key is missing")
     palette.activateAt(noKey); test.stage++; return
   case 3:
     if (!palette.providerViewActive) return
     check(svc.needsKey && !svc.loading, "the view knows the key is missing")
     check(!svc.items.length, "nothing is searched without a key")
     palette.cancel()
     palette.applyConfigText(config(true, test.key))
     palette.open(JSON.stringify({query:"reaction happy"})); test.stage++; return
   case 4:
     var index = palette.rows.findIndex(function(r) { return r.id === "gif-search-open" })
     if (index < 0) return
     check(palette.rows[index].action.term === "happy", "renamed command seeds term")
     palette.activateAt(index); test.stage++; return
   case 5:
     if (svc.loading || !svc.items.length || !palette.providerViewActive) return
     check(!svc.needsKey, "the key from settings reaches the service")
     check(svc.request.command.join(" ").indexOf(test.key) === -1, "the key never enters argv")
     for (var n = 0; n < palette.resources.length; n++) {
       var window = palette.resources[n]
       if (window && window.contentItem) {
         test.input = find(window.contentItem, "gifSearchInput")
         test.grid = find(window.contentItem, "gifSearchGrid")
       }
     }
     check(!!test.input && !!test.grid, "view controls loaded")
     test.input.cursorPosition = 1
     keyboard.keyClick(Qt.Key_Right)
     check(test.input.activeFocus && test.input.cursorPosition === 2, "Right inside text edits normally")
     test.input.cursorPosition = test.input.text.length
     keyboard.keyClick(Qt.Key_Right, Qt.ShiftModifier)
     check(test.input.activeFocus, "modified Right stays in search")
     keyboard.keyClick(Qt.Key_Right)
     check(test.grid.activeFocus && test.grid.currentIndex === 1, "Right at end enters grid and advances")
     keyboard.keyClick(Qt.Key_Tab)
     test.grid.currentIndex = 0
     keyboard.keyClick(Qt.Key_Tab)
     keyboard.keyClick(Qt.Key_Right)
     check(test.grid.currentIndex === 1, "Tab then Right selects second GIF")
     keyboard.keyClick(Qt.Key_Down)
     check(test.grid.currentIndex === 4, "Down selects next row")
     keyboard.keyClick(Qt.Key_Tab)
     check(test.input.activeFocus, "Tab returns to search")
     check(svc.items[0].title === "happy 0", "initial search results")
     check(svc.more, "next page available")
     svc.turnPage(1); test.stage++; return
   case 6:
     if (svc.loading) return
     check(svc.items[0].id === "24" && !svc.more, "second page offset")
     svc.search("slow"); test.stage++; return
   case 7:
     if (++test.ticks < 4) return
     svc.search("new"); test.stage++; return
   case 8:
     if (svc.loading) return
     check(svc.items[0].title === "new 0", "stale response ignored")
     keyboard.keyClick(Qt.Key_Return, Qt.ControlModifier); test.stage++; return
   case 9:
     if (svc.copying) return
     check(svc.message === "Copied to clipboard", "copy link succeeded")
     check(palette.opened && svc.settings.defaultAction === "image" && !svc.settings.closeAfterCopy, "defaults keep view open")
     svc.settings = withKey({ defaultAction: "link", closeAfterCopy: false })
     keyboard.keyClick(Qt.Key_Return)
     check(svc.clipboard.command[2] === "link", "Enter uses link default")
     test.stage = 91; return
   case 91:
     if (svc.copying) return
     keyboard.keyClick(Qt.Key_Return, Qt.ControlModifier)
     check(svc.clipboard.command[2] === "gif", "Ctrl+Enter swaps to GIF")
     test.stage = 92; return
   case 92:
     if (svc.copying) return
     check(svc.message === "Copied to clipboard" && palette.opened, "image copy keeps view open")
     svc.search("error"); test.stage++; return
   case 93:
     if (svc.loading) return
     check(svc.items.length === 0 && svc.message.indexOf("HTTP 500") !== -1, "the helper's own error message is shown")
     svc.search("ratelimit"); test.stage = 94; return
   case 94:
     if (svc.loading) return
     check(svc.message.indexOf("rate limit reached") !== -1, "a 429 names the rate limit")
     svc.search("empty"); test.stage = 10; return
   case 10:
     if (svc.loading) return
     check(svc.items.length === 0 && svc.message.indexOf("No GIFs") === 0, "empty state")
     svc.search(""); test.stage++; return
   case 11:
     if (svc.loading) return
     check(svc.items[0].title === "trending 0", "trending")
     svc.search("new"); test.stage = 111; return
   case 111:
     if (svc.loading) return
     check(svc.items[0].title === "new 0", "a page already fetched is served from the cache")
     test.input.text = ""
     test.ticks = 0; test.stage = 12; return
   case 12:
     if (++test.ticks < 5) return
     var captureDir = ''' + json.dumps(capture) + '''
     if (captureDir) {
       for (var i = 0; i < palette.resources.length; i++) {
         var win = palette.resources[i]
         if (win && win.contentItem) win.contentItem.grabToImage(function(result) { result.saveToFile(captureDir + "/grid.png") })
       }
     }
     test.stage++; return
   case 13:
     svc.settings = withKey({ defaultAction: "link", closeAfterCopy: true })
     svc.copyBodyDone = true; svc.copyExit = 1; svc.copyBody = "Copy failed"
     svc.copied()
     check(palette.opened, "failed copy never closes")
     keyboard.keyClick(Qt.Key_Return)
     test.stage = 131; return
   case 131:
     if (svc.copying) return
     check(!palette.opened, "successful copy closes when enabled")
     check(!svc.active && !svc.items.length, "dismiss releases previews")
     palette.applyConfigText(config(false, test.key)); test.stage = 14; return
   case 14:
     if (palette.registry.services["gif-search"]) return
     console.log(test.failures ? "FAIL palette gifs" : "PASS palette gifs")
     Qt.quit(); test.stage++; return
   }
 } }
 Timer { interval: 25000; running: true; onTriggered: { console.log("FAIL timeout", test.stage, JSON.stringify(palette.registry.problems)); Qt.quit() } }
}
''')
    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), PATH=f"{fake}:{os.environ.get('PATH', '')}",
               GIPHY_API_BASE=base,
               QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("GIPHY_API_KEY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr
    assert "PASS palette gifs" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output and "Unable to assign" not in output, output
    assert (work / "copied").read_bytes() == b"https://media.giphy.com/0.gif"
    expected = ['happy:0', 'happy:24', 'slow:0', 'new:0', 'error:0', 'ratelimit:0', 'empty:0', 'trending:0']
    assert REQUESTS == expected, REQUESTS
    # The key travelled in the environment and arrived intact; the rating was honoured.
    assert KEYS_SEEN == {KEY}, KEYS_SEEN
    assert RATINGS_SEEN == {"pg-13"}, RATINGS_SEEN
    print("PASS real palette: setup without a key, key from settings, renamed command, view, paging, "
          "stale response, clipboard, HTTP and rate-limit errors, empty, trending, cache, dismiss, disable")
