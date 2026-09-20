#!/usr/bin/env python3
"""Exercise the real palette with isolated HOME, fake network and clipboard."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[3]
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
    def script(name, body):
        path = fake / name
        path.write_text(body)
        path.chmod(0o755)
    script("curl", '''#!/usr/bin/env python3
import json, sys, time, urllib.parse
qs = urllib.parse.parse_qs(urllib.parse.urlsplit(sys.argv[-1]).query)
term = qs.get('q', ['trending'])[0]
offset = int(qs['offset'][0])
with open(''' + repr(str(work / "requests")) + ''', 'a') as out: out.write(term + ':' + str(offset) + '\\n')
if term == 'slow': time.sleep(0.7)
if term == 'error': sys.exit(22)
gif = lambda i: {'id': str(i), 'title': term + ' ' + str(i), 'images': {'original': {'url': 'https://media.giphy.com/' + str(i) + '.gif'}, 'preview_gif': {'url': 'https://media.giphy.com/small.gif'}}}
print(json.dumps({'data': [] if term == 'empty' else [gif(offset+i) for i in range(24)], 'pagination': {'offset':offset, 'count':24, 'total_count':48}}))
''')
    script("wl-copy", "#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\nPath(" + repr(str(work / "copied")) + ").write_bytes(sys.stdin.buffer.read())\n")
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
 property TestCase keyboard: TestCase { when: false }
 function find(object, name) {
   if (object.objectName === name) return object
   var children = object.children || []
   for (var i = 0; i < children.length; i++) { var found = find(children[i], name); if (found) return found }
   return null
 }
 function check(ok, message) { if (!ok) { failures++; console.log("FAIL", message) } }
 function config(enabled) { return JSON.stringify({version:1, matching:{mode:"off"}, providers:{"gif-search":{enabled:enabled, prefix:"reaction"}}}) }
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 Timer { interval: 100; repeat: true; running: true; onTriggered: {
   switch (test.stage) {
   case 0:
     if (!palette.registry.manifests["gif-search"]) return
     check(!palette.registry.services["gif-search"], "off by default")
     palette.applyConfigText(config(true)); test.stage++; return
   case 1:
     var entry = palette.registry.services["gif-search"]
     if (!entry || !entry.instance) return
     test.svc = entry.instance
     palette.open(JSON.stringify({query:"reaction happy"})); test.stage++; return
   case 2:
     var index = palette.rows.findIndex(function(r) { return r.id === "gif-search-open" })
     if (index < 0) return
     check(palette.rows[index].action.term === "happy", "renamed command seeds term")
     palette.activateAt(index); test.stage++; return
   case 3:
     if (svc.loading || !svc.items.length || !palette.providerViewActive) return
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
   case 4:
     if (svc.loading) return
     check(svc.items[0].id === "24" && !svc.more, "second page offset")
     svc.search("slow"); test.stage++; return
   case 5:
     if (++test.ticks < 4) return
     svc.search("new"); test.stage++; return
   case 6:
     if (svc.loading) return
     check(svc.items[0].title === "new 0", "stale response ignored")
     keyboard.keyClick(Qt.Key_Return, Qt.ControlModifier); test.stage++; return
   case 7:
     if (svc.copying) return
     check(svc.message === "Copied to clipboard", "copy link succeeded")
     check(palette.opened && svc.settings.defaultAction === "image" && !svc.settings.closeAfterCopy, "defaults keep view open")
     svc.settings = { defaultAction: "link", closeAfterCopy: false }
     keyboard.keyClick(Qt.Key_Return)
     check(svc.clipboard.command[2] === "link", "Enter uses link default")
     test.stage = 71; return
   case 71:
     if (svc.copying) return
     keyboard.keyClick(Qt.Key_Return, Qt.ControlModifier)
     check(svc.clipboard.command[2] === "gif", "Ctrl+Enter swaps to GIF")
     test.stage = 72; return
   case 72:
     if (svc.copying) return
     check(svc.message === "Copied to clipboard" && palette.opened, "image copy keeps view open")
     svc.search("error"); test.stage++; return
   case 73:
     test.stage = 8; return
   case 8:
     if (svc.loading) return
     check(svc.items.length === 0 && svc.message.indexOf("Could not reach") === 0, "request error visible")
     svc.search("empty"); test.stage++; return
   case 9:
     if (svc.loading) return
     check(svc.items.length === 0 && svc.message.indexOf("No GIFs") === 0, "empty state")
     svc.search(""); test.stage++; return
   case 10:
     if (svc.loading) return
     check(svc.items[0].title === "trending 0", "trending")
     test.input.text = ""
     test.ticks = 0; test.stage++; return
   case 11:
     if (++test.ticks < 5) return
     var captureDir = ''' + json.dumps(capture) + '''
     if (captureDir) {
       for (var i = 0; i < palette.resources.length; i++) {
         var win = palette.resources[i]
         if (win && win.contentItem) win.contentItem.grabToImage(function(result) { result.saveToFile(captureDir + "/grid.png") })
       }
     }
     test.stage++; return
   case 12:
     svc.settings = { defaultAction: "link", closeAfterCopy: true }
     svc.copyBodyDone = true; svc.copyExit = 1; svc.copyBody = "Copy failed"
     svc.copied()
     check(palette.opened, "failed copy never closes")
     keyboard.keyClick(Qt.Key_Return)
     test.stage = 121; return
   case 121:
     if (svc.copying) return
     check(!palette.opened, "successful copy closes when enabled")
     check(!svc.active && !svc.items.length, "dismiss releases previews")
     palette.applyConfigText(config(false)); test.stage = 13; return
   case 13:
     if (palette.registry.services["gif-search"]) return
     console.log(test.failures ? "FAIL palette gifs" : "PASS palette gifs")
     Qt.quit(); test.stage++; return
   }
 } }
 Timer { interval: 18000; running: true; onTriggered: { console.log("FAIL timeout", test.stage, JSON.stringify(palette.registry.problems)); Qt.quit() } }
}
''')
    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), PATH=f"{fake}:{os.environ.get('PATH', '')}",
               QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert "PASS palette gifs" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output and "Unable to assign" not in output, output
    assert (work / "copied").read_bytes() == b"https://media.giphy.com/0.gif"
    requests = (work / "requests").read_text().splitlines()
    assert requests == ['happy:0', 'happy:24', 'slow:0', 'new:0', 'error:0', 'empty:0', 'trending:0'], requests
    print("PASS real palette: enable, renamed command, view, paging, stale response, clipboard link, errors, empty, trending, dismiss, disable")
