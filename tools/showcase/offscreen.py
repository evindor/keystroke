#!/usr/bin/env python3
"""Capture the site's screenshots offscreen, never touching the desktop.

Two palettes run one after the other under Quickshell's offscreen platform,
scaled 4x so a 640x540 card becomes the 2560x2160 PNG the site expects:

- the real `Keystroke.qml` with every bundled provider and the shipped
  extensions, in a fake HOME (demo files for the file search, a demo
  clipboard history, `keystroke.json` with Timer and Translate on, the
  machine's current Omarchy theme linked in so the captures look like the
  desktop) and a fake PATH (`curl` answers the Translate extension from a
  table, `wl-paste` finds no selection) and a fake OMARCHY_PATH whose
  `omarchy-menu-keybindings` prints demo binds. Everything on screen is what
  the providers compute; nothing here draws rows by hand.
- the fixture palette `prepare.py` builds (stubbed registry, voice and Codex
  session) for the three staged states the real one cannot reach offline:
  the Applications list, a Codex conversation and a live voice recording.

The Timer's countdown in the bar is the real `BarWidget.qml` in a bar-sized
window against a fake bar, saved as `bar-timer.png`.

    python3 tools/showcase/offscreen.py            # every scene
    python3 tools/showcase/offscreen.py commands help   # a few by name

Output: site/assets/screenshots/<name>.png. Review the PNGs before publishing.
"""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "site/assets/screenshots"
WANTED = set(sys.argv[1:])

CONFIG = {"version": 1, "palette": {"accent": "ember", "density": "compact", "animations": "off"}, "matching": {"mode": "off"},
          "providers": {"timer": {"enabled": True}, "translate": {"enabled": True}, "hotkeys": {"limit": 5}}}
CONFIG_TRANSLATE_OFF = json.loads(json.dumps(CONFIG))
CONFIG_TRANSLATE_OFF["providers"]["translate"] = {"enabled": False}
# Smart Match at its default, for its settings screen only: no query is run
# while it is on, so the engine is never started and nothing is downloaded.
CONFIG_MATCHING = json.loads(json.dumps(CONFIG))
CONFIG_MATCHING["matching"] = {"mode": "text"}

# The real palette: what to open, what to do, then a grab of the card.
REAL = [
    dict(name="root", open={"query": ""}),
    dict(name="calculator", open={"query": "sqrt(144) + 15% of 80"}),
    dict(name="converter", open={"query": "72 F to C"}),
    dict(name="units", open={"query": "5 miles in kilometers"}),
    dict(name="timezone", open={"query": "10 am in London"}),
    dict(name="colors", open={"query": "#ff6644"}),
    dict(name="emoji", open={"query": ":rocket"}),
    dict(name="clipboard", open={"scope": "clipboard", "title": "Clipboard"}),
    dict(name="files", open={"query": "readme"}, wait=1500),
    dict(name="files-tilde", open={"query": "~dcmnts rpt"}, wait=1500),
    dict(name="fuzzy", open={"query": "prefcla"}),
    dict(name="hotkeys", open={"scope": "hotkeys", "title": "Hotkeys"}, wait=1500),
    dict(name="hotkeys-search", open={"query": "flcrn"}, wait=1500),
    dict(name="shortcuts", open={"query": ""}, steps=[{"ctrl": True}]),
    dict(name="ai", open={"query": "explain hyprland workspaces"}),
    dict(name="commands", open={"query": "timer "}),
    dict(name="help", open={"query": "/"}),
    dict(name="suggest", open={"query": "transl"}),
    dict(name="translate", open={"query": "tr bonjour"}, wait=1800),
    dict(name="translate-view", open={"query": "tr bonjour"}, wait=1800, steps=[{"activate": "Open in the editor", "wait": 800}], view=True),
    dict(name="extensions", open={"scope": "extensions", "title": "Extensions"}),
    dict(name="extension-detail", open={"scope": "extensions/timer", "title": "Timer"}),
    dict(name="settings", open={"scope": "settings", "title": "Keystroke Settings"}),
    dict(name="appearance", open={"scope": "settings/palette", "title": "Appearance"}),
    dict(name="omarchy", open={"menu": "system"}),
    dict(name="confirm", open={"menu": "system"}, steps=[{"activate": "Shutdown", "wait": 400}], confirm=True),
    dict(name="dictation", open={"scope": "dictation", "title": "Dictate to Clipboard", "query": "Build something worth sharing."}),
    dict(name="timer", open={"query": "timer 25m focus"}),
    dict(name="timers", open={"query": ""}, steps=[{"startTimer": {"seconds": 1500, "label": "focus"}}, {"startTimer": {"seconds": 3600, "label": "bread"}},
                                                  {"open": {"scope": "timer", "title": "Timers"}, "wait": 600}], bar="bar-timer"),
    dict(name="matching", open={"scope": "settings/palette", "title": "Appearance"}, steps=[{"config": CONFIG_MATCHING, "wait": 600},
                                                                                          {"open": {"scope": "settings/matching", "title": "Matching"}, "wait": 600}]),
    dict(name="confirm-extension", open={"query": ""}, steps=[{"config": CONFIG_TRANSLATE_OFF, "wait": 600},
                                                             {"open": {"scope": "extensions/translate", "title": "Translate"}, "wait": 600},
                                                             {"activate": "Enabled", "wait": 400}], confirm=True),
]
FIXTURE = ["apps", "codex", "voice"]

