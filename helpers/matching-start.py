#!/usr/bin/env python3
"""Provision the pinned CPU runtime, then replace this process with its worker."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
child = None


def stop(signum, _frame):
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
    raise SystemExit(128 + signum)


def run(argv, env):
    global child
    child = subprocess.Popen(argv, env=env, stdout=sys.stderr, start_new_session=True)
    if child.wait() != 0:
        raise RuntimeError('Could not install the matching runtime; check your connection and uv installation')
    child = None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['small', 'large'], default='small')
    parser.add_argument('--install-only', action='store_true')
    parser.add_argument('--data-dir', type=Path, default=Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'keystroke/matching')
    args = parser.parse_args()
    data = args.data_dir
    data.mkdir(parents=True, exist_ok=True)
    lockfile = ROOT / 'matching/requirements.lock'
    fingerprint = hashlib.sha256(lockfile.read_bytes()).hexdigest() + sys.version.split()[0]
    runtime = data / 'runtime'
    marker = data / 'runtime-version'
    env = dict(os.environ, UV_PYTHON_DOWNLOADS='never', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false', HF_HUB_DISABLE_TELEMETRY='1')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with (data / 'install.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not (runtime / 'bin/python').exists() or not marker.exists() or marker.read_text() != fingerprint:
            print(json.dumps({'type':'status', 'message':'Installing matching runtime'}), flush=True)
            uv = shutil.which('uv')
            if not uv:
                raise RuntimeError('Smart Match needs uv; install uv and retry in Keystroke Settings')
            run([uv, 'venv', '--clear', '--python', sys.executable, str(runtime)], env)
            run([uv, 'pip', 'sync', '--python', str(runtime / 'bin/python'), '--require-hashes', str(lockfile)], env)
            marker.write_text(fingerprint)
    command = [str(runtime / 'bin/python'), '-u', str(ROOT / 'helpers/matching-worker.py'), '--model', args.model, '--data-dir', str(data)]
    if args.install_only:
        command.append('--install-only')
    os.execve(command[0], command, env)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'type':'error', 'message':str(exc)}), flush=True)
        sys.exit(1)
