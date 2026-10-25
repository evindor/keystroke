#!/usr/bin/env python3
"""Exercise the real Omarchy adapter with synthetic 4.5 menus and catalogs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="keystroke-omarchy45-") as temp:
    work = Path(temp)
    for folder in ("providers", "core", "omarchy"):
        shutil.copytree(root / folder, work / folder)
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    default = work / "default/omarchy"
    default.mkdir(parents=True)
    (default / "omarchy-menu.jsonc").write_text(json.dumps({
        "setup": {"label": "Setup"},
        "setup.language": {"label": "Language", "provider": "languages"},
        "install": {"label": "Install"},
        "install.present": {"label": "Present", "disabled": "true", "action": "never-run"},
        "install.absent": {"label": "Absent", "disabled": "false", "action": "never-run"},
        "install.hidden": {"label": "Hidden", "when": "false", "action": "never-run"},
    }))
    for code in ("de", "en"):
        folder = work / "default/i18n" / code
        folder.mkdir(parents=True)
        catalog = {"root": {"label": "Los"}, "setup": {"label": "Einrichten"}, "setup.language": {"label": "Sprache"}} if code == "de" else {}
        (folder / "menu.json").write_text(json.dumps(catalog))
    language = work / "language"
    language.write_text("de\n")
    (work / ".config/omarchy/extensions").mkdir(parents=True)
    (work / ".config/omarchy/extensions/omarchy-menu.jsonc").write_text(json.dumps({"setup": {"label": "My setup"}}))
    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import "providers"
ShellRoot {
  id: test
  property int phase: 0
  OmarchyMenu { id: menu }
  function check(ok, message) { if (!ok) { console.log("FAIL", message); Qt.quit(); throw Error(message) } }
  Timer { interval: 50; running: true; repeat: true; onTriggered: {
    if (test.phase === 0) {
      if (menu.language !== "de" || menu.item("setup.language") === null || menu.item("setup.language").label !== "Sprache" || menu.disabledResults["install.present"] !== true) return
      test.check(menu.item("root").label === "Los", "translated root")
      test.check(menu.item("setup").label === "My setup", "user label wins over translation")
      var ctx = {scope:"omarchy", sub:"install", query:"", settings:{}, pending:function(){}}
      var rows = menu.query(ctx)
      test.check(rows.some(r => r.id === "install.present" && r.disabled && r.accessory === "✓"), "installed action stays listed but disabled")
      test.check(rows.some(r => r.id === "install.absent" && !r.disabled), "available action remains enabled")
      test.check(!rows.some(r => r.id === "install.hidden"), "when guard still hides rows")
      test.check(menu.catalog(ctx).some(r => r.id === "install.present" && r.disabled), "smart catalog preserves disabled flag")
      ctx.sub="setup"; ctx.query="Language"
      test.check(menu.query(ctx).some(r => r.title === "Sprache"), "English search reaches translated label")
      test.check(menu.resolveRoute("Language") !== "setup.language", "English label does not become an IPC alias")
      menu.mergeProviderRows("Deutsch\\tde\\tde\\tGerman\\nEnglish\\ten\\tde\\tEnglish", "setup.language", "languages")
      ctx.sub="setup.language"; ctx.query="German"
      rows=menu.query(ctx)
      test.check(rows.length === 1 && rows[0].title === "Deutsch", "native names searchable in English")
      test.check(rows[0].action.command.indexOf("omarchy-language") === 0, "language action uses stock command")
      menu.setLanguage("en")
      test.phase=1
    } else if (test.phase === 1) {
      if (menu.item("setup.language").label !== "Language") return
      test.check(menu.item("setup").label === "My setup", "override survives language change")
      test.check(menu.parseCatalog("broken").root === undefined, "broken catalog degrades safely")
      menu.setLanguage("../../invalid")
      test.check(menu.language === "en", "language code cannot escape catalog directory")
      console.log("PASS Omarchy 4.5 adapter")
      Qt.quit()
    }
  } }
  Timer { interval: 8000; running: true; onTriggered: { console.log("FAIL timeout", test.phase); Qt.quit() } }
}
''')
    env = dict(os.environ, HOME=str(work), OMARCHY_PATH=str(work), OMARCHY_LANGUAGE_FILE=str(language), XDG_RUNTIME_DIR=str(work), QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=12)
    output = result.stdout + result.stderr
    assert "PASS Omarchy 4.5 adapter" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    print("PASS Omarchy 4.5: translations, live catalog reload, user overrides, English search, disabled guards and language rows")
