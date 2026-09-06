#!/usr/bin/env python3
"""Temporarily swap local LLMs, test native audio, and restore the installed LLM."""
import argparse
import json
from pathlib import Path
import subprocess
import signal
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
UNIT = 'keystroke-audio-experiment.service'


def command(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True)


def active(unit):
    return command('systemctl', '--user', 'is-active', '--quiet', unit, check=False).returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--startup-timeout', type=int, default=300)
    parser.add_argument('--server-arg', action='append', default=[])
    parser.add_argument('--cases', type=Path, help='JSON list of WAV paths and expected command IDs')
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Experiment interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if active(UNIT):
        raise RuntimeError('An experiment is already running; do not interrupt it')
    restore = active('keystroke-llm.service')
    invocation = None
    started = time.perf_counter()
    outcome = {'restore_installed_llm': restore, 'audio_inference_passed': False}
    try:
        if restore:
            command('systemctl', '--user', 'stop', 'keystroke-llm.service')
        command('bash', str(ROOT / 'launch.sh'), *args.server_arg)
        invocation = command('systemctl', '--user', 'show', UNIT,
                             '-p', 'InvocationID', '--value').stdout.strip()
        deadline = time.perf_counter() + args.startup_timeout
        while True:
            try:
                with urllib.request.urlopen('http://127.0.0.1:18782/health', timeout=2) as r:
                    if r.status == 200:
                        break
            except (OSError, TimeoutError):
                pass
            if not active(UNIT):
                raise RuntimeError('vLLM exited during startup; see server.log')
            if time.perf_counter() > deadline:
                raise TimeoutError('vLLM did not become ready before startup deadline')
            time.sleep(1)
        outcome['startup_seconds'] = round(time.perf_counter() - started, 3)
        outcome['memory_before_inference'] = command('systemctl', '--user', 'show', UNIT,
                            '-p', 'MemoryCurrent', '-p', 'MemoryPeak').stdout.strip()
        print(json.dumps(outcome), flush=True)
        result = command('python', str(ROOT / 'benchmark.py'), str(args.wav),
                         '--prefix-seconds', '2', '4', '--repeats', '2',
                         '--output', str(args.output_dir / 'audio.json'), check=False)
        (args.output_dir / 'client.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError('Native audio request failed; see client.log and server.log')
        rows = json.loads((args.output_dir / 'audio.json').read_text())
        outcome['audio_inference_passed'] = all(row['valid_selection'] for row in rows)
        if args.cases:
            cases=json.loads(args.cases.read_text())
            routed=[]
            for index, case in enumerate(cases):
                path=args.cases.parent / case['wav']
                expected=case['command_id'] if case['command_id'] is not None else 'none'
                result=command('python',str(ROOT / 'benchmark.py'),str(path),
                    '--expected-command',expected,'--repeats','2',
                    '--output',str(args.output_dir / f'case-{index}.json'),check=False)
                (args.output_dir / f'case-{index}.log').write_text(result.stdout + result.stderr)
                if result.returncode:
                    raise RuntimeError(f'Audio case {index} failed')
                routed.extend(json.loads((args.output_dir / f'case-{index}.json').read_text()))
            outcome['routing_correct_count']=sum(row.get('routing_correct',False) for row in routed)
            outcome['routing_test_count']=len(routed)
        outcome['memory_after_inference'] = command('systemctl', '--user', 'show', UNIT,
                            '-p', 'MemoryCurrent', '-p', 'MemoryPeak').stdout.strip()
    except BaseException as error:
        outcome['error'] = str(error)
        raise
    finally:
        command('systemctl', '--user', 'stop', UNIT, check=False)
        if invocation:
            log = command('journalctl', '--user', '_SYSTEMD_INVOCATION_ID=' + invocation,
                          '--no-pager', '-o', 'cat', check=False).stdout
            (args.output_dir / 'server.log').write_text(log)
        if restore:
            result = command('systemctl', '--user', 'start', 'keystroke-llm.service', check=False)
            outcome['installed_llm_restored'] = result.returncode == 0 and active('keystroke-llm.service')
        (args.output_dir / 'outcome.json').write_text(json.dumps(outcome, indent=2) + '\n')
        print(json.dumps(outcome), flush=True)


if __name__ == '__main__':
    main()
