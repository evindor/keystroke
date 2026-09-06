#!/usr/bin/env python3
"""Generate known-text synthetic speech; never accesses the microphone."""
import argparse
import json
import os
from pathlib import Path
import subprocess

CASES = [
    ('browser', 'Open my browser please.', 'browser'),
    ('terminal', 'Please open a terminal.', 'terminal'),
    ('settings', 'Open the settings.', 'settings'),
    ('clipboard', 'Copy what I dictated to the clipboard.', 'clipboard'),
    ('weather', 'Tomorrow will probably be rainy.', None),
    ('description', 'The browser is already open.', None),
    ('negation', 'Do not open a browser.', None),
    ('unsupported', 'Make my window corners more rounded.', None),
]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--espeak', default='espeak-ng')
parser.add_argument('--data', type=Path, help='Parent of espeak-ng-data')
parser.add_argument('--output-dir', type=Path, required=True)
args = parser.parse_args()
args.output_dir.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
local_lib = Path(args.espeak).resolve().parent.parent / 'lib'
if local_lib.exists() and Path(args.espeak).is_absolute():
    env['LD_LIBRARY_PATH'] = str(local_lib) + ':' + env.get('LD_LIBRARY_PATH', '')
rows = []
for name, text, expected in CASES:
    wav = args.output_dir / (name + '.wav')
    command = [args.espeak, '-v', 'en-us', '-s', '150', '-w', str(wav)]
    if args.data:
        command.append('--path=' + str(args.data))
    subprocess.run(command + [text], env=env, check=True)
    rows.append({'wav': wav.name, 'text': text, 'command_id': expected,
                 'source': 'espeak-ng 1.52.0, en-us, 150 words/minute'})
(args.output_dir / 'cases.json').write_text(json.dumps(rows, indent=2) + '\n')
print(args.output_dir / 'cases.json')
