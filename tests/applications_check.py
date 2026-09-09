#!/usr/bin/env python3
"""Exercise shared and missing scoped app libraries using real Omarchy/QML."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
omarchy = Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy'))
with tempfile.TemporaryDirectory(prefix='keystroke-apps-') as temp:
    work = Path(temp)
    shutil.copytree(root / 'core', work / 'core')
    (work / 'providers').mkdir()
    shutil.copy(root / 'providers/Applications.qml', work / 'providers')
    for name in ('Commons', 'services'):
        (work / name).symlink_to(omarchy / 'shell' / name)
    (work / 'qs').symlink_to(omarchy / 'shell')
    data = work / 'data'
    apps = data / 'applications'
    apps.mkdir(parents=True)
    for name, extra in [('visible', ''), ('hidden', 'Hidden=true\n'), ('nodisplay', 'NoDisplay=true\n')]:
        (apps / f'keystroke-test-{name}.desktop').write_text(
            f'[Desktop Entry]\nType=Application\nName=Keystroke {name}\n'
            f'Exec=true\nGenericName=Test Browser\nKeywords=internet;\n{extra}')
    (work / 'shell.qml').write_text('''import QtQuick
import QtQml.Models
import Quickshell
import "core"
import "providers"
ShellRoot {
  id: test
  property int stage: 0
  property int requeries: 0
  property var appLibrary: adapter.library
  property var manifestRows: [{manifest: {kinds: ["menu", "bar-widget"]}}]
  property bool convertedKinds: false
  function requery() { requeries++ }
  function check(ok, message) { if (!ok) { console.log("FAIL", message); Qt.quit(); throw Error(message) } }
  // The 4.0.3 loader passes this converted manifest to manifestHasKind.
  Instantiator {
    model: test.manifestRows
    delegate: QtObject {
      required property var modelData
      Component.onCompleted: test.convertedKinds = !Array.isArray(modelData.manifest.kinds)
        && modelData.manifest.kinds.indexOf("menu") === 0
    }
  }
  QtObject { id: sharedShell; property var appLibrary: shared }
  QtObject { id: scopedShell; property var appLibrary: null }
  QtObject {
    id: shared
    signal appsChanged()
    property int refreshes: 0
    function sortedEntries(query) { return [{entry: {id: "shared", name: "Shared Browser"}}] }
    function entryName(entry) { return entry.name }
    function entrySubtext(entry) { return "" }
    function iconSource(icon) { return "" }
    function refreshIcons() { refreshes++ }
  }
  ApplicationLibrary { id: adapter; omarchyPath: Quickshell.env("OMARCHY_PATH") }
  Applications { id: provider; host: test }
  Timer { interval: 100; repeat: true; running: true; onTriggered: {
    if (test.stage === 0) {
      test.check(test.convertedKinds, "reproduce Instantiator manifest conversion")
      test.check(!adapter.library, "no library before shell injection")
      adapter.hostShell = sharedShell
      test.check(adapter.library === shared, "4.0.2/shared capability preferred")
      test.check(provider.query({scope:"applications", query:""})[0].id === "shared", "shared app rows")
      provider.provider.opened()
      test.check(shared.refreshes === 1, "refresh delegated")
      var before = test.requeries
      shared.appsChanged()
      test.check(test.requeries > before, "app changes requery")
      adapter.hostShell = scopedShell
      test.stage = 1
    } else if (test.stage === 1 && adapter.library && adapter.library.sortedEntries("").length) {
      var rows = provider.query({scope:"applications", query:""})
      test.check(rows.length === 1 && rows[0].id === "keystroke-test-visible", "fallback lists visible entries only")
      test.check(provider.query({scope:"", query:"internet"}).length === 1, "root keyword search")
      test.check(rows[0].action.type === "app" && rows[0].action.id === rows[0].id, "launch action retains desktop id")
      test.check(typeof adapter.library.launch === "function" && typeof adapter.library.remove === "function", "native launch and removal APIs")
      adapter.library.loadConfiguredHides("keystroke-test-visible.desktop")
      test.check(provider.query({scope:"applications", query:""}).length === 0, "configured hides respected")
      adapter.hostShell = sharedShell
      test.check(adapter.library === shared, "shared capability replaces fallback")
      adapter.hostShell = null
      test.check(!adapter.library, "fallback released with host")
      console.log("PASS applications: shared/scoped libraries, filtering, search, updates, lifecycle")
      Qt.quit()
      test.stage = 2
    }
  } }
  Timer { interval: 8000; running: true; onTriggered: { console.log("FAIL timeout", test.stage); Qt.quit() } }
}
''')
    env = os.environ.copy()
    for name in ('DISPLAY', 'WAYLAND_DISPLAY'):
        env.pop(name, None)
    env.update(HOME=str(work), XDG_RUNTIME_DIR=str(work), XDG_DATA_HOME=str(data),
               XDG_DATA_DIRS=str(work / 'empty'), OMARCHY_PATH=str(omarchy),
               QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic',
               QT_QUICK_BACKEND='software', QML_IMPORT_PATH=str(work))
    result = subprocess.run(['quickshell', '-p', str(work / 'shell.qml')], env=env,
                            capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and 'PASS applications:' in output and 'FAIL' not in output, output
    assert 'TypeError' not in output and 'ReferenceError' not in output, output
    print('PASS applications: shared/scoped libraries, filtering, search, updates, lifecycle')
