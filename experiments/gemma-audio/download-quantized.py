#!/usr/bin/env python3
"""Download the pinned INT4 audio checkpoint, excluding obsolete weight shards."""
import json
import os
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

REPO = 'Vishva007/gemma-4-E2B-it-W4A16-AutoRound'
REVISION = 'b5c22b35dcc1eb28dc20e801300ec221cd754d71'
root = Path(os.environ.get('KEYSTROKE_AUDIO_ENV',
            Path.home() / '.local/share/keystroke/experiments/gemma-audio'))
destination = root / 'models/gemma-4-E2B-it-W4A16-AutoRound'
info = HfApi().model_info(REPO, revision=REVISION, files_metadata=True)
index = json.loads(Path(hf_hub_download(REPO, 'model.safetensors.index.json',
                        revision=REVISION)).read_text())
weights = sorted(set(index['weight_map'].values()))
metadata = [f.rfilename for f in info.siblings
            if f.rfilename.endswith(('.json', '.jinja', '.model'))]
sizes = {f.rfilename: f.size for f in info.siblings}
print(json.dumps({'repo': REPO, 'revision': REVISION,
                  'weight_bytes': sum(sizes[f] for f in weights),
                  'weight_files': weights}), flush=True)
snapshot_download(REPO, revision=REVISION, local_dir=destination,
                  allow_patterns=metadata + weights, max_workers=2)
manifest = {'repo': REPO, 'revision': REVISION,
            'weights': {f: sizes[f] for f in weights},
            'total_weight_bytes': sum(sizes[f] for f in weights)}
(root / 'quantized-download.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(destination, flush=True)