RUNNER = '''import QtQuick
import Quickshell
import qs.Commons
import "%(project)s"
ShellRoot {
 id: test
 property var scenes: %(scenes)s
 property int index: 0
 property int step: -1
 property bool busy: false
 property double settleUntil: 0
 property double sceneStart: 0
 function indexOf(title) { for (var i = 0; i < palette.rows.length; i++) if (palette.rows[i].title === title) return i; console.log("no row", title, "in", palette.rows.map(function(r) { return r.title }).join(" | ")); return -1 }
 function settle(ms) { test.settleUntil = Date.now() + (ms || 300) }
 Keystroke { id: palette; omarchyPath: "%(omarchy)s" }
 %(bar)s
 function grab(item, name, done) {
   test.busy = true
   item.grabToImage(function(r) { r.saveToFile("%(out)s/" + name + ".png"); console.log("captured", name); test.busy = false; done() })
 }
 function ready(scene) {
   if (palette.pending) return false
   if (palette.providerViewActive || palette.confirmPending) return true
   return palette.rows.length > 0 || Date.now() - test.sceneStart > 4000
 }
 function run(s) {
   if (s.open !== undefined) { palette.cancel(); palette.open(JSON.stringify(s.open)) }
   if (s.query !== undefined) palette.setQuery(s.query)
   if (s.select !== undefined) palette.selected = test.indexOf(s.select)
   if (s.activate !== undefined) palette.activateAt(test.indexOf(s.activate))
   if (s.ctrl !== undefined) palette.ctrlHeld = !!s.ctrl
   if (s.config !== undefined) palette.applyConfigText(JSON.stringify(s.config))
   if (s.startTimer !== undefined) {
     var svc = palette.registry.services["timer"].instance
     svc.activate({ action: { type: "timer-start", seconds: s.startTimer.seconds, label: s.startTimer.label } }, { host: palette, settings: palette.providerSettings("timer"), alternate: false })
   }
   test.settle(s.wait)
 }
 Timer { interval: 50; repeat: true; running: true; onTriggered: {
   if (test.busy || Date.now() < test.settleUntil) return
   var scene = test.scenes[test.index]
   if (!scene) { console.log("DONE"); Qt.quit(); return }
   if (test.step === -1) {
     if (%(guard)s) return
     test.sceneStart = Date.now()
     palette.open(JSON.stringify(scene.open))
     test.step = 0; test.settle(scene.wait || 400); return
   }
   if (!test.ready(scene)) return
   var steps = scene.steps || []
   if (test.step < steps.length) { test.run(steps[test.step]); test.step++; return }
   if (scene.view && !palette.providerViewActive) { console.log("FAIL no view for", scene.name); }
   if (scene.confirm && !palette.confirmPending) { console.log("FAIL no confirmation for", scene.name); }
   test.grab(palette.showcaseCard, scene.name, function() {
     var finish = function() { palette.ctrlHeld = false; palette.cancel(); test.index++; test.step = -1; test.settle(300) }
     if (scene.bar && typeof barWindow !== "undefined") test.grab(barWindow.contentItem, scene.bar, finish); else finish()
   })
 } }
 Timer { interval: 180000; running: true; onTriggered: { console.log("FAIL timeout in scene", test.index, test.step); Qt.quit() } }
}
'''

BAR = '''QtObject { id: paletteLoader; property var item: palette }
 QtObject { id: fakeShell; property var panelLoaders: ({ "evindor.keystroke": paletteLoader }) }
 QtObject {
   id: fakeBar
   property var shell: fakeShell
   property string fontFamily: Style.font.family
   property color barForeground: Color.bar.text
   property color urgent: Color.urgent
   property bool vertical: false
   property int barSize: Style.bar.sizeHorizontal
   property bool foregroundAnimationEnabled: false
   function run(cmd) { }
   function hideTooltip(item) { }
   function showTooltip(item, text) { }
   function registerClickTarget(item) { }
   function unregisterClickTarget(item) { }
   function moduleWidgets(id) { return [widget] }
 }
 Window { id: barWindow; visible: true; width: 200; height: Style.bar.sizeHorizontal; color: Color.bar.background
   BarWidget { id: widget; bar: fakeBar; x: 8 } }'''


