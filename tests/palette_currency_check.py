#!/usr/bin/env python3
"""The Currency extension fetches its table on demand, offscreen, with a fake curl.

A copy of the project and a fake HOME with the extension turned on. `curl` on
PATH is a script that logs every call and answers what a mode file says: first
an empty body with exit 0 (a failure the service must record, then wait
RETRY_MS before trying again rather than downloading on every query), then a
real Frankfurter table. The palette is driven through Keystroke.qml itself.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix="keystroke-palette-currency-") as temp:
    work = Path(temp)
    project = work / "project"
    shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".claude", ".agents", ".codex", "tests", "__pycache__", "experiments"))
    (work / "qs").symlink_to("/usr/share/omarchy/shell")
    source = project / "Keystroke.qml"
    qml = source.read_text()
    qml = qml.replace("  PanelWindow {", "  Window {\n    transientParent: null\n    width: 1000; height: 800")
    qml = qml.replace("    anchors { top: true; bottom: true; left: true; right: true }\n", "")
    source.write_text("\n".join(line for line in qml.splitlines() if "exclusionMode:" not in line and "WlrLayershell." not in line))

    (work / ".config/omarchy").mkdir(parents=True)
    (work / ".config/omarchy/keystroke.json").write_text(json.dumps({"version": 1, "matching": {"mode": "off"}, "providers": {"currency": {"enabled": True, "preferredCurrency": "EUR"}}}))

    fake = work / "bin"
    fake.mkdir()
    log = work / "curl.log"
    mode = work / "curl.mode"
    table = [{"base": "EUR", "quote": q, "rate": r, "date": "2026-09-10"} for q, r in
             [("USD", 1.2), ("GBP", 0.8), ("TRY", 60), ("JPY", 170), ("CHF", 0.95), ("CAD", 1.6), ("AUD", 1.8), ("SEK", 11), ("NOK", 11.5), ("DKK", 7.46), ("PLN", 4.3)]]
    (work / "table.json").write_text(json.dumps(table))
    mode.write_text("empty")
    (fake / "curl").write_text(f'''#!/bin/sh
echo "$@" >> "{log}"
case "$(cat "{mode}")" in
  empty) exit 0 ;;
  table) cat "{work / 'table.json'}" ;;
esac
''')
    (fake / "curl").chmod(0o755)

    (work / "shell.qml").write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import "project"
ShellRoot {
 id: test
 property int stage: 0
 property int failures: 0
 function check(ok, msg) { if (!ok) { failures++; console.log("FAIL", msg) } else console.log("ok", msg) }
 function titles() { return palette.rows.map(function(r) { return r.title }) }
 function row(title) { return palette.rows.filter(function(r) { return r.title === title })[0] || null }
 function service() { var s = palette.registry.services["currency"]; return s ? s.instance : null }
 function curlCalls() { return String(curlLog.text()).split("\\n").filter(function(l) { return l.trim() }).length }
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 FileView { id: curlLog; path: "''' + str(log) + '''"; printErrors: false }
 FileView { id: curlMode; path: "''' + str(mode) + '''"; printErrors: false }
 FileView { id: rates; path: "''' + str(work / ".cache/keystroke/currency/rates.json") + '''"; printErrors: false }
 Timer { interval: 100; repeat: true; running: true; onTriggered: {
   curlLog.reload()
   switch (test.stage) {
   case 0:
     if (!service()) return
     palette.open(JSON.stringify({ query: "100 usd to try" }))
     test.stage = 1; return
   case 1:   // the fake curl answered an empty body: recorded as a failure, not retried on the next query
     if (palette.pending || service().fetching || !palette.rows.length || row("Downloading exchange rates…") || curlCalls() < 1) return
     test.check(row("Exchange rates unavailable") !== null, "empty answer: the status row says the rates are unavailable: " + titles().join(" | "))
     test.check(row("Exchange rates unavailable") && row("Exchange rates unavailable").subtitle.indexOf("Frankfurter answered nothing") === 0, "the row says why: " + (row("Exchange rates unavailable") || {}).subtitle)
     test.check(service().failedAt > 0 && service().error === "Frankfurter answered nothing", "the failure is recorded on the service: " + service().error)
     test.check(curlCalls() === 1, "curl ran once: " + curlCalls())
     palette.setQuery("100 usd to eur")
     test.stage = 2; return
   case 2:
     if (palette.pending || service().fetching) return
     test.check(curlCalls() === 1, "another query within RETRY_MS does not run curl again: " + curlCalls())
     test.check(row("Exchange rates unavailable") !== null, "still the status row: " + titles().join(" | "))
     curlMode.setText("table")
     service().failedAt = 1        // RETRY_MS has passed
     palette.setQuery("100 usd to try")
     test.stage = 3; return
   case 3:   // a real table: the conversion answers and the cache is written
     if (palette.pending || service().fetching || !palette.rows.length || row("Downloading exchange rates…") || row("Exchange rates unavailable") || curlCalls() < 2) return
     var r = row(Number(5000).toLocaleString(Qt.locale(), "f", 2) + " TRY")
     test.check(r !== null, "100 usd to try answers from the table: " + titles().join(" | "))
     test.check(r && r.subtitle.indexOf("1 USD = 50 TRY") === 0, "the subtitle carries the rate: " + (r && r.subtitle))
     test.check(curlCalls() === 2, "curl ran once more: " + curlCalls())
     test.check(service().error === "" && service().failedAt === 0, "the failure is cleared")
     palette.setQuery("129usd")
     test.stage = 4; return
   case 4:
     if (palette.pending || service().fetching || !palette.rows.length) return
     test.check(row(Number(107.5).toLocaleString(Qt.locale(), "f", 2) + " EUR") !== null, "a bare amount goes to the preferred currency: " + titles().join(" | "))
     test.check(curlCalls() === 2, "a fresh table is not downloaded again: " + curlCalls())
     rates.reload()
     test.stage = 5; return
   case 5:
     var text = String(rates.text())
     if (!text) return
     var cache = JSON.parse(text)
     test.check(cache.version === 1 && cache.base === "EUR" && cache.rates.TRY.rate === 60, "the table landed in ~/.cache/keystroke/currency/rates.json")
     console.log(test.failures ? "FAIL palette currency" : "PASS palette currency")
     Qt.quit(); test.stage = 6; return
   }
 } }
 Timer { interval: 15000; running: true; onTriggered: { console.log("FAIL timeout at stage", test.stage, JSON.stringify(palette.registry.problems), palette.errorMessage, titles().join(" | ")); Qt.quit() } }
}
''')

    env = dict(os.environ, HOME=str(work), XDG_RUNTIME_DIR=str(work), PATH=f"{fake}:{os.environ['PATH']}",
               QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QML_IMPORT_PATH=str(work))
    for k in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        env.pop(k, None)
    result = subprocess.run(["quickshell", "-p", str(work / "shell.qml")], env=env, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert "PASS palette currency" in output and "FAIL" not in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    print("PASS palette currency: an empty download is recorded and not retried before RETRY_MS, a real table answers conversions, is cached and is not fetched again")
