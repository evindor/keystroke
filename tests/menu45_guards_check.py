#!/usr/bin/env python3
"""Execute the vendored 4.5 guard batch against fake commands, never desktop actions."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
model = root / 'omarchy/MenuModel.js'

with tempfile.TemporaryDirectory(prefix='keystroke-menu-guards-') as temp:
    work = Path(temp)
    for name, body in {
        'pacman': 'exit 0',
        'pacman-conf': 'echo "$HOME/packages"',
        'omarchy-bar': 'echo probe >> "$HOME/probes"; echo top',
    }.items():
        path = work / name
        path.write_text('#!/bin/bash\n' + body + '\n')
        path.chmod(0o700)
    env = dict(os.environ, HOME=str(work), PATH=str(work)+':/usr/bin', XDG_RUNTIME_DIR=str(work))
    env.pop('OMARCHY_PACMAN_DB_PATH', None)
    (work / 'MenuModel.js').write_text(model.read_text())
    (work / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "MenuModel.js" as MenuModel
ShellRoot {
  Component.onCompleted: {
    console.log("GUARD_SCRIPT", JSON.stringify(MenuModel.guardScript(JSON.parse(Quickshell.env("TEST_GUARDS")))))
    Qt.callLater(function() { Qt.quit() })
  }
}
''')

    def script(items):
        fixture_env = dict(env, TEST_GUARDS=json.dumps(items), QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_BACKEND='software')
        result = subprocess.run(['quickshell', '-p', str(work/'shell.qml')], env=fixture_env, capture_output=True, text=True, timeout=8)
        output = result.stdout + result.stderr
        line = next(line for line in output.splitlines() if 'GUARD_SCRIPT ' in line)
        return json.loads(line.split('GUARD_SCRIPT ', 1)[1])

    batch = script({
        'first': {'when': '[[ "$(omarchy-bar position)" == "top" ]]'},
        'second': {'checked': '[[ "$(omarchy-bar position)" == "top" ]]', 'disabled': 'true'},
        'absent': {'disabled': 'false'},
    })
    result = subprocess.run(['bash', '-c', batch], env=env, capture_output=True, text=True, check=True)
    assert sorted(result.stdout.splitlines()) == ['absent:d:0', 'first:w:1', 'second:c:1', 'second:d:1'], result.stdout
    assert (work/'probes').read_text().splitlines() == ['probe'], 'repeated readers were not cached'
    broken = subprocess.run(['bash', '-c', script({'broken': {'when':'exit 7'}, 'after':{'disabled':'true'}})], env=env, capture_output=True, text=True)
    assert broken.returncode != 0, 'partial guard batch reported success'
    print('PASS 4.5 guard batch: visibility/check/disabled results, one reader invocation, failed group propagation')
