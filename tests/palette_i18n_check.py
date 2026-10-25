#!/usr/bin/env python3
"""Switch actual Omarchy translations around a real palette with synthetic data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

if not Path("/usr/share/omarchy/shell/Commons/Translations.qml").is_file():
    print("SKIP native live-switch check: Omarchy 4.5 translation API is unavailable; legacy_i18n_check.py covers this runtime")
    raise SystemExit(0)

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="keystroke-i18n-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text().replace("  id: root\n", "  id: root\n  property alias testCard: card\n", 1)
    qml = qml.replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))
    (work / "language").write_text("en\n")
    (work / "extension-i18n").mkdir()
    (work / "extension-i18n/en.json").write_text(json.dumps({"title":"Private extension title"}))
    (work / "extension-i18n/de.json").write_text(json.dumps({"title":"Privater Erweiterungstitel"}))
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import "project"
ShellRoot {
  id: test
  property int phase: 0
  property var prefixes: []
  property var extensionStrings: null
  property bool capturing: false
  function check(ok, message) { if (!ok) { console.log("FAIL", message); Qt.quit(); throw Error(message) } }
  function settings() { return palette.registry.bundled.filter(p => p.provider.id === "settings")[0] }
  function rows(q) { return test.settings().query({scope:"settings",query:q,settings:{}}) }
  function screenshot(name) {
    var dir=Quickshell.env("KEYSTROKE_SCREENSHOT_DIR")
    if (dir) { test.capturing=true; palette.testCard.grabToImage(function(result) { result.saveToFile(dir+"/"+name+".png"); test.capturing=false }) }
  }
  FileView { id: language; path: Quickshell.env("OMARCHY_LANGUAGE_FILE"); blockLoading: true }
  Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
  Timer { interval: 200; running: true; repeat: true; onTriggered: {
    if (test.capturing) return
    if (test.phase === 0) {
      palette.applyConfigText(JSON.stringify({version:1,matching:{mode:"off"},providers:{files:{prefix:"Open"}}}))
      palette.open('{"scope":"settings","title":"Settings"}')
      test.check(palette.t("What would you like to do?") === "What would you like to do?", "English catalog")
      test.prefixes=palette.commandItems().map(c=>c.prefix)
      test.extensionStrings=palette.createTranslator(test, Quickshell.env("HOME")+"/extension-i18n")
      test.check(test.extensionStrings.t("title", "Private extension title") === "Private extension title", "extension-owned catalog")
      test.screenshot("settings-en")
      test.phase=9
    } else if (test.phase === 9) {
      language.setText("de\\n")
      test.phase=1
    } else if (test.phase === 1) {
      if (palette.language !== "de" || palette.t("Appearance") !== "Darstellung") return
      test.check(test.extensionStrings.t("title") === "Privater Erweiterungstitel", "extension catalog follows the language")
      test.check(test.rows("Darstellung").some(r=>r.id==="palette"), "German settings search")
      test.check(test.rows("Appearance").some(r=>r.id==="palette"), "English settings search retained")
      var tree=test.settings().current()
      var density=tree.nodes.filter(n=>n.id==="palette/density/compact")[0]
      test.check(tree.nodes.filter(n=>n.id==="palette")[0].action.title === "Appearance", "navigation title stays canonical for live headers")
      test.check(density.title === "Kompakt" && density.action.value === "compact", "translated option retains persisted enum value")
      var prefix=tree.nodes.filter(n=>n.id==="files/prefix")[0]
      test.check(prefix.accessory === "Open", "arbitrary string setting value is not translated")
      test.check(palette.commandItems().map(c=>c.prefix).join("|") === test.prefixes.join("|"), "command prefixes stay literal")
      var row=palette.normalize({id:"external",title:"Open",subtitle:"Save",action:{type:"copy",text:"Open %2"}}, {key:"test",provider:{name:"Test"},source:"extension"},"",0)
      test.check(row.title === "Open" && row.subtitle === "Save" && row.action.text === "Open %2", "external content and actions stay literal")
      test.check(palette.t("No matches for “%1”", ["<tag> %2"]) === "Keine Treffer für „<tag> %2“", "placeholder values are substituted once")
      test.check(palette.tn("%1 extension",1) === "1 Erweiterung" && palette.tn("%1 extension",2) === "2 Erweiterungen", "German plural forms")
      test.check(palette.formatNumber(1.5) === "1,5", "Omarchy number formatting")
      test.check(palette.queryProvider(palette.registry.entries.filter(e=>e.key==="calculator")[0],"Rechner","","",null).rows.some(r=>r.title==="Rechner"), "German provider navigation")
      var names = {calculator:"Calculator",clipboard:"Clipboard History",emoji:"Emoji Picker",converter:"Convert Anything",files:"Search Files",colors:"Pick a Color",extensions:"Extensions"}
      for (var key in names) {
        var entry=palette.registry.entries.filter(e=>e.key===key)[0]
        test.check(palette.queryProvider(entry,names[key],"","",null).rows.length > 0, "English provider name retained: " + key)
      }
      palette.runQuery()
      test.screenshot("settings-de")
      test.phase=10
    } else if (test.phase === 10) {
      palette.navigate("settings/palette", "Appearance")
      test.check(palette.localizedScopeTitle === "Darstellung", "German nested header")
      language.setText("de-AT\\n")
      test.phase=2
    } else if (test.phase === 2) {
      if (palette.language !== "de-AT" || palette.t("Appearance") !== "Darstellung") return
      test.check(palette.t("missing untranslated key") === "missing untranslated key", "unknown key falls back")
      language.setText("fr\\n")
      test.phase=3
    } else if (test.phase === 3) {
      if (palette.language !== "fr" || palette.t("Appearance") !== "Appearance") return
      test.check(palette.localizedScopeTitle === "Appearance", "open header switches back without renavigation")
      test.check(test.rows("Appearance").some(r=>r.title==="Appearance"), "unsupported catalog falls back to English after switching")
      language.setText("ar\\n")
      test.phase=4
    } else if (test.phase === 4) {
      if (palette.language !== "ar" || !palette.rightToLeft) return
      test.check(palette.t("Appearance") === "Appearance", "RTL locale can use English fallback")
      test.check(palette.readingKey({key:Qt.Key_Left}) === Qt.Key_Right && palette.readingKey({key:Qt.Key_Right}) === Qt.Key_Left, "directional keys follow the language without newer shell helpers")
      palette.cancel()
      console.log("PASS palette i18n")
      Qt.quit()
    }
  } }
  Timer { interval: 10000; running:true; onTriggered: { console.log("FAIL timeout",test.phase,palette.language); Qt.quit() } }
}
''')
    env = dict(os.environ, HOME=str(work), XDG_CONFIG_HOME=str(work/".config"), OMARCHY_LANGUAGE_FILE=str(work/"language"), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work/"shell.qml")], env=env, capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    assert "PASS palette i18n" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    print("PASS live i18n: German/English search, stable actions/settings, safe substitutions, plurals, regional/English fallback and RTL locale")
