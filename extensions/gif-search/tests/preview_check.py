#!/usr/bin/env python3
"""Exercise real GIF previews with a sequential stream, no network or clipboard."""
import base64
import ctypes
import json
import os
from pathlib import Path
import resource
import struct
import subprocess
import tempfile

extension = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 240, 100  # the shape of a 16:9-ish GIPHY fixed_height_small preview


def frame(index):
    # One solid frame, LZW-coded without compression: a clear code before every
    # pair of pixels keeps the code width at 3 bits, so no table logic is needed.
    codes = []
    for i in range(WIDTH * HEIGHT):
        if i % 2 == 0:
            codes.append(4)
        codes.append(index)
    codes.append(5)
    bits = sum(code << (3 * i) for i, code in enumerate(codes))
    data = bits.to_bytes((3 * len(codes) + 7) // 8, "little")
    blocks = b"".join(bytes([len(data[i:i + 255])]) + data[i:i + 255] for i in range(0, len(data), 255))
    return (bytes.fromhex("21f904000a000000") + b"\x2c" + struct.pack("<4HB", 0, 0, WIDTH, HEIGHT, 0)
            + b"\x02" + blocks + b"\x00")


# Two 100 ms frames, no GIF loop extension: Qt must restart the sequential stream.
gif = (b"GIF89a" + struct.pack("<2H3B", WIDTH, HEIGHT, 0x80, 0, 0) + bytes.fromhex("000000ffffff")
       + frame(0) + frame(1) + b"\x3b")
url = "data:image/gif;base64," + base64.b64encode(gif).decode()
libc = ctypes.CDLL(None)


def no_core():
    # The unfixed Qt 6.12 path overflows its stack; never collect a core in tests.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if libc.prctl(4, 0, 0, 0, 0) != 0:  # Linux PR_SET_DUMPABLE
        os._exit(2)


with tempfile.TemporaryDirectory(prefix="keystroke-gif-preview-") as temp:
    work = Path(temp)
    shell = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")) / "shell"
    (work / "qs").symlink_to(shell)
    view = (extension / "GifView.qml").read_text()
    # Observe the actual preview without replacing its source or playback logic.
    assert view.count("id: preview") == 1
    view = view.replace("id: preview", """id: preview
              objectName: "testGifPreview"
              property int testFrameChanges: 0
              onCurrentFrameChanged: testFrameChanges++""", 1)
    (work / "GifView.qml").write_text(view)
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
  id: test
  property int stage: 0
  property int ticks: 0
  property var firstPreview: null
  function check(ok, message) { if (!ok) { console.log("FAIL", message); Qt.exit(1) } }
  function find(node, name, list) {
    if (node.objectName === name) list.push(node)
    var children = node.children || []
    for (var i = 0; i < children.length; i++) find(children[i], name, list)
    return list
  }
  function advance() { stage++; ticks = 0 }
  QtObject {
    id: service
    property bool active: true
    property string term: "fixture"
    property var settings: ({defaultAction: "image", closeAfterCopy: false})
    property var items: Array.from({length: 24}, function(_, i) {
      return {title: "GIF " + i, preview: __URL__}
    })
    property bool loading: false
    property int page: 0
    property bool more: false
    property string message: ""
    signal copySucceeded()
    function search(text) {}
    function dismiss() { active = false; items = [] }
    function copy(item, link) {}
    function turnPage(delta) {}
    function refresh() {}
  }
  Window {
    width: 640; height: 480; visible: true
    GifView { id: view; anchors.fill: parent; service: service }
  }
  Timer {
    interval: 100; running: true; repeat: true
    onTriggered: {
      test.ticks++
      var previews = test.find(view, "testGifPreview", [])
      var loaded = previews.filter(function(p) { return String(p.source).length > 0 })
      switch (test.stage) {
      case 0:
        // Qt 6.12 restarts a GIF without a loop extension; 6.11 plays it once
        // and stops. Either way the stream must end without crashing.
        if (!loaded.length || loaded[0].frameCount !== 2) return
        if (loaded[0].testFrameChanges < 8 && (loaded[0].playing || test.ticks < 10)) return
        test.check(loaded.length < 24, "only visible previews are loaded")
        loaded.forEach(function(p) {
          test.check(p.status === Image.Ready && p.cache, "GIF decoded and cached")
          test.check(p.implicitWidth === __WIDTH__ && p.implicitHeight === __HEIGHT__,
            "frames decoded at the GIF's own size and shape: " + p.implicitWidth + "x" + p.implicitHeight)
        })
        test.firstPreview = loaded[0]
        test.find(view, "gifSearchGrid", [])[0].positionViewAtIndex(23, GridView.End)
        test.advance(); return
      case 1:
        if (test.ticks < 3) return
        test.check(!test.firstPreview || String(test.firstPreview.source) === "", "scrolled-out preview released")
        test.check(loaded.length > 0 && loaded.length < 24, "new visible tiles load")
        service.active = false
        test.advance(); return
      case 2:
        if (test.ticks < 2) return
        test.check(loaded.length === 0, "inactive service releases every preview")
        view.visible = false; service.active = true
        test.advance(); return
      case 3:
        if (test.ticks < 2) return
        test.check(loaded.length === 0, "hidden view keeps previews unloaded")
        view.visible = true
        test.advance(); return
      case 4:
        if (!loaded.length || loaded.some(function(p) { return p.status !== Image.Ready })) return
        service.dismiss()
        test.advance(); return
      case 5:
        if (test.ticks < 2) return
        test.check(loaded.length === 0, "dismiss releases previews")
        console.log("PASS sequential GIF ends safely, frames at native size, scroll, hide, reopen, dismiss")
        Qt.quit()
      }
    }
  }
  Timer { interval: 15000; running: true; onTriggered: { console.log("FAIL timeout", test.stage); Qt.exit(1) } }
}
'''.replace("__URL__", json.dumps(url)).replace("__WIDTH__", str(WIDTH)).replace("__HEIGHT__", str(HEIGHT)))
    env = dict(os.environ, HOME=temp, XDG_CONFIG_HOME=str(work / ".config"),
               XDG_DATA_HOME=str(work / ".local/share"), XDG_STATE_HOME=str(work / ".local/state"),
               XDG_CACHE_HOME=str(work / ".cache"), XDG_RUNTIME_DIR=temp,
               QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic",
               QT_QUICK_BACKEND="software", QML_IMPORT_PATH=temp, QML_DISABLE_DISK_CACHE="1",
               QS_DISABLE_CRASH_HANDLER="1")
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
        env.pop(name, None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env,
                            capture_output=True, text=True, timeout=20, preexec_fn=no_core)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "PASS sequential GIF" in output and "FAIL" not in output, output + f"\nexit={result.returncode}"
    assert not any(error in output for error in ("TypeError", "ReferenceError", "Unable to assign")), output
    print("PASS sequential GIF ends safely, frames at native size, scroll, hide, reopen, dismiss")
