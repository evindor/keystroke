#!/usr/bin/env python3
"""Worker protocol, bounded input, catalog replacement and embedding cache checks."""
import importlib.util
import io
import json
from pathlib import Path
from contextlib import redirect_stdout

import numpy as np

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('matching_worker', root/'helpers/matching-worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

class Model:
    def __init__(self):
        self.calls = []
    def encode(self, texts):
        self.calls.append(list(texts))
        return np.array([[1.,0.] if 'screen' in t else [0.,1.] for t in texts], dtype=np.float32)

model = Model()
index = worker.Index(model)
rows = [{'id':'screen','text':'take a screenshot'}, {'id':'theme','text':'change theme'}]
index.update(rows)
assert index.query('screen')[0]['id'] == 'screen'
assert index.query('theme')[0]['id'] == 'theme'
count = len(model.calls)
index.update(rows)
assert len(model.calls) == count
index.update([{'id':'new-theme','text':'change theme'}])
assert len(model.calls) == count, 'unchanged document vectors must be reused'
assert list(index.cache) == ['change theme'], 'removed metadata must not remain cached'
assert [r['id'] for r in index.query('screen')] == ['new-theme'], 'removed IDs must never be returned'
for bad in [[rows[0], rows[0]], [{'id':'x','text':'x'*4097}], [{'id':'x'}], {}]:
    try:
        index.update(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid catalog accepted')
index.update([])
assert index.query('screen') == []
stream = io.StringIO('\n'.join(json.dumps(r) for r in [
    {'id':1,'rows':rows,'query':'screen'},
    {'id':2,'query':'theme'},
    {'id':3,'query':'x'*1025},
    {'id':4,'rows':[],'query':'screen'},
])+'\n')
output = io.StringIO()
with redirect_stdout(output):
    worker.serve(Model(), stream)
messages = [json.loads(line) for line in output.getvalue().splitlines()]
assert messages[0]['type'] == 'ready'
assert messages[1]['matches'][0]['id'] == 'screen'
assert messages[2]['matches'][0]['id'] == 'theme'
assert messages[3]['type'] == 'error' and messages[3]['id'] == 3
assert messages[4]['matches'] == []
assert all(set(r) == {'id','score'} for m in messages for r in m.get('matches', [])), 'worker must not return executable actions'
print('PASS matching worker: protocol, cache reuse/eviction, live catalog replacement, bounded input and IDs-only output')
