#!/usr/bin/env python3
"""Offscreen palette-open benchmark.

Opens the real palette repeatedly (offscreen, installed Quickshell, this
machine's providers) and reports, per open: how long open() blocked the UI
thread, the CPU time Quickshell and its children used while the open settled,
and the processes it spawned. A process is seen by polling /proc, so ones that
live under ~2 ms can be missed; counts are a floor.

Usage: tools/bench_open.py [checkout] [label] [opens]
"""
import json, os, re, shutil, statistics as st, subprocess, sys, tempfile, threading, time
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
label = sys.argv[2] if len(sys.argv) > 2 else 'run'
opens = int(sys.argv[3]) if len(sys.argv) > 3 else 8
TICK = os.sysconf('SC_CLK_TCK')

def cpu_ms(pid):
    f = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return sum(int(f[i]) for i in (11, 12, 13, 14)) * 1000 / TICK   # utime stime cutime cstime

def descendants(pid):
    out, todo = {}, [pid]
    while todo:
        p = todo.pop()
        try:
            for t in os.listdir(f'/proc/{p}/task'):
                for c in Path(f'/proc/{p}/task/{t}/children').read_text().split():
                    c = int(c)
                    if c not in out:
                        out[c] = None; todo.append(c)
        except OSError:
            pass
    return out

with tempfile.TemporaryDirectory(prefix='keystroke-bench-') as temp:
    work = Path(temp); project = work / 'project'
    shutil.copytree(root, project, ignore=shutil.ignore_patterns('.git', '.claude', '.agents', '.codex', 'tests', '__pycache__', 'experiments', 'site', 'assets', 'docs'))
    (work / 'qs').symlink_to('/usr/share/omarchy/shell')
    src = project / 'Keystroke.qml'; qml = src.read_text()
    qml = qml.replace('  PanelWindow {', '  Window {\n    transientParent: null\n    width: 1000; height: 800')
    qml = qml.replace('    anchors { top: true; bottom: true; left: true; right: true }\n', '')
    src.write_text('\n'.join(l for l in qml.splitlines() if 'exclusionMode:' not in l and 'WlrLayershell.' not in l))
    (work / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "project"
ShellRoot {
 id: test
 property int n: 0
 Keystroke { id: palette; omarchyPath: "/usr/share/omarchy" }
 Timer { id: start; interval: 3000; running: true; onTriggered: { palette.shell = ({ pluginId: "bench" }); step.start() } }
 Timer { id: step; interval: 2500; repeat: true; onTriggered: {
   if (test.n > 0) { console.log("MARK end " + test.n); palette.cancel() }
   if (test.n >= %d + 1) { step.stop(); console.log("MARK done"); Qt.quit(); return }
   test.n++
   console.log("MARK start " + test.n)
   var t = Date.now(); palette.open('{}'); console.log("MARK open " + test.n + " " + (Date.now() - t))
 } }
 Timer { interval: 60000; running: true; onTriggered: { console.log("MARK timeout"); Qt.quit() } }
}
''' % opens)
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_BACKEND='software', QML_IMPORT_PATH=str(work), OMARCHY_PATH='/usr/share/omarchy')
    env.pop('DISPLAY', None); env.pop('WAYLAND_DISPLAY', None)
    proc = subprocess.Popen(['quickshell', '-p', str(work / 'shell.qml')], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    seen = {}            # pid -> (cmdline, open index) for processes started inside an open window
    state = {'n': 0, 'live': False}
    stop = threading.Event()
    def watch():
        while not stop.is_set():
            if state['live']:
                for pid in descendants(proc.pid):
                    if pid not in seen:
                        try: cmd = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace').strip()
                        except OSError: continue
                        if cmd: seen[pid] = (cmd, state['n'])
            time.sleep(0.001)
    threading.Thread(target=watch, daemon=True).start()

    cpu0, rows = 0, []
    open_ms = {}
    for line in proc.stdout:
        m = re.search(r'MARK (\w+)\s*(\d*)\s*(\d*)', line)
        if not m: continue
        kind, n, extra = m.group(1), int(m.group(2) or 0), m.group(3)
        if kind == 'start':
            state['n'] = n; state['live'] = True; cpu0 = cpu_ms(proc.pid)
        elif kind == 'open':
            open_ms[n] = int(extra)
        elif kind == 'end':
            state['live'] = False
            rows.append((n, cpu_ms(proc.pid) - cpu0))
        elif kind in ('done', 'timeout'):
            break
    stop.set()
    try: proc.wait(timeout=10)
    except subprocess.TimeoutExpired: proc.kill()

# the first open also pays one-time start-up work; report the steady state
steady = [(n, c) for n, c in rows if n > 1]
if not steady:
    print('no samples'); sys.exit(1)
def short(cmd):
    a = cmd.split()
    return ' '.join(a[:3])[:70]
per_open = {n: [v[0] for v in seen.values() if v[1] == n] for n, _ in steady}
print(f'[{label}] opens measured: {len(steady)} (first open discarded)')
print(f'open() blocked UI thread, ms   median {st.median(open_ms[n] for n, _ in steady):6.1f}   max {max(open_ms[n] for n, _ in steady):6.1f}')
print(f'CPU per open (self+children), ms   median {st.median(c for _, c in steady):6.1f}   max {max(c for _, c in steady):6.1f}')
print(f'processes spawned per open     median {st.median(len(v) for v in per_open.values()):6.1f}')
kinds = {}
for n, cmds in per_open.items():
    for c in cmds: kinds[short(c)] = kinds.get(short(c), 0) + 1
print('spawned processes (total over measured opens):')
for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])[:14]:
    print(f'  {v:4d}  {k}')
print('RESULT ' + json.dumps({'label': label, 'open_ms': [open_ms[n] for n, _ in steady], 'cpu_ms': [c for _, c in steady], 'spawned': [len(v) for v in per_open.values()]}))
