#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/env.sh"
# Separate loopback port; never replaces the stable assistant on 18781.
# Eager execution is the initial compatibility baseline. Compare graph mode
# separately once audio works. Cap KV allocation rather than consuming spare RAM.
exec "$AUDIO_ENV/venv/bin/vllm" serve "${KEYSTROKE_AUDIO_MODEL:-google/gemma-4-E2B-it}" \
  --served-model-name keystroke-audio \
  --host 127.0.0.1 --port 18782 \
  --dtype bfloat16 --max-model-len 4096 --max-num-seqs 1 \
  --max-num-batched-tokens 1024 --kv-cache-memory-bytes 268435456 \
  --gpu-memory-utilization 0.45 --enable-prefix-caching \
  --limit-mm-per-prompt '{"audio":1,"image":0,"video":0}' \
  --mm-processor-cache-gb 0 --enforce-eager "$@"
