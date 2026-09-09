#!/usr/bin/env python3
"""Prepare the local matching engine and model, then replace this process with the worker.

Preferred: the compiled engine (matching/engine, Rust; ~16 MiB resident, ready in
tens of milliseconds). The static binary shipped in matching/bin is used when its
manifest names this machine's architecture and the current engine source;
otherwise the engine is built once per source revision with cargo into the data
directory. Without cargo, the pinned Python runtime (uv) from an earlier release
serves the same protocol. Model files are downloaded once per fixed revision and
verified against pinned SHA-256 digests; nothing else is fetched or executed."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    'small': {
        'repo': 'minishlab/potion-base-2M', 'revision': '389b9f64be5aa4ae7a6bc6fe95ef20ce485ae5da',
        'files': {
            'config.json': 'b2a89173391ca774c2d7323090a993a9a1553faa5b40eb37bb7cec6685fbea47',
            'tokenizer.json': 'e67e803f624fb4d67dea1c730d06e1067e1b14d830e2c2202569e3ef0f70bb50',
            'model.safetensors': 'f95ffde02ad06f63ae38eb9d400038cd5ccaf8411ec3cb650c6025113f96cbb8',
        },
    },
    'large': {
        'repo': 'minishlab/potion-base-8M', 'revision': 'bf8b056651a2c21b8d2565580b8569da283cab23',
        'files': {
            'config.json': '2a6ac0e9aaa356a68a5688070db78fc3a464fefe85d2f06a1905ce3718687553',
            'tokenizer.json': 'e67e803f624fb4d67dea1c730d06e1067e1b14d830e2c2202569e3ef0f70bb50',
            'model.safetensors': 'f65d0f325faadc1e121c319e2faa41170d3fa07d8c89abd48ca5358d9a223de2',
        },
    },
}
ENGINE_SOURCE = ROOT / 'matching/engine'
SHIPPED_ENGINE = ROOT / 'matching/bin/keystroke-matching'
child = None


def emit(value):
    print(json.dumps(value), flush=True)


def stop(signum, _frame):
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
    raise SystemExit(128 + signum)


def run(argv, env, failure):
    global child
    child = subprocess.Popen(argv, env=env, stdout=sys.stderr, start_new_session=True)
    if child.wait() != 0:
        raise RuntimeError(failure)
    child = None


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verified(path, expected):
    return path.is_file() and sha256(path) == expected


# ------------------------------------------------------------------- model
def prepare_model(name, data):
    spec = MODELS[name]
    target = data / 'models' / name / spec['revision']
    target.mkdir(parents=True, exist_ok=True)
    missing = [f for f, digest in spec['files'].items() if not verified(target / f, digest)]
    if not missing:
        return target
    # An earlier release cached the same files through huggingface_hub; reuse them.
    snapshot = data / 'models' / ('models--' + spec['repo'].replace('/', '--')) / 'snapshots' / spec['revision']
    for f in list(missing):
        if verified(snapshot / f, spec['files'][f]):
            shutil.copyfile(snapshot / f, target / f)
            missing.remove(f)
    if missing:
        emit({'type': 'status', 'message': 'Downloading ' + name + ' matching model'})
    for f in missing:
        url = 'https://huggingface.co/%s/resolve/%s/%s' % (spec['repo'], spec['revision'], f)
        with tempfile.NamedTemporaryFile(dir=target, prefix='.' + f + '.', delete=False) as tmp:
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'keystroke-matching'})
                with urllib.request.urlopen(request, timeout=60) as response:
                    shutil.copyfileobj(response, tmp)
            except Exception as exc:
                Path(tmp.name).unlink(missing_ok=True)
                raise RuntimeError('Could not download the matching model; check your connection and retry') from exc
        if sha256(Path(tmp.name)) != spec['files'][f]:
            Path(tmp.name).unlink(missing_ok=True)
            raise RuntimeError('Downloaded matching model did not match its pinned digest')
        os.replace(tmp.name, target / f)
    return target


# ------------------------------------------------------------------ engine
def engine_fingerprint():
    digest = hashlib.sha256()
    for path in sorted(list(ENGINE_SOURCE.glob('Cargo.*')) + list((ENGINE_SOURCE / 'src').glob('*.rs'))):
        digest.update(path.name.encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()[:16]


def shipped_engine(fingerprint):
    """The prebuilt binary, when its manifest matches this machine and the source it was built from."""
    manifest = SHIPPED_ENGINE.with_suffix('.json')
    if not os.access(SHIPPED_ENGINE, os.X_OK) or not manifest.is_file():
        return None
    try:
        info = json.loads(manifest.read_text())
    except ValueError:
        return None
    if info.get('machine') != platform.machine() or info.get('source') != fingerprint:
        return None
    return SHIPPED_ENGINE


def prepare_engine(data, env):
    if not ENGINE_SOURCE.is_dir():
        return None
    fingerprint = engine_fingerprint()
    shipped = shipped_engine(fingerprint)
    if shipped is not None:
        return shipped
    built = data / 'engine' / fingerprint / 'keystroke-matching'
    if os.access(built, os.X_OK):
        return built
    cargo = shutil.which('cargo')
    if not cargo:
        return None
    emit({'type': 'status', 'message': 'Building matching engine'})
    target = data / 'engine' / 'target'
    run([cargo, 'build', '--release', '--locked', '--quiet', '--manifest-path', str(ENGINE_SOURCE / 'Cargo.toml'), '--target-dir', str(target)],
        env, 'Could not build the matching engine; check your Rust toolchain or install uv for the Python runtime')
    built.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target / 'release' / 'keystroke-matching', built)
    built.chmod(0o755)
    # Only the finished binary is kept; intermediate objects are large.
    shutil.rmtree(target, ignore_errors=True)
    for stale in (data / 'engine').iterdir():
        if stale.is_dir() and stale != built.parent:
            shutil.rmtree(stale, ignore_errors=True)
    return built


# ---------------------------------------------------------- python fallback
def prepare_python_runtime(data, env):
    lockfile = ROOT / 'matching/requirements.lock'
    fingerprint = hashlib.sha256(lockfile.read_bytes()).hexdigest() + sys.version.split()[0]
    runtime = data / 'runtime'
    marker = data / 'runtime-version'
    if not (runtime / 'bin/python').exists() or not marker.exists() or marker.read_text() != fingerprint:
        emit({'type': 'status', 'message': 'Installing matching runtime'})
        uv = shutil.which('uv')
        if not uv:
            raise RuntimeError('Smart Match needs cargo (Rust) or uv (Python); install one and retry in Keystroke Settings')
        run([uv, 'venv', '--clear', '--python', sys.executable, str(runtime)], env, 'Could not install the matching runtime; check your connection and uv installation')
        run([uv, 'pip', 'sync', '--python', str(runtime / 'bin/python'), '--require-hashes', str(lockfile)], env, 'Could not install the matching runtime; check your connection and uv installation')
        marker.write_text(fingerprint)
    return runtime / 'bin/python'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=sorted(MODELS), default='small')
    parser.add_argument('--install-only', action='store_true')
    parser.add_argument('--engine', choices=['auto', 'native', 'python'], default='auto', help='auto prefers the compiled engine')
    parser.add_argument('--engine-fingerprint', action='store_true', help='print the engine source fingerprint and exit')
    parser.add_argument('--data-dir', type=Path, default=Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'keystroke/matching')
    args = parser.parse_args()
    if args.engine_fingerprint:
        print(engine_fingerprint())
        return
    data = args.data_dir
    data.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, UV_PYTHON_DOWNLOADS='never', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false', HF_HUB_DISABLE_TELEMETRY='1')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with (data / 'install.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        model_dir = prepare_model(args.model, data)
        engine = prepare_engine(data, env) if args.engine != 'python' else None
        if engine is None and args.engine == 'native':
            raise RuntimeError('The compiled matching engine is unavailable')
        if engine is None:
            python = prepare_python_runtime(data, env)
    if engine is not None:
        command = [str(engine), '--model-dir', str(model_dir), '--model', args.model]
    else:
        command = [str(python), '-u', str(ROOT / 'helpers/matching-worker.py'), '--model', args.model, '--model-dir', str(model_dir)]
    if args.install_only:
        command.append('--install-only')
    os.execve(command[0], command, env)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        emit({'type': 'error', 'message': str(exc)})
        sys.exit(1)
