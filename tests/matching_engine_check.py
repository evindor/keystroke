#!/usr/bin/env python3
"""Compiled engine: builds from source, speaks the worker protocol, and tokenizes
exactly like Hugging Face `tokenizers` on a synthetic WordPiece model (the real
POTION model is also compared when it is installed locally)."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

from tokenizers import Tokenizer

root = Path(__file__).resolve().parents[1]
engine_src = root / 'matching/engine'
tricky = ["Hello World!", "Übermäßig café naïve", "野口里佳 Noguchi", "don't stop-me_now  x", "\x00weird�\tchars", "a" * 120, "emoji 😀 test",
          "ǅ İstanbul ﬁle", "", "   ", "open the browser", "Volume up!!", "screen-shot (region)", "SUPER+SHIFT+Q", "Straße", "ΣΊΣΥΦΟΣ", "①②③ 𝔘𝔫𝔦𝔠𝔬𝔡𝔢",
          "​zero​width", "tab\tsep\nnl\rcr", "café́ combining", "ｆｕｌｌｗｉｄｔｈ", "русский текст", "日本語のテキスト", "🇺🇸 flags 👨‍👩‍👧", "a·b•c", "path/to/file.txt", "50% of 80"]


def build(target):
    subprocess.run(['cargo', 'build', '--release', '--locked', '--quiet', '--manifest-path', str(engine_src / 'Cargo.toml'), '--target-dir', str(target)], check=True)
    return target / 'release' / 'keystroke-matching'


def synthetic_model(directory):
    words = ['[PAD]', '[UNK]', '[CLS]', '[SEP]', 'take', 'a', 'screen', '##shot', 'change', 'theme', 'the', 'open', 'browser', '##s', '!', 'é', 'ab', '##c']
    vocab = {w: i for i, w in enumerate(words)}
    tokenizer = {
        'version': '1.0', 'truncation': None, 'padding': None,
        'added_tokens': [{'id': i, 'content': w, 'single_word': False, 'lstrip': False, 'rstrip': False, 'normalized': False, 'special': True} for i, w in enumerate(words[:4])],
        'normalizer': {'type': 'BertNormalizer', 'clean_text': True, 'handle_chinese_chars': True, 'strip_accents': None, 'lowercase': True},
        'pre_tokenizer': {'type': 'BertPreTokenizer'},
        'post_processor': None, 'decoder': {'type': 'WordPiece', 'prefix': '##', 'cleanup': True},
        'model': {'type': 'WordPiece', 'unk_token': '[UNK]', 'continuing_subword_prefix': '##', 'max_input_chars_per_word': 100, 'vocab': vocab},
    }
    (directory / 'tokenizer.json').write_text(json.dumps(tokenizer))
    (directory / 'config.json').write_text(json.dumps({'model_type': 'model2vec', 'hidden_dim': 2, 'normalize': True}))
    # Two dimensions: "screen" words point one way, everything else the other.
    rows = []
    for w in words:
        rows.append((1.0, 0.0) if 'screen' in w or 'shot' in w else (0.0, 1.0))
    data = b''.join(struct.pack('<2f', *r) for r in rows)
    header = json.dumps({'embeddings': {'dtype': 'F32', 'shape': [len(words), 2], 'data_offsets': [0, len(data)]}}).encode()
    (directory / 'model.safetensors').write_bytes(struct.pack('<Q', len(header)) + header + data)


def tokenize_with(binary, model_dir, texts):
    proc = subprocess.run([binary, '--model-dir', str(model_dir), '--tokenize'], input=''.join(json.dumps(t) + '\n' for t in texts), capture_output=True, text=True, check=True)
    return [json.loads(line) for line in proc.stdout.splitlines()]


def parity(binary, model_dir, texts, label):
    hf = Tokenizer.from_file(str(model_dir / 'tokenizer.json'))
    unk = hf.token_to_id('[UNK]')
    expected = [[i for i in hf.encode(t, add_special_tokens=False).ids if i != unk] for t in texts]
    got = tokenize_with(binary, model_dir, texts)
    bad = [(t, e, g) for t, e, g in zip(texts, expected, got) if e != g]
    assert len(got) == len(texts) and not bad, (label, bad[:5])
    print('ok tokenizer parity (%s): %d texts' % (label, len(texts)))


with tempfile.TemporaryDirectory(prefix='keystroke-engine-') as temp:
    work = Path(temp)
    binary = build(work / 'target')
    model = work / 'model'
    model.mkdir()
    synthetic_model(model)
    corpus = tricky + ['take a screenshot', 'Take A SCREENSHOT!', 'change theme', 'open the browsers', 'abc ab c é é', 'screenshots', 'x' * 101]
    parity(binary, model, corpus, 'synthetic')

    proc = subprocess.Popen([binary, '--model-dir', str(model)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    def ask(message):
        proc.stdin.write(json.dumps(message) + '\n'); proc.stdin.flush()
        return json.loads(proc.stdout.readline())
    assert json.loads(proc.stdout.readline())['type'] == 'ready'
    rows = [{'id': 'screen', 'text': 'take a screenshot'}, {'id': 'theme', 'text': 'change theme'}]
    reply = ask({'id': 1, 'rows': rows, 'query': 'screen'})
    assert reply['type'] == 'result' and reply['matches'][0]['id'] == 'screen', reply
    assert all(set(m) == {'id', 'score'} for m in reply['matches']), 'engine must not return executable actions'
    assert ask({'id': 2, 'query': 'theme'})['matches'][0]['id'] == 'theme'
    assert ask({'id': 3, 'query': 'x' * 1025})['type'] == 'error'
    assert ask({'id': 4, 'rows': [{'id': 'new-theme', 'text': 'change theme'}], 'query': 'screen'})['matches'] == [{'id': 'new-theme', 'score': 0.0}], 'removed IDs must never be returned'
    for bad in [[rows[0], rows[0]], [{'id': 'x', 'text': 'x' * 4097}], [{'id': 'x'}], {}]:
        assert ask({'id': 5, 'rows': bad, 'query': 'a'})['type'] == 'error', bad
    assert ask({'id': 6, 'rows': [], 'query': 'screen'})['matches'] == []
    assert ask({'query': 'no id'})['type'] == 'error'
    assert ask({'id': 7, 'query': ''})['matches'] == []
    proc.stdin.close()
    assert proc.wait(timeout=5) == 0
    print('ok protocol: ready, results, catalog replacement, bounded input, IDs-only output')

    # The shipped binary must be current (built from this source) and must run.
    shipped = root / 'matching/bin/keystroke-matching'
    manifest = json.loads(shipped.with_suffix('.json').read_text())
    fingerprint = subprocess.run([sys.executable, str(root / 'helpers/matching-start.py'), '--engine-fingerprint'], capture_output=True, text=True, check=True).stdout.strip()
    assert manifest['source'] == fingerprint, 'matching/bin/keystroke-matching is stale: run bin/keystroke engine'
    import hashlib
    assert manifest['sha256'] == hashlib.sha256(shipped.read_bytes()).hexdigest(), 'shipped engine does not match its manifest'
    if manifest['machine'] == os.uname().machine:
        parity(shipped, model, corpus, 'shipped binary')
    else:
        print('skip: shipped engine is for', manifest['machine'])

    installed = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'keystroke/matching/models/small'
    snapshots = sorted(installed.glob('*/tokenizer.json')) if installed.is_dir() else []
    if snapshots:
        real = snapshots[-1].parent
        descriptions = list(json.load(open(root / 'matching/descriptions.json')).values())
        parity(binary, real, tricky + descriptions, 'installed small model')
    else:
        print('skip: no installed small model for real-vocabulary parity')
print('PASS matching engine: build, protocol and tokenizer parity')
