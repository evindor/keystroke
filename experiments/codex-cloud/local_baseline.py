#!/usr/bin/env python3
"""Same small classifier prompt against the installed local llama-server."""
import argparse
import importlib.util
import json
from pathlib import Path
from benchmark import CASES, INSTRUCTIONS, SCHEMA


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    path = Path(__file__).parent.parent / 'gemma-audio/benchmark.py'
    spec = importlib.util.spec_from_file_location('audio_benchmark', path)
    audio = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audio)
    rows = []
    for phrase, expected in CASES:
        body = {
            'model': 'keystroke', 'temperature': 0, 'max_tokens': 128,
            'stream': True, 'stream_options': {'include_usage': True},
            'chat_template_kwargs': {'enable_thinking': False},
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'route', 'strict': True, 'schema': SCHEMA}},
            'messages': [{'role': 'system', 'content': INSTRUCTIONS},
                         {'role': 'user', 'content': phrase}],
        }
        row = audio.infer('http://127.0.0.1:18781', body)
        row.update(phrase=phrase, correct=isinstance(row['parsed'], dict)
                   and row['parsed'].get('route') == expected)
        rows.append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, indent=2) + '\n')
        print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