def patch_settings_path(project, home):
    """The Settings screen names the config file; show it under ~ rather than the harness folder."""
    tree = project / "core/SettingsTree.js"
    js = tree.read_text()
    needle = 'subtitle: String(model.configPath || "")'
    assert needle in js, "configPath row not found"
    tree.write_text(js.replace(needle, 'subtitle: String(model.configPath || "").replace(%s, "~")' % json.dumps(str(home))))


def patch_palette(source):
    qml = source.read_text()
    qml = qml.replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    qml = qml.replace("  function inspect() {", "  readonly property var showcaseCard: card\n  function inspect() {", 1)
    assert "showcaseCard" in qml, "inspect() anchor not found"
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))


def script(folder, name, body):
    p = folder / name
    p.write_text(body)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


def fake_home(work):
    home = work / "home"
    (home / ".config/omarchy").mkdir(parents=True)
    (home / ".config/omarchy/keystroke.json").write_text(json.dumps(CONFIG))
    state = home / ".local/state/omarchy"
    state.mkdir(parents=True)
    current = Path.home() / ".local/state/omarchy/current"
    if current.exists():   # the theme the desktop shows right now, read-only
        (state / "current").symlink_to(current)
    (state / "clipboard-history.json").write_text(json.dumps([
        "Build something worth sharing.", "https://omarchy.org", "omarchy plugin list", "#ff6644", "Remember to take a break."]))
    fontconfig = Path.home() / ".config/fontconfig/fonts.conf"
    if fontconfig.exists():
        (home / ".config/fontconfig").mkdir(parents=True)
        (home / ".config/fontconfig/fonts.conf").symlink_to(fontconfig)
    for rel in ("Projects/keystroke/README.md", "Projects/weekend-app/README.md", "Projects/dotfiles/README.md", "Documents/notes/README.md",
                "Documents/reports/quarterly-report.md", "Documents/reports/trip-report.md", "Documents/report-draft.md",
                "Downloads/omarchy-wallpaper.jpg", "Pictures/Screenshots/.keep"):
        p = home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# " + p.stem + "\n")
    return home


def fake_path(work):
    fake = work / "bin"
    fake.mkdir()
    script(fake, "curl", '''#!/usr/bin/env python3
import json, sys, urllib.parse
args = sys.argv[1:]
url = args[-1]
text = None
if "--data-urlencode" in args: text = args[args.index("--data-urlencode") + 1][2:]
qs = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
tl = qs.get("tl", [""])[0]
if text is None: text = qs.get("q", [""])[0]
table = {("bonjour", "en"): "Hello", ("Hello", "fr"): "Bonjour", ("bonjour", "fr"): "bonjour"}
detected = "fr" if text.lower().startswith("bonjour") else "en"
out = table.get((text, tl)) or (text if tl == detected else tl + ":" + text)
body = json.dumps([[[out, text, None, None, 10]], None, detected, None, None, None, 1, [], [[detected], None, [1], [detected]]], ensure_ascii=False)
sys.stdout.write(body + "\\n__STATUS__200")
''')
    script(fake, "wl-paste", "#!/bin/sh\nexit 1\n")
    script(fake, "wl-copy", "#!/bin/sh\nexit 0\n")
    script(fake, "wtype", "#!/bin/sh\nexit 0\n")
    script(fake, "pw-play", "#!/bin/sh\nexit 0\n")
    return fake


def fake_omarchy(work):
    """OMARCHY_PATH with the real tree, except a keybindings script that prints demo binds."""
    real = Path("/usr/share/omarchy")
    fake = work / "omarchy"
    fake.mkdir()
    for entry in real.iterdir():
        if entry.name != "bin":
            (fake / entry.name).symlink_to(entry)
    (fake / "bin").mkdir()
    for entry in (real / "bin").iterdir():
        if entry.name != "omarchy-menu-keybindings":
            (fake / "bin" / entry.name).symlink_to(entry)
    records = [
        ("SUPER + RETURN", "Terminal", "exec", "xdg-terminal-exec"),
        ("SUPER + B", "Browser", "exec", "omarchy-launch-browser"),
        ("SUPER + SPACE", "Keystroke", "exec", "omarchy-shell shell toggle omarchy.menu"),
        ("SUPER + F", "Full screen", "lua", "hl.dsp.window.fullscreen({ mode = \"fullscreen\" })"),
        ("SUPER + W", "Close window", "", ""),
        ("SUPER + T", "Toggle floating", "lua", "hl.dsp.window.float()"),
        ("SUPER SHIFT + S", "Screenshot region", "exec", "omarchy-capture-screenshot region"),
        ("SUPER SHIFT + R", "Record screen", "exec", "omarchy-capture-screenrecord"),
        ("SUPER CTRL + L", "Lock screen", "exec", "omarchy-lock-screen"),
        ("SUPER + 1", "Workspace 1", "lua", "hl.dsp.workspace.go(1)"),
        ("SUPER SHIFT + SPACE", "Next background", "exec", "omarchy-theme-bg-next"),
        ("SUPER + K", "Keybindings", "exec", "omarchy-menu-keybindings"),
    ]
    lines = "".join("  printf '%%s\\t%%s\\t%%s\\n' '%-36s→ %s' '%s' '%s'\n" % (combo, label, dispatcher, arg.replace("'", "'\\''"))
                    for combo, label, dispatcher, arg in records)
    script(fake / "bin", "omarchy-menu-keybindings", "#!/bin/bash\n# Demo binds for the screenshot harness; the real script lists the user's own.\n"
           "output_binding_records() {\n" + lines + "}\ndispatch_binding() { :; }\n")
    return fake


