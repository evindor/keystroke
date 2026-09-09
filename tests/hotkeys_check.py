#!/usr/bin/env python3
"""Drive providers/Hotkeys.qml against the real omarchy-menu-keybindings.

The provider loads Omarchy's keybinding records through the stock script
(so this needs a running Hyprland: `hyprctl binds` answers), then the
harness queries the root for an abbreviation, opens the Hotkeys screen and
asks activate() for the effect of a row. Nothing is dispatched: the effect's
argv is inspected, never run.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]

if subprocess.run(["hyprctl", "binds"], capture_output=True, text=True).returncode != 0:
    print("SKIP hotkeys check: hyprctl binds is not answering (no Hyprland session)")
    raise SystemExit(0)

with tempfile.TemporaryDirectory(prefix="keystroke-hotkeys-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__", "experiments"))
    for name, target in [("qs", "/usr/share/omarchy/shell"), ("Commons", "/usr/share/omarchy/shell/Commons"), ("Ui", "/usr/share/omarchy/shell/Ui")]:
        (work / name).symlink_to(target)

    harness = work / "shell.qml"
    harness.write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import "project/providers" as Providers
ShellRoot {
  id: test
  property int stage: 0
  property int failures: 0
  property int pendings: 0
  property var rows: []
  function check(ok, what) { if (!ok) { failures++; console.log("FAIL", what) } else console.log("ok", what) }
  function titles() { return rows.map(function(r) { return r.title }).join(" | ") }
  function row(id) { for (var i = 0; i < rows.length; i++) if (rows[i].id === id) return rows[i]; return null }
  function find(title) { for (var i = 0; i < rows.length; i++) if (rows[i].title === title) return rows[i]; return null }

  QtObject {
    id: host
    property int requeries: 0
    function requery() { requeries++ }
  }
  Providers.Hotkeys { id: hotkeys; host: host }

  function query(scope, q) {
    var ctx = { query: q, rawQuery: q, scope: scope, sub: "", generation: 0, settings: { limit: 10, keyboardOnly: true },
                pending: function() { test.pendings++ }, host: host, shell: null, appLibrary: null, omarchyPath: "/usr/share/omarchy" }
    rows = hotkeys.provider.query(ctx)
    return rows
  }

  Timer { id: tick; interval: 100; repeat: true; running: true; onTriggered: test.advance() }
  Timer { id: guard; interval: 20000; running: true; onTriggered: { console.log("FAIL timeout at stage", test.stage); Qt.quit() } }

  function advance() {
    switch (stage) {
    case 0:
      query("", "flcrn")
      check(pendings === 1 && rows.length === 0, "first query is pending until the script answers")
      stage = 1; return
    case 1:
      if (!hotkeys.loaded) return
      check(host.requeries >= 1, "the host is requeried when the records land")
      check(hotkeys.binds.length > 50, "records loaded: " + hotkeys.binds.length + " binds")
      query("", "")
      check(rows.length === 1 && rows[0].id === "hotkeys" && rows[0].action.type === "navigate", "empty root shows only the Hotkeys entry")
      query("", "flcrn")
      check(rows.length > 0 && rows[0].title === "Full screen", "flcrn finds Full screen first: " + titles())
      check(rows[0].accessory === "Super + F", "Super + F shown next to it: " + rows[0].accessory)
      check(rows[0].section === "Hotkeys" && rows[0].remember === true, "row is a remembered Hotkeys item")
      query("", "super f")
      check(find("Full screen") !== null, "the keys themselves find the bind: " + titles())
      query("", "terminal")
      check(find("Terminal") !== null && find("Terminal").accessory === "Super + ↵", "Terminal on Super + Return: " + JSON.stringify(find("Terminal") && find("Terminal").accessory))
      check(rows.length <= 10, "root results are capped: " + rows.length)
      query("hotkeys", "")
      check(rows.length === hotkeys.binds.length, "the screen lists every bind: " + rows.length)
      check(rows[0].title === "Keybindings" && rows[0].accessory === "Super + K", "menu order kept, Keybindings first: " + rows[0].title)
      // Close window was a keyboard-only closure on the reference host;
      // current bindings expose it as a runnable Lua dispatcher. Follow the
      // actual record, keeping fixed closure coverage in tst_hotkeys.qml.
      var closeBind = hotkeys.binds.find(function(bind) { return bind.combos.indexOf("SUPER + W") !== -1 })
      var closeWin = closeBind ? row(closeBind.id) : null
      check(closeWin !== null && closeWin.disabled === !closeBind.dispatcher && closeWin.accessory.indexOf("Super + W") !== -1,
            "Close window availability follows the host binding")
      query("hotkeys", "screenshot")
      check(rows.length > 0 && rows[0].title === "Screenshot", "search inside the screen: " + titles())
      query("other", "x")
      check(rows.length === 0, "silent in another provider's scope")
      // Activation is translated to the script's own dispatcher; the argv is not run here.
      query("", "full screen")
      var effect = hotkeys.provider.activate(rows[0], { host: host, settings: {}, alternate: false })
      check(effect.type === "exec" && effect.argv[0] === "bash" && effect.argv[3] === "/usr/share/omarchy/bin/omarchy-menu-keybindings", "activate runs through omarchy-menu-keybindings")
      check(effect.argv[4] === "lua" && effect.argv[5].indexOf("fullscreen") > 0, "dispatcher and argument travel as argv: " + effect.argv.slice(4).join(" "))
      var nav = hotkeys.provider.activate({ action: { type: "navigate", scope: "hotkeys" } }, { host: host, settings: {} })
      check(nav.type === "navigate", "non-hotkey actions pass through")
      console.log(failures ? "FAIL hotkeys check" : "PASS hotkeys provider over omarchy-menu-keybindings")
      Qt.quit(); stage = 2; return
    }
  }
}
''')

    env = os.environ.copy()
    env.pop("DISPLAY", None)
    env.update(QML_IMPORT_PATH=str(work), OMARCHY_PATH="/usr/share/omarchy",
               QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software")
    r = subprocess.run(["quickshell", "-p", str(harness)], env=env, text=True, capture_output=True, timeout=60)
    out = r.stdout + r.stderr
    plain = re.sub(r"\x1b\[[0-9;]*m", "", out)
    print("\n".join(line.split("qml: ", 1)[-1] for line in plain.splitlines() if re.search(r"qml: (ok|PASS|FAIL)", line)))
    assert "PASS hotkeys" in out and "FAIL" not in out, out
    assert "TypeError" not in out and "ReferenceError" not in out, out
