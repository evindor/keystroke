#!/usr/bin/env python3
"""Temporarily load a fixture in the existing Omarchy shell, capture, clean up."""
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ID = 'local.keystroke-showcase-' + str(time.time_ns())
TARGET = Path.home()/'.config/omarchy/plugins'/PLUGIN_ID

def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()

def call(method, data):
    return run('omarchy-shell','shell','call',PLUGIN_ID,method,json.dumps(data))

if TARGET.exists():
    raise SystemExit('Refusing to overwrite an existing capture plugin')
shutil.copytree('/tmp/keystroke-showcase-plugin', TARGET)
manifest = json.loads((TARGET/'manifest.json').read_text())
manifest['id'] = PLUGIN_ID
(TARGET/'manifest.json').write_text(json.dumps(manifest))
try:
    run('omarchy','plugin','validate',str(TARGET))
    run('omarchy-shell','shell','rescanPlugins')
    time.sleep(1)
    run('omarchy','plugin','enable',PLUGIN_ID)
    time.sleep(1)
    fixtures = json.loads(Path('/tmp/keystroke-showcase-fixtures.json').read_text())
    for name, fixture in fixtures.items():
        run('omarchy-shell','shell','summon',PLUGIN_ID,json.dumps(fixture))
        time.sleep(0.5)
        output = ROOT/'site/assets/screenshots'/f'{name}.png'
        result = call('screenshot',dict(path=str(output)))
        if result != 'capturing':
            raise RuntimeError(f'Capture failed: {result}')
        time.sleep(0.35)
        if not output.exists(): raise RuntimeError(f'No capture for {name}')
        print(name, output.stat().st_size, flush=True)
finally:
    subprocess.run(['omarchy-shell','shell','call',PLUGIN_ID,'cancel','{}'],capture_output=True)
    subprocess.run(['omarchy','plugin','disable',PLUGIN_ID],capture_output=True)
    shutil.rmtree(TARGET)
    subprocess.run(['omarchy-shell','shell','rescanPlugins'],capture_output=True)
