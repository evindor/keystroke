#!/usr/bin/env python3
"""Offscreen palette profiler.

Runs the actual providers against this machine's menu, apps, hotkeys and home
folder, with the installed Smart Match engine, and types a fixed script of
queries. A copy of the checkout is patched with timestamps around each phase of
runQuery(); nothing is installed, replaced or activated. Prints, per keystroke on
the UI thread, the median/p90/max milliseconds of each phase, how many queries
one keystroke caused, and per-provider totals.

Usage: tools/profile_palette.py [checkout] [label]
"""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
label = sys.argv[2] if len(sys.argv) > 2 else 'run'
queries = ["o","op","ope","open","open ","open t","open th","open the","open the ","open the b","open the br","open the bro","open the brow","open the brows","open the browse","open the browser",
           "s","sc","scr","scre","scree","screen","screens","screensh","screensho","screenshot",
           "v","vo","vol","volu","volum","volume","volume ","volume u","volume up",
           "c","ch","chr","chro","chrom","chrome"]
with tempfile.TemporaryDirectory(prefix='keystroke-prof-') as temp:
    work = Path(temp); project = work/'project'
    shutil.copytree(root, project, ignore=shutil.ignore_patterns('.git','.claude','.agents','.codex','tests','__pycache__','experiments','site','assets'))
    (work/'qs').symlink_to('/usr/share/omarchy/shell')
    src = project/'Keystroke.qml'; qml = src.read_text()
    qml = qml.replace('  id: root\n', '  id: root\n  property alias testMatching: matchingSession\n  property var marks: []\n  property int queryCalls: 0\n  function mark(n) { marks.push([n, Date.now()]) }\n', 1)
    qml = qml.replace('  function runQuery() {\n    if (!root.opened || root.providerViewActive) return\n',
                      '  function runQuery() {\n    if (!root.opened || root.providerViewActive) return\n    root.queryCalls++; root.marks = []; root.mark("start")\n')
    assert 'root.mark("start")' in qml
    qml = qml.replace('    if (root.configError) errors.push(root.configError)\n', '    root.mark("providers")\n    if (root.configError) errors.push(root.configError)\n')
    qml = qml.replace('      var hasAnswer = collected.some(', '      root.mark("documents")\n      var hasAnswer = collected.some(')
    qml = qml.replace('    var ranked = Match.rank(collected, root.bonusFor)\n', '    root.mark("merge")\n    var ranked = Match.rank(collected, root.bonusFor)\n    root.mark("rank")\n')
    qml = qml.replace('    root.lastPatterns = matchedPatterns\n', '    root.mark("apply")\n    root.lastPatterns = matchedPatterns\n')
    qml = qml.replace('    root.afterRows()\n  }\n\n  // One provider', '    root.afterRows()\n    root.mark("end")\n  }\n\n  // One provider')
    assert qml.count('root.mark(') == 7, qml.count('root.mark(')
    qml = qml.replace('      var out = entry.provider.query(ctx) || []\n', '      var __t = Date.now(); var out = entry.provider.query(ctx) || []; root.providerMs[entry.key] = (root.providerMs[entry.key] || 0) + (Date.now() - __t); root.providerCalls[entry.key] = (root.providerCalls[entry.key] || 0) + 1\n')
    assert 'root.providerMs[entry.key]' in qml
    qml = qml.replace('        if (typeof entry.provider.catalog === "function") candidates = entry.provider.catalog(ctx) || []\n', '        var __c = Date.now(); if (typeof entry.provider.catalog === "function") { candidates = entry.provider.catalog(ctx) || []; root.catalogMs[entry.key] = (root.catalogMs[entry.key] || 0) + (Date.now() - __c) }\n')
    assert 'root.catalogMs[entry.key]' in qml
    qml = qml.replace('  property var marks: []\n', '  property var marks: []\n  property var providerMs: ({})\n  property var providerCalls: ({})\n  property var catalogMs: ({})\n')
    qml = qml.replace('  PanelWindow {','  Window {\n    transientParent: null\n    width: 1000; height: 800')
    qml = qml.replace('    anchors { top: true; bottom: true; left: true; right: true }\n','')
    src.write_text('\n'.join(l for l in qml.splitlines() if 'exclusionMode:' not in l and 'WlrLayershell.' not in l))
    (work/'shell.qml').write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
 id: test
 property int step: -1
 property var queries: %s
 property var samples: []
 property var calls: []
 property real typedAt: 0
 property var roundTrips: []
 property string lastKey: ""
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 function phases() {
   var m = palette.marks, out = {}
   for (var i = 1; i < m.length; i++) out[m[i][0]] = m[i][1] - m[i-1][1]
   out.total = m.length ? m[m.length-1][1] - m[0][1] : -1
   return out
 }
 Connections { target: palette.testMatching; function onResultKeyChanged() { if (palette.testMatching.resultKey && palette.testMatching.resultKey !== test.lastKey) { test.lastKey = palette.testMatching.resultKey; test.roundTrips.push(Date.now() - test.typedAt) } } }
 Timer { interval: 1500; running: true; onTriggered: { palette.shell = ({ pluginId: "prof" }); palette.open('{}'); test.step = 0; warm.start() } }
 Timer { id: warm; interval: 2500; onTriggered: { console.log("STATE rows", palette.rows.length, "matching", palette.testMatching.status, "apps", palette.inspectApplications()); typing.start() } }
 Timer { id: typing; interval: 120; repeat: true; onTriggered: {
   if (test.step > 0) { test.samples.push(test.phases()); test.calls.push(palette.queryCalls) }
   if (test.step >= test.queries.length) { typing.stop(); settle.start(); return }
   palette.queryCalls = 0
   test.typedAt = Date.now()
   palette.setQuery(test.queries[test.step]); test.step++
 } }
 Timer { id: settle; interval: 800; onTriggered: {
   console.log("RESULT " + JSON.stringify({ providerMs: palette.providerMs, providerCalls: palette.providerCalls, catalogMs: palette.catalogMs, samples: test.samples, calls: test.calls, roundTrips: test.roundTrips, rows: palette.rows.length, status: palette.testMatching.status, error: palette.errorMessage }))
   palette.cancel(); Qt.quit()
 } }
 Timer { interval: 40000; running: true; onTriggered: { console.log("FAIL timeout"); Qt.quit() } }
}
''' % json.dumps(queries))
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_BACKEND='software', QML_IMPORT_PATH=str(work), OMARCHY_PATH='/usr/share/omarchy')
    env.pop('DISPLAY', None); env.pop('WAYLAND_DISPLAY', None)
    t0 = time.time()
    r = subprocess.run(['quickshell','-p',str(work/'shell.qml')], env=env, capture_output=True, text=True, timeout=60)
    out = r.stdout + r.stderr
    res = [l for l in out.splitlines() if 'RESULT ' in l]
    state = [l for l in out.splitlines() if 'STATE ' in l]
    print(*state, sep='\n')
    if not res:
        print(out[-4000:]); sys.exit(1)
    data = json.loads(res[0].split('RESULT ',1)[1])
    import statistics as st
    keys = ['providers','documents','merge','rank','apply','end','total']
    print(f"[{label}] rows={data['rows']} status={data['status']} error={data['error']!r} keystrokes={len(data['samples'])}")
    print("phase       median   p90    max   (ms, per keystroke on the UI thread)")
    for k in keys:
        v = [s.get(k, 0) for s in data['samples']]
        print(f"{k:11} {st.median(v):6.1f} {sorted(v)[int(len(v)*0.9)]:6.1f} {max(v):6.1f}")
    print("runQuery calls per keystroke:", st.mean(data['calls']), "max", max(data['calls']))
    if data.get('providerMs'):
        print("provider query ms total over run:", json.dumps({k: [round(v,1), data['providerCalls'][k]] for k, v in sorted(data['providerMs'].items(), key=lambda kv: -kv[1])}))
        print("provider catalog ms total over run:", json.dumps({k: round(v,1) for k, v in sorted(data['catalogMs'].items(), key=lambda kv: -kv[1])}))
    if data['roundTrips']: print(f"embedding round trip ms: median {st.median(data['roundTrips']):.0f} max {max(data['roundTrips'])} n={len(data['roundTrips'])}")
    warn = [l for l in out.splitlines() if 'TypeError' in l or 'ReferenceError' in l or 'FAIL' in l]
    if warn: print("WARN", *warn[:5], sep='\n')
    Path(temp).joinpath('out.log').write_text(out)
    print('log:', Path(temp).joinpath('out.log').read_text().count('\n'), 'lines (temporary directory removed)')
