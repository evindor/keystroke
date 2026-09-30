#!/usr/bin/env python3
"""Check the real startup helper's version gate without launching Codex."""
import os
import pathlib
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='keystroke-codex-start-') as temp:
    path = pathlib.Path(temp)
    mock = path / 'codex'
    mock.write_text('''#!/usr/bin/env bash
if [[ "$1" == --version ]]; then
  printf '%s\\n' "$MOCK_VERSION"
  exit "${MOCK_VERSION_EXIT:-0}"
fi
printf '%s\\n' "$@"
''')
    mock.chmod(0o755)
    cases = [
        ('codex-cli 0.153.2', 65), ('codex-cli 0.159.1', 65),
        ('codex-cli 0.159.2', 0), ('codex-cli 0.159.3', 0),
        ('codex-cli 0.160.0', 0), ('codex-cli 0.1000.0', 0),
        ('codex-cli 1.0.0', 0), ('codex-cli 0.159.2-alpha.1', 65),
        ('garbage', 65), ('', 65),
    ]
    for index, (version, expected) in enumerate(cases):
        home = path / str(index)
        env = dict(os.environ, PATH=temp + ':' + os.environ['PATH'],
                   HOME=str(home), MOCK_VERSION=version)
        result = subprocess.run(['bash', str(root / 'helpers/codex-start.sh')],
                                env=env, capture_output=True, text=True)
        assert result.returncode == expected, (version, result)
        state = home / '.local/state/keystroke/questions'
        if expected == 0:
            assert state.is_dir(), version
            assert result.stdout.splitlines() == [
                'app-server', '--stdio', '--enable', 'fast_mode', '--disable',
                'hooks', '--disable', 'apps', '--disable', 'plugins'], result
        else:
            assert not state.exists(), version
            assert not result.stdout, result
            assert '0.159.2 or newer' in result.stderr, result
    env.update(MOCK_VERSION='', MOCK_VERSION_EXIT='127')
    result = subprocess.run(['bash', str(root / 'helpers/codex-start.sh')],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 65 and 'no Codex CLI' in result.stderr, result
print('PASS Codex minimum version, rejection before side effects, and launch arguments')
