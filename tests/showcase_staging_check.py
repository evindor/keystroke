"""Live capture prepares its executable fixture in private, fresh staging."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capture', ROOT / 'tools/showcase/capture.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
seen = []


def inspect(source, fixtures):
    seen.append(source.parent)
    assert source.parent.stat().st_mode & 0o777 == 0o700
    assert (source / 'Keystroke.qml').is_file() and fixtures.is_file()
    assert str(source.parent / 'home') in (source / 'Keystroke.qml').read_text()
    env = dict(os.environ, KEYSTROKE_SHOWCASE_DEST=str(source),
               KEYSTROKE_SHOWCASE_HOME=str(source.parent / 'home'))
    before = (source / 'Keystroke.qml').read_bytes()
    result = subprocess.run([sys.executable, str(ROOT / 'tools/showcase/prepare.py')], env=env, capture_output=True)
    assert result.returncode != 0
    assert (source / 'Keystroke.qml').read_bytes() == before


with patch.object(capture, 'capture', inspect):
    capture.main()
assert seen and not seen[0].exists()

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    target = root / 'target'
    target.mkdir()
    link = root / 'plugin'
    link.symlink_to(target, target_is_directory=True)
    result = subprocess.run([sys.executable, str(ROOT / 'tools/showcase/prepare.py')],
                            env=dict(os.environ, KEYSTROKE_SHOWCASE_DEST=str(link)), capture_output=True)
    assert result.returncode != 0 and not list(target.iterdir())
print('PASS: private staging, cleanup, existing directory and symlink rejection')
