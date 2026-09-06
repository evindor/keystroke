#!/usr/bin/env bash
# Select the live backend. The heavy vLLM environment is prepared separately.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${1:-}"
case "$BACKEND" in vllm|voxtype) ;; *) echo 'Usage: bin/keystroke voice-backend vllm|voxtype' >&2; exit 2;; esac
AUDIO_ENV="$HOME/.local/share/keystroke/experiments/gemma-audio"
if [[ $BACKEND == vllm ]]; then
  for required in venv/bin/vllm driver/usr/lib/libze_intel_gpu.so.1 models/gemma-4-E2B-it-W4A16-AutoRound/model.safetensors.index.json; do
    [[ -e "$AUDIO_ENV/$required" ]] || { echo "Missing $AUDIO_ENV/$required. Prepare experiments/gemma-audio first." >&2; exit 1; }
  done
  install -Dm755 "$ROOT/helpers/vllm-serve.sh" "$HOME/.local/share/keystroke/vllm/serve.sh"
  install -Dm644 "$ROOT/helpers/keystroke-vllm.service" "$HOME/.config/systemd/user/keystroke-vllm.service"
fi
CONFIG="$HOME/.config/omarchy/keystroke.json"
mkdir -p "$(dirname "$CONFIG")"
if [[ -f $CONFIG ]]; then
  # Verify before touching running services; keep a unique rollback copy.
  jq -e 'type == "object"' "$CONFIG" >/dev/null
  cp "$CONFIG" "$CONFIG.before-$BACKEND-$(date +%s%N)"
fi
systemctl --user daemon-reload
if [[ $BACKEND == vllm ]]; then
  systemctl --user disable --now keystroke-llm.service
  systemctl --user enable --now keystroke-vllm.service
else
  if systemctl --user cat keystroke-vllm.service >/dev/null 2>&1; then systemctl --user disable --now keystroke-vllm.service; fi
  systemctl --user enable --now voxtype.service keystroke-llm.service
fi
python3 - "$CONFIG" "$BACKEND" <<'PY'
import json, os, sys, tempfile
from pathlib import Path
path = Path(sys.argv[1])
value = json.loads(path.read_text()) if path.exists() else {'version': 1}
voice = value.setdefault('voice', {})
voice['backend'] = sys.argv[2]
voice['audioEndpoint'] = 'http://127.0.0.1:18782'
fd, temp = tempfile.mkstemp(prefix='.keystroke-', dir=path.parent)
with os.fdopen(fd, 'w') as output:
    json.dump(value, output, indent=2); output.write('\n')
os.replace(temp, path)
PY
printf 'Voice backend: %s. The first vLLM startup takes about 90 seconds; it stays loaded afterwards.\n' "$BACKEND"