def run_quickshell(work, shell, env):
    result = subprocess.run(["quickshell", "-p", str(shell)], env=env, capture_output=True, text=True, timeout=240)
    output = result.stdout + result.stderr
    if os.environ.get("KEYSTROKE_SHOWCASE_DEBUG"): sys.stderr.write(output)
    captured = [line.split("captured ", 1)[1].strip() for line in output.splitlines() if "captured " in line]
    fails = [line for line in output.splitlines() if "FAIL" in line or "TypeError" in line or "ReferenceError" in line or "no row " in line]
    return captured, fails, output


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="keystroke-showcase-") as temp:
        work = Path(temp)
        project = work / "project"
        shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "site", "__pycache__", "experiments", "docs"))
        (work / "qs").symlink_to("/usr/share/omarchy/shell")
        patch_palette(project / "Keystroke.qml")
        home = fake_home(work)
        patch_settings_path(project, home)
        fake = fake_path(work)
        omarchy = fake_omarchy(work)
        env = dict(os.environ, HOME=str(home), XDG_RUNTIME_DIR=str(work), OMARCHY_PATH=str(omarchy), PATH=f"{fake}:{os.environ.get('PATH', '')}",
                   QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QT_SCALE_FACTOR="4", QML_IMPORT_PATH=str(work))
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)

        real = [s for s in REAL if not WANTED or s["name"] in WANTED]
        captured, fails = [], []
        if real:
            (work / "real.qml").write_text(RUNNER % dict(project="project", scenes=json.dumps(real), omarchy=str(omarchy), out=str(OUT), bar=BAR,
                                                          guard='!palette.registry.services["timer"] || !palette.registry.services["timer"].instance || !palette.registry.services["translate"] || !palette.registry.services["translate"].instance'))
            c, f, output = run_quickshell(work, work / "real.qml", env)
            captured += c; fails += f
            if "DONE" not in output: fails.append("real palette did not finish:\n" + output[-3000:])

        fixture = [name for name in FIXTURE if not WANTED or name in WANTED]
        if fixture:
            dest = work / "fixture"
            subprocess.run([sys.executable, str(ROOT / "tools/showcase/prepare.py")], check=True, capture_output=True,
                           env=dict(os.environ, KEYSTROKE_SHOWCASE_DEST=str(dest), KEYSTROKE_SHOWCASE_HOME=str(home)))
            fixtures_json = work / "fixtures.json"
            subprocess.run([sys.executable, str(ROOT / "tools/showcase/fixtures.py")], check=True, capture_output=True,
                           env=dict(os.environ, KEYSTROKE_SHOWCASE_FIXTURES=str(fixtures_json)))
            payloads = json.loads(fixtures_json.read_text())
            patch_palette(dest / "Keystroke.qml")
            scenes = [dict(name=name, open=payloads[name], wait=600) for name in fixture]
            (work / "fixture.qml").write_text(RUNNER % dict(project="fixture", scenes=json.dumps(scenes, ensure_ascii=False), omarchy=str(omarchy), out=str(OUT), bar="", guard="false"))
            c, f, output = run_quickshell(work, work / "fixture.qml", env)
            captured += c; fails += f
            if "DONE" not in output: fails.append("fixture palette did not finish:\n" + output[-3000:])

    for name in captured:
        png = OUT / (name + ".png")
        head = png.read_bytes()[:24]
        width, height = int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
        print(f"{name}.png {width}x{height}")
        if not name.startswith("bar-") and (width, height) != (2560, 2160): fails.append(f"{name}.png is {width}x{height}, not 2560x2160")
    if fails:
        raise SystemExit("\n".join(fails))
    print(f"PASS: {len(captured)} screenshots in {OUT}")


if __name__ == "__main__":
    main()
