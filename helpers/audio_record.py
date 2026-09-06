#!/usr/bin/env python3
"""One private microphone session -> resident vLLM; JSONL controls and events.

stdin: initial {endpoint,prompt,count}, followed by {action:stop|cancel}.
stdout: listening, level, preview, result, stopping, empty, error events.
Audio stays in memory. No model-selected command is ever executed here.
"""
import argparse
import array
import base64
import ctypes
import fcntl
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave

RATE = 16000
MAX_SECONDS = 60


class Cancelled(Exception):
    pass


def endpoint_url(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.password:
        raise ValueError('Voice audio requires a local HTTP endpoint')
    return value.rstrip('/')


def wav_bytes(pcm):
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as output:
        output.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        output.writeframes(pcm[:len(pcm) // 2 * 2])
    return stream.getvalue()


def transcript_preview(content):
    match = re.search(r'"transcript"\s*:\s*(")', content)
    if not match:
        return None
    fragment = content[match.start(1):]
    try:
        value, _ = json.JSONDecoder().raw_decode(fragment)
        return value if isinstance(value, str) else None
    except ValueError:
        try:
            return json.loads(fragment + '"')
        except ValueError:
            return None


def parse_result(content, count):
    text = content.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    value = json.loads(text)
    if not isinstance(value, dict) or not isinstance(value.get('transcript'), str):
        raise ValueError('Gemma returned an invalid transcript')
    index = value.get('index', 0)
    if type(index) is not int or not 0 <= index <= count:
        index = 0
    return {'text': value['transcript'].strip(), 'index': index}


def infer(endpoint, prompt, pcm, count, cancelled, preview):
    body = {'model': 'keystroke-audio', 'temperature': 0, 'max_tokens': 768,
            'stream': True, 'chat_template_kwargs': {'enable_thinking': False},
            'messages': [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': [
                {'type': 'input_audio', 'input_audio': {'format': 'wav', 'data': base64.b64encode(wav_bytes(pcm)).decode()}},
                {'type': 'text', 'text': 'Transcribe this speech and select an explicit catalog action, if any.'}]}]}
    request = urllib.request.Request(endpoint + '/v1/chat/completions',
                    data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    began = time.monotonic()
    content = ''
    previous = None
    with urllib.request.urlopen(request, timeout=30) as response:
        for line in response:
            if cancelled.is_set():
                raise Cancelled()
            if not line.startswith(b'data:'):
                continue
            data = line[5:].strip()
            if data == b'[DONE]':
                break
            event = json.loads(data)
            if event.get('error'):
                raise ValueError('Gemma could not process the recording')
            for choice in event.get('choices', []):
                content += choice.get('delta', {}).get('content') or ''
            current = transcript_preview(content)
            if current is not None and current != previous:
                preview(current)
                previous = current
    if cancelled.is_set():
        raise Cancelled()
    result = parse_result(content, count)
    result['ms'] = round((time.monotonic() - began) * 1000)
    return result


def stop_process(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)


def parent_death_signal():
    # Invoked before any helper threads are started. A killed UI/helper must
    # never leave a microphone reader running as an orphan.
    ctypes.CDLL(None).prctl(1, signal.SIGTERM)
    if os.getppid() == 1:
        os.kill(os.getpid(), signal.SIGTERM)


def run(config):
    endpoint = endpoint_url(str(config.get('endpoint', 'http://127.0.0.1:18782')))
    prompt = str(config['prompt'])
    count = int(config.get('count', 0))
    if len(prompt) > 100000 or not 0 <= count <= 2000:
        raise ValueError('The voice catalog is too large')
    with urllib.request.urlopen(endpoint + '/health', timeout=2) as response:
        if response.status != 200:
            raise ValueError('Gemma is still starting')
    cancelled = threading.Event()
    stopped = threading.Event()
    capture_done = threading.Event()
    output_lock = threading.Lock()
    pcm_lock = threading.Lock()
    pcm = bytearray()
    voiced = False
    capture_error = ''

    def emit(event, **fields):
        if cancelled.is_set():
            return
        with output_lock:
            print(json.dumps({'event': event, **fields}, ensure_ascii=False), flush=True)

    recorder = subprocess.Popen(['pw-record', '--raw', '--rate=16000', '--channels=1',
                                 '--format=s16', '--media-role=Communication', '-'],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                preexec_fn=parent_death_signal, bufsize=0)

    def interrupt(*_):
        cancelled.set()
        stopped.set()
        if recorder.poll() is None:
            recorder.terminate()
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)

    def controls():
        try:
            for line in sys.stdin:
                try:
                    action = json.loads(line).get('action')
                except (ValueError, AttributeError):
                    continue
                if action == 'cancel':
                    interrupt()
                    return
                if action == 'stop':
                    stopped.set()
                    if recorder.poll() is None:
                        recorder.terminate()
                    return
            interrupt()  # UI closed its pipe.
        except OSError:
            interrupt()

    def capture():
        nonlocal voiced, capture_error
        first = True
        try:
            while not stopped.is_set():
                chunk = recorder.stdout.read(3200)
                if not chunk:
                    break
                if first:
                    emit('listening')
                    first = False
                with pcm_lock:
                    remaining = MAX_SECONDS * RATE * 2 - len(pcm)
                    pcm.extend(chunk[:remaining])
                    length = len(pcm)
                values = array.array('h', chunk[:len(chunk) // 2 * 2])
                peak = max((abs(x) for x in values), default=0) / 32768
                rms = math.sqrt(sum(x * x for x in values) / max(1, len(values))) / 32768
                voiced = voiced or rms > .002
                emit('level', peak=peak, rms=rms)
                if length >= MAX_SECONDS * RATE * 2:
                    stopped.set()
                    recorder.terminate()
            if not stopped.is_set():
                capture_error = 'Microphone capture stopped unexpectedly'
                stopped.set()
        except OSError:
            if not stopped.is_set():
                capture_error = 'Could not read the microphone'
                stopped.set()
        finally:
            capture_done.set()

    threading.Thread(target=controls, daemon=True).start()
    threading.Thread(target=capture, daemon=True).start()
    started = time.monotonic()
    previous_size = 0
    previous_result = None
    next_partial = started + 1.0
    try:
        while not cancelled.is_set():
            final = stopped.is_set()
            if final:
                emit('stopping')
                stop_process(recorder)
                capture_done.wait(2)
            if capture_error:
                raise RuntimeError(capture_error)
            with pcm_lock:
                snapshot = bytes(pcm)
            if not snapshot and not final and time.monotonic() - started > 8:
                raise RuntimeError('No audio received from the microphone')
            if final and (len(snapshot) < RATE // 5 or not voiced):
                emit('empty')
                return
            if final or (voiced and len(snapshot) >= RATE * 2 and time.monotonic() >= next_partial
                         and len(snapshot) - previous_size >= RATE // 2):
                if final and len(snapshot) == previous_size and previous_result is not None:
                    result = previous_result
                else:
                    result = infer(endpoint, prompt, snapshot, count, cancelled,
                                   lambda text: emit('preview', text=text))
                    previous_size = len(snapshot)
                    previous_result = result
                emit('result', final=final, **result)
                if final:
                    return
                next_partial = time.monotonic() + .25
            time.sleep(.025)
    finally:
        cancelled.set()
        stop_process(recorder)
        capture_done.wait(2)
        with pcm_lock:
            pcm.clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    if args.probe:
        print(json.dumps({'detected': bool(shutil.which('pw-record'))}))
        return
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp'))
    lock_path = runtime / f'keystroke-audio-{os.getuid()}.lock'
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            config = json.loads(sys.stdin.readline())
            run(config)
        except Cancelled:
            pass
        except BlockingIOError:
            print(json.dumps({'event': 'error', 'message': 'Another voice recording is still active'}), flush=True)
        except Exception as error:
            message = 'Gemma is not ready; wait for the voice server to start' if isinstance(error, urllib.error.URLError) else str(error)
            print(json.dumps({'event': 'error', 'message': message[:300]}), flush=True)
            sys.exit(1)


if __name__ == '__main__':
    main()
