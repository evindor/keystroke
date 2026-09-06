#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/env.sh"
# Separate loopback port; never replaces the stable assistant on 18781.
# INT4 weights, BF16 activations and audio encoder. Never defaults to full BF16
# weights. Download the pinned checkpoint with download-quantized.py first.
exec "$AUDIO_ENV/venv/bin/vllm" serve "${KEYSTROKE_AUDIO_MODEL:-$AUDIO_ENV/models/gemma-4-E2B-it-W4A16-AutoRound}" \
  --served-model-name keystroke-audio \
  --host 127.0.0.1 --port 18782 \
  --dtype bfloat16 --max-model-len 2048 --max-num-seqs 1 \
  --max-num-batched-tokens 1024 --kv-cache-memory-bytes 268435456 \
  --gpu-memory-utilization 0.25 --enable-prefix-caching \
  --limit-mm-per-prompt '{"audio":1,"image":0,"video":0}' \
  --mm-processor-cache-gb 0 --enforce-eager "$@"
