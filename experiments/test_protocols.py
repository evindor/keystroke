"""Offline checks for benchmark event ordering and full-request audio prefixes."""
import base64
from collections import deque
import importlib.util
import io
from pathlib import Path
import queue
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import contextlib
import wave


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cloud = load('cloud_benchmark', 'codex-cloud/benchmark.py')
audio = load('audio_benchmark', 'gemma-audio/benchmark.py')
runner = load('audio_runner', 'gemma-audio/run-quantized-test.py')


class ProtocolTests(unittest.TestCase):
    def test_failed_start_restores_previously_active_llm(self):
        with tempfile.TemporaryDirectory() as work:
            argv = ['run-quantized-test.py', 'speech.wav', '--output-dir', work]
            with patch('sys.argv', argv), patch.object(runner.signal, 'signal'), \
                 patch.object(runner, 'active', side_effect=[False, True, False, True]), \
                 patch.object(runner, 'command', return_value=SimpleNamespace(stdout='test-invocation', returncode=0)) as cmd, \
                 patch.object(runner.urllib.request, 'urlopen', side_effect=OSError('not ready')), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'exited during startup'):
                    runner.main()
            commands = [call.args for call in cmd.call_args_list]
            self.assertIn(('systemctl', '--user', 'stop', 'keystroke-llm.service'), commands)
            self.assertIn(('systemctl', '--user', 'stop', runner.UNIT), commands)
            self.assertIn(('systemctl', '--user', 'start', 'keystroke-llm.service'), commands)
            self.assertIn('"installed_llm_restored": true', (Path(work) / 'outcome.json').read_text())

    def test_failed_start_keeps_previously_inactive_llm_inactive(self):
        with tempfile.TemporaryDirectory() as work:
            argv = ['run-quantized-test.py', 'speech.wav', '--output-dir', work]
            with patch('sys.argv', argv), patch.object(runner.signal, 'signal'), \
                 patch.object(runner, 'active', return_value=False), \
                 patch.object(runner, 'command', return_value=SimpleNamespace(stdout='test-invocation', returncode=0)) as cmd, \
                 patch.object(runner.urllib.request, 'urlopen', side_effect=OSError('not ready')), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    runner.main()
            self.assertFalse(any('keystroke-llm.service' in call.args for call in cmd.call_args_list))

    def test_rpc_preserves_early_stream_timestamp(self):
        server = cloud.Server.__new__(cloud.Server)
        server.queue = queue.Queue()
        server.pending = deque()
        server.next_id = 0
        server.send = lambda message: None
        stamp = time.perf_counter()
        notification = {'method': 'item/agentMessage/delta', 'params': {'delta': 'hello'}}
        server.queue.put((stamp, notification))
        server.queue.put((stamp + .01, {'id': 1, 'result': {'ok': True}}))
        self.assertEqual(server.call('turn/start', {}), {'ok': True})
        self.assertEqual(server.receive(time.perf_counter() + 1), (stamp, notification))

    def test_approval_request_does_not_collide_with_client_rpc_id(self):
        server = cloud.Server.__new__(cloud.Server)
        server.queue = queue.Queue()
        server.pending = deque()
        server.next_id = 0
        sent = []
        server.send = sent.append
        stamp = time.perf_counter()
        server.queue.put((stamp, {'id': 1, 'method': 'item/commandExecution/requestApproval'}))
        server.queue.put((stamp, {'id': 1, 'result': {'ok': True}}))
        self.assertEqual(server.call('turn/start', {}), {'ok': True})
        self.assertEqual(sent[-1]['error']['code'], -32601)
        self.assertFalse(server.pending)

    def test_audio_prefixes_keep_start_and_include_whole_recording(self):
        samples = bytes(range(100))
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / 'speech.wav'
            with wave.open(str(path), 'wb') as output:
                output.setparams((1, 1, 100, 0, 'NONE', 'not compressed'))
                output.writeframes(samples)
            rows = list(audio.prefixes(path, [.25, .5, .5, 2]))
        self.assertEqual([r[0] for r in rows], [.25, .5, 1])
        for duration, payload in rows:
            with wave.open(io.BytesIO(payload), 'rb') as source:
                self.assertEqual(source.readframes(100), samples[:round(duration * 100)])
            body = audio.request_body([], payload, 'test-model')
            encoded = body['messages'][1]['content'][0]['input_audio']['data']
            self.assertEqual(base64.b64decode(encoded), payload)


if __name__ == '__main__':
    unittest.main()
