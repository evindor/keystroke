#!/usr/bin/env python3
"""Drive the actual capture helper with synthetic PCM and a streaming HTTP peer."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import wave

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audio_record', ROOT/'helpers/audio_record.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.parse_result('{"transcript":"hello","index":true}', 2)['index'] == 0
assert module.parse_result('{"transcript":"hello","index":3}', 2)['index'] == 0
assert module.transcript_preview('{"transcript":"hello') == 'hello'
assert module.transcript_preview('{"transcript":"hi\\') is None
requests = []
class Server(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        self.send_response(200); self.end_headers()
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        audio = body['messages'][1]['content'][0]['input_audio']['data']
        with wave.open(io.BytesIO(base64.b64decode(audio))) as recording:
            frames = recording.getnframes()
            assert recording.getframerate() == 16000
            assert recording.getnchannels() == 1
        requests.append(frames)
        self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
        content = json.dumps({'transcript': 'First words' if len(requests) == 1 else 'Entire request corrected.', 'index': 1})
        try:
            for part in [content[:23], content[23:]]:
                self.wfile.write(('data: ' + json.dumps({'choices':[{'delta':{'content':part}}]}) + '\n\n').encode()); self.wfile.flush()
                time.sleep(.03)
            self.wfile.write(b'data: [DONE]\n\n')
        except BrokenPipeError: pass
server = ThreadingHTTPServer(('127.0.0.1', 0), Server)
threading.Thread(target=server.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory(prefix='keystroke-audio-test-') as work:
    directory = Path(work)
    recorder = directory/'pw-record'
    recorder.write_text('''#!/usr/bin/python3
import os, pathlib, struct, sys, time
pathlib.Path(__file__).with_name('recorder.pid').write_text(str(os.getpid()))
while True:
    sys.stdout.buffer.write(struct.pack('<h', 1800) * 1600)
    sys.stdout.buffer.flush()
    time.sleep(.1)
''')
    recorder.chmod(0o700)
    env = dict(os.environ, PATH=str(directory)+':'+os.environ['PATH'], XDG_RUNTIME_DIR=work)
    def start():
        proc = subprocess.Popen(['python3', str(ROOT/'helpers/audio_record.py')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        proc.stdin.write(json.dumps({'endpoint':f'http://127.0.0.1:{server.server_port}', 'prompt':'test', 'count':2})+'\n'); proc.stdin.flush()
        events = queue.Queue()
        def read():
            for line in proc.stdout: events.put(json.loads(line))
        threading.Thread(target=read, daemon=True).start()
        return proc, events
    def until(events, predicate):
        deadline = time.monotonic()+8
        while time.monotonic()<deadline:
            item = events.get(timeout=8)
            assert item['event'] != 'error', item
            if predicate(item): return item
        raise AssertionError('event timeout')
    proc, events = start()
    until(events, lambda e:e['event']=='result' and not e['final'])
    time.sleep(.35)
    proc.stdin.write('{"action":"stop"}\n'); proc.stdin.flush()
    final = until(events, lambda e:e['event']=='result' and e['final'])
    proc.wait(timeout=4)
    assert final['text'] == 'Entire request corrected.', final
    assert len(requests)>=2 and requests[-1]>requests[0], requests
    assert requests == sorted(requests), requests
    assert proc.returncode == 0, proc.stderr.read()
    proc, events = start()
    until(events, lambda e:e['event']=='listening')
    pid = int((directory/'recorder.pid').read_text())
    proc.stdin.write('{"action":"cancel"}\n'); proc.stdin.flush()
    proc.wait(timeout=4)
    assert not Path(f'/proc/{pid}').exists(), 'orphan microphone'
    assert all(event['event'] != 'result' for event in list(events.queue)), 'cancelled result leaked'
server.shutdown()
print('PASS: native capture streams whole revisions, corrects final text, validates indexes, and cancels without an orphan microphone')
