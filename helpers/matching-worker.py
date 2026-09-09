#!/usr/bin/env python3
"""Resident local embeddings over supplied metadata; outputs IDs, never actions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

MODELS = {
    'small': ('minishlab/potion-base-2M', '389b9f64be5aa4ae7a6bc6fe95ef20ce485ae5da'),
    'large': ('minishlab/potion-base-8M', 'bf8b056651a2c21b8d2565580b8569da283cab23'),
}
MAX_LINE = 4 * 1024 * 1024
MAX_ROWS = 6000


def emit(value):
    print(json.dumps(value, separators=(',', ':')), flush=True)


class Index:
    def __init__(self, model):
        self.model = model
        self.signature = None
        self.ids = []
        self.vectors = None
        self.cache = {}

    def update(self, rows):
        import numpy as np
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValueError('Invalid matching catalog')
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not isinstance(row.get('text'), str):
                raise ValueError('Invalid matching document')
            if not row['id'] or row['id'] in seen or len(row['id']) > 512 or len(row['text']) > 4096:
                raise ValueError('Invalid matching document size or duplicate ID')
            seen.add(row['id'])
        signature = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        if signature == self.signature:
            return
        missing = list(dict.fromkeys(r['text'] for r in rows if r['text'] not in self.cache))
        if missing:
            encoded = self.model.encode(missing)
            for text, vector in zip(missing, encoded):
                self.cache[text] = vector / max(float(np.linalg.norm(vector)), 1e-12)
        self.cache = {r['text']:self.cache[r['text']] for r in rows}
        self.ids = [r['id'] for r in rows]
        self.vectors = np.stack([self.cache[r['text']] for r in rows]) if rows else None
        self.signature = signature

    def query(self, text):
        import numpy as np
        if not isinstance(text, str) or len(text) > 1024:
            raise ValueError('Invalid matching query')
        if not text.strip() or self.vectors is None:
            return []
        vector = self.model.encode([text])[0]
        vector /= max(float(np.linalg.norm(vector)), 1e-12)
        scores = self.vectors @ vector
        order = np.argsort(-scores, kind='stable')[:30]
        return [{'id':self.ids[int(i)], 'score':float(scores[i])} for i in order if np.isfinite(scores[i])]


def serve(model, stream):
    index = Index(model)
    emit({'type':'ready'})
    while True:
        line = stream.readline(MAX_LINE + 1)
        if not line:
            return
        if len(line) > MAX_LINE:
            raise ValueError('Matching request is too large')
        request = {}
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or not isinstance(request.get('id'), int):
                raise ValueError('Invalid matching request')
            if 'rows' in request:
                index.update(request['rows'])
            emit({'type':'result', 'id':request['id'], 'matches':index.query(request.get('query'))})
        except (ValueError, TypeError, KeyError) as exc:
            emit({'type':'error', 'id':request.get('id') if isinstance(request, dict) else None, 'message':str(exc)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=MODELS, default='small')
    parser.add_argument('--model-dir', type=Path, help='directory holding config.json, tokenizer.json and model.safetensors (verified by matching-start.py)')
    parser.add_argument('--data-dir', type=Path, help='legacy huggingface_hub cache root, used when --model-dir is absent')
    parser.add_argument('--install-only', action='store_true')
    args = parser.parse_args()
    from model2vec import StaticModel
    files = ['config.json', 'tokenizer.json', 'model.safetensors']
    if args.model_dir is not None:
        location = args.model_dir
        if not all((location / f).exists() for f in files):
            raise FileNotFoundError('Model files are missing')
    else:
        from huggingface_hub import snapshot_download
        name, revision = MODELS[args.model]
        cache = args.data_dir / 'models'
        try:
            location = snapshot_download(name, revision=revision, cache_dir=cache, local_files_only=True, allow_patterns=files)
            if not all((Path(location) / f).exists() for f in files):
                raise FileNotFoundError('Model download incomplete')
        except (FileNotFoundError, OSError):
            emit({'type':'status', 'message':'Downloading ' + args.model + ' matching model'})
            location = snapshot_download(name, revision=revision, cache_dir=cache, allow_patterns=files)
    if args.install_only:
        # Loading validates a complete model before reporting installation success.
        StaticModel.from_pretrained(location)
        emit({'type':'installed', 'model':args.model})
        return
    emit({'type':'status', 'message':'Loading ' + args.model + ' matching model'})
    serve(StaticModel.from_pretrained(location), sys.stdin)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        emit({'type':'error', 'message':'Smart Match unavailable: ' + str(exc)})
        sys.exit(1)
