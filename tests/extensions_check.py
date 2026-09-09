#!/usr/bin/env python3
"""Drive providers/Extensions.qml through Omarchy's real plugin scripts.

A fake HOME holds the plugin folder, a local bare git repository plays the
extension's upstream, a file:// index plays the Keystroke index, and a stub
`omarchy-shell` answers the IPC calls the scripts make (rescan, list).
Everything else is real: omarchy-plugin-add/update/remove/validate, git, curl,
and the plugin-folder scan the registry uses (core/Extensions.js scanArgv and
parseScan) stands in for providers/Registry.qml. The harness installs, checks
for updates, updates, toggles, and removes the extension through the
provider's own query()/activate() entry points.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
PLUGIN_ID = "test.keystroke-probe"


def sh(cmd, cwd=None, env=None):
    subprocess.run(cmd, cwd=cwd, env=env, check=True, text=True, capture_output=True)


with tempfile.TemporaryDirectory(prefix="keystroke-extensions-") as temp:
    work = Path(temp)
    home = work / "home"
    plugins = home / ".config/omarchy/plugins"
    plugins.mkdir(parents=True)
    (home / ".cache/keystroke").mkdir(parents=True)
    (home / ".config/omarchy/keystroke.json").write_text('{"version": 1, "providers": {}}\n')

    # The project, with the qs module reachable as in tests/lint.sh.
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__", "experiments"))
    for name, target in [("qs", "/usr/share/omarchy/shell"), ("Commons", "/usr/share/omarchy/shell/Commons"), ("Ui", "/usr/share/omarchy/shell/Ui")]:
        (work / name).symlink_to(target)

    # Upstream: a bare repository with one commit of a minimal extension.
    upstream = work / "probe.git"
    src = work / "probe-src"
    src.mkdir()
    (src / "manifest.json").write_text(json.dumps({
        "schemaVersion": 1, "id": PLUGIN_ID, "name": "Probe", "version": "1.0.0", "author": "Test", "license": "MIT",
        "description": "Probe extension", "kinds": ["service"], "keepLoaded": True,
        "entryPoints": {"service": "Service.qml"}, "x-keystroke": {"apiVersion": 1}}, indent=2))
    (src / "Service.qml").write_text('import QtQuick\nQtObject { readonly property var provider: ({ apiVersion: 1, name: "Probe", query: function(ctx) { return [] } }) }\n')
    (src / "README.md").write_text("# Probe\n")
    (src / "LICENSE").write_text("MIT\n")
    genv = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x", HOME=str(home))
    sh(["git", "init", "-q", "-b", "main"], cwd=src, env=genv)
    sh(["git", "add", "."], cwd=src, env=genv)
    sh(["git", "commit", "-q", "-m", "v1"], cwd=src, env=genv)
    sh(["git", "init", "-q", "--bare", "-b", "main", str(upstream)], env=genv)
    sh(["git", "push", "-q", str(upstream), "main"], cwd=src, env=genv)

    def bump(version):
        m = json.loads((src / "manifest.json").read_text())
        m["version"] = version
        (src / "manifest.json").write_text(json.dumps(m, indent=2))
        sh(["git", "commit", "-q", "-am", "v" + version], cwd=src, env=genv)
        sh(["git", "push", "-q", str(upstream), "main"], cwd=src, env=genv)

    # The index the provider fetches; the listed repo is never cloned here.
    index = work / "index.json"
    index.write_text(json.dumps({"version": 1, "extensions": [
        {"id": "example.keystroke-spotify", "name": "Spotify", "description": "Control Spotify", "author": "Example", "repo": "https://github.com/example/keystroke-spotify.git", "tags": ["media"]}]}))

    # Stub omarchy-shell: the plugin scripts talk to the shell over it.
    stubs = work / "bin"
    stubs.mkdir()
    shell_stub = stubs / "omarchy-shell"
    shell_stub.write_text(f'''#!/usr/bin/env python3
import json, os, sys
plugins = "{plugins}"
log = open("{work / 'shell.log'}", "a")
log.write(" ".join(sys.argv[1:]) + "\\n")
args = sys.argv[1:]
if args[:2] == ["shell", "rescanPlugins"]:
    import time; time.sleep(1.5)   # the real shell reloads every plugin here, which takes a while
elif args[:2] == ["shell", "listPlugins"]:
    out = []
    for d in sorted(os.listdir(plugins)):
        m = os.path.join(plugins, d, "manifest.json")
        if os.path.isfile(m):
            j = json.load(open(m)); out.append({{"id": j["id"], "enabled": True, "kinds": j["kinds"], "name": j["name"]}})
    print(json.dumps(out))
elif args[:2] in (["shell", "enablePlugin"], ["shell", "setPluginEnabled"]):
    print("ok")
''')
    shell_stub.chmod(0o755)

    harness = work / "shell.qml"
    harness.write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import "project/providers" as Providers
import "project/core/Extensions.js" as Extensions
ShellRoot {
  id: test
  property int stage: 0
  property int failures: 0
  property var lastEffect: null
  property var rows: []
  property var pluginsRaw: ({})
  property string indexUrl: %(index)s
  property string upstream: %(upstream)s
  function check(ok, what) { if (!ok) { failures++; console.log("FAIL", what) } else console.log("ok", what) }
  function titles() { return rows.map(function(r) { return r.title }).join(" | ") }
  function row(id) { for (var i = 0; i < rows.length; i++) if (rows[i].id === id) return rows[i]; return null }

  // Stand-in for providers/Registry.qml as Extensions.qml sees it: the same scan, the same parser.
  QtObject {
    id: reg
    property var manifests: ({})
    property var problems: []
    function scan() { scanProc.running = true }
  }
  Process {
    id: scanProc
    command: Extensions.scanArgv(%(home)s)
    stdout: StdioCollector { onStreamFinished: { var found = Extensions.parseScan(text); reg.manifests = found.manifests; reg.problems = found.problems } }
    onExited: test.advance()
  }
  function rescan() { reg.scan() }

  // Stand-in for Keystroke.qml as providers see it.
  QtObject {
    id: host
    property var registry: reg
    property var config: ({ version: 1, providers: {} })
    property string statusMessage: ""
    property string errorMessage: ""
    property string scope: "extensions"
    property int requeries: 0
    property int backs: 0
    function requery() { requeries++ }
    function goBack() { backs++ }
    function saveConfig(next) { config = next }
    function registryEntry(key) { return key === "extensions" ? { key: key, provider: ext.provider, source: "bundled" } : null }
    function settingsFor(entry) { return { marketplace: false, autoCheck: false, indexUrl: test.indexUrl } }
  }
  Providers.Extensions { id: ext; host: host }
  // A second instance stands in for the palette the shell recreates after a rescan.
  Loader { id: twin; active: false; sourceComponent: Providers.Extensions { host: host } }

  function query(scope, q) {
    var ctx = { query: q, rawQuery: q, scope: scope, sub: "", generation: 0, settings: host.settingsFor(null), pending: function() {}, host: host, shell: null, appLibrary: null, omarchyPath: "" }
    rows = ext.provider.query(ctx)
    return rows
  }
  function activate(row, alternate) {
    lastEffect = ext.provider.activate(row, { host: host, settings: host.settingsFor(null), alternate: !!alternate })
    return lastEffect
  }
  function idle() { return !ext.job && !ext.fetching }

  Timer { id: tick; interval: 100; repeat: true; running: true; onTriggered: test.advance() }
  Timer { id: guard; interval: 40000; running: true; onTriggered: { console.log("FAIL timeout at stage", test.stage, "job", JSON.stringify(ext.job), "fetching", ext.fetching); Qt.quit() } }

  function advance() {
    if (scanProc.running) return
    switch (stage) {
    case 0:   // fresh: nothing installed, index fetched from file://
      stage = 1; rescan(); return
    case 1:
      query("extensions", "")
      if (!idle()) return
      check(row("none") !== null, "empty state row: " + titles())
      check(row("discover/example.keystroke-spotify") !== null, "index entry discovered from file:// index")
      check(host.requeries > 0, "fetch requeries the palette")
      var root = query("", "ext")
      check(root.length === 1 && root[0].action.scope === "extensions", "root query reaches the Extensions screen")
      // Install from a git URL: the row the palette would build for a typed URL, pointed at the local upstream.
      query("extensions", "")
      var install = { id: "install-url", action: { type: "ext", op: "install", id: "", name: "Probe", url: test.upstream } }
      var eff = activate(install)
      check(eff.type === "noop" && ext.job && ext.job.kind === "install", "install starts omarchy-plugin-add")
      var busy = query("extensions", "")
      check(busy[0].id === "job" && busy[0].disabled, "job row shown while installing: " + titles())
      twin.active = true
      stage = 12; return
    case 12:   // the recreated instance finds the running job in the runtime dir
      if (!twin.item.job) return
      check(twin.item.job.kind === "install" && twin.item.job.startedAt === ext.job.startedAt, "a fresh instance picks up the in-flight job from job.json")
      twin.active = false
      stage = 2; return
    case 2:
      if (!idle()) return
      check(host.errorMessage === "", "install succeeded: " + host.errorMessage)
      check(host.statusMessage === "Installed Probe", "status after install: " + host.statusMessage)
      stage = 3; rescan(); return
    case 3:   // afterInstall rescanned the folder and checked the fresh clone; nothing was written to keystroke.json
      if (!idle() || !reg.manifests[%(id)s]) return
      query("extensions", "")
      var r = row("installed/" + %(id)s)
      check(r !== null && r.accessory === "On", "installed row is on: " + JSON.stringify(r && r.accessory))
      check(Object.keys(host.config.providers).length === 0, "install writes nothing to keystroke.json: " + JSON.stringify(host.config.providers))
      check(!(reg.manifests[%(id)s].__sourceDir === undefined), "scan stamps the source folder")
      stage = 4; return
    case 4:
      if (!idle()) return
      check(host.statusMessage === "Installed Probe", "the quiet check after an install keeps the install status: " + host.statusMessage)
      query("extensions", "")
      check(row("check").subtitle.indexOf("Checked ") === 0, "fresh clone was checked: " + row("check").subtitle)
      test.bumpUpstream(); stage = 5; return
    case 5:   // a new upstream commit: check finds it, update applies it, validation passes
      if (bumpProc.running) return
      query("extensions", "")
      activate(row("check"))
      stage = 6; return
    case 6:
      if (!idle()) return
      check(host.statusMessage === "1 update available", "update detected: " + host.statusMessage)
      query("extensions", "")
      check(row("check").title === "Update all (1)", "update-all offered: " + row("check").title)
      var detail = query("extensions/" + %(id)s, "")
      check(row(%(id)s + "/update").title === "Update now", "detail offers update")
      activate(row(%(id)s + "/update"))
      check(ext.job && ext.job.kind === "update", "update job started")
      stage = 7; return
    case 7:
      if (!idle()) return
      check(host.statusMessage === "Updated Probe · omarchy-restart-shell loads its new code", "update applied, restart advised: " + host.statusMessage + " " + host.errorMessage)
      stage = 8; rescan(); return
    case 8:
      query("extensions/" + %(id)s, "")
      check(reg.manifests[%(id)s].version === "1.1.0", "manifest on disk is the new version")
      check(row(%(id)s + "/update").title === "Check for updates", "no pending update after the merge")
      check(row(%(id)s + "/loaded") === null, "no second switch: the shell does not load extensions")
      // Turning off and on: Keystroke's switch is a setting effect the host writes.
      var off = activate(row(%(id)s + "/enabled"))
      check(off.type === "setting" && off.value === false && off.path[1] === %(id)s, "disable is a setting effect")
      var saved = { version: 1, providers: {} }; saved.providers[%(id)s] = { enabled: false }
      host.saveConfig(saved)
      query("extensions/" + %(id)s, "")
      check(row(%(id)s + "/enabled").accessory === "Off", "off once saved")
      var on = activate(row(%(id)s + "/enabled"))
      check(on.type === "setting" && on.value === true, "enable is a setting effect")
      host.saveConfig({ version: 1, providers: {} })
      // Ctrl+Enter on the list row toggles too.
      query("extensions", "")
      check(row("installed/" + %(id)s).accessory === "On", "on again with nothing saved")
      var alt = activate(row("installed/" + %(id)s), true)
      check(alt.type === "setting" && alt.value === false, "alternate action toggles enabled")
      activate(row(%(id)s + "/remove") || query("extensions/" + %(id)s, "") && row(%(id)s + "/remove"))
      check(ext.job && ext.job.kind === "remove", "remove job started")
      stage = 9; return
    case 9:
      if (!idle()) return
      check(host.statusMessage === "Removed Probe", "removed: " + host.statusMessage + " " + host.errorMessage)
      check(host.backs === 0, "no back navigation when not on the removed screen")
      stage = 10; rescan(); return
    case 10:
      query("extensions", "")
      check(row("none") !== null && row("installed/" + %(id)s) === null, "nothing installed after removal: " + titles())
      var gone = query("extensions/" + %(id)s, "")
      check(gone[0].id === "gone", "detail of a removed extension says so")
      console.log(failures ? "FAIL extensions check" : "PASS extensions install, check, update, toggle, remove through the Omarchy scripts")
      Qt.quit(); stage = 11; return
    }
  }
  Process { id: bumpProc; command: ["python3", %(bump)s]; onExited: function(code) { if (code !== 0) console.log("FAIL bump", code) } }
  function bumpUpstream() { bumpProc.running = true }
}
''' % dict(project=str(project), index=json.dumps("file://" + str(index)), upstream=json.dumps(str(upstream)), home=json.dumps(str(home)), id=json.dumps(PLUGIN_ID), bump=json.dumps(str(work / "bump.py"))))

    (work / "bump.py").write_text(f'''import json, subprocess, os
src = {json.dumps(str(src))}; up = {json.dumps(str(upstream))}
env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
m = json.load(open(src + "/manifest.json")); m["version"] = "1.1.0"; json.dump(m, open(src + "/manifest.json", "w"), indent=2)
subprocess.run(["git", "commit", "-q", "-am", "v1.1.0"], cwd=src, env=env, check=True)
subprocess.run(["git", "push", "-q", up, "main"], cwd=src, env=env, check=True)
''')

    env = os.environ.copy()
    env.pop("DISPLAY", None)
    env.update(HOME=str(home), XDG_RUNTIME_DIR=str(work), QML_IMPORT_PATH=str(work), PATH=str(stubs) + ":" + env["PATH"], OMARCHY_PATH="/usr/share/omarchy",
               QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", GIT_CONFIG_GLOBAL="/dev/null")
    r = subprocess.run(["quickshell", "-p", str(harness)], env=env, text=True, capture_output=True, timeout=60)
    out = r.stdout + r.stderr
    assert "PASS extensions" in out and "FAIL" not in out, out
    assert "TypeError" not in out and "ReferenceError" not in out, out
    import re
    plain = re.sub(r"\x1b\[[0-9;]*m", "", out)
    print("\n".join(line.split("qml: ", 1)[-1] for line in plain.splitlines() if re.search(r"qml: (ok|PASS|FAIL)", line)))
