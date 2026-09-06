#!/usr/bin/env bash
set -euo pipefail
# Reuse the isolated, pinned XPU runtime prepared by experiments/gemma-audio.
# No global Python packages or system Intel drivers are replaced.
AUDIO_ENV="${KEYSTROKE_AUDIO_ENV:-$HOME/.local/share/keystroke/experiments/gemma-audio}"
export LD_LIBRARY_PATH="$AUDIO_ENV/driver/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ZE_ENABLE_ALT_DRIVERS="$AUDIO_ENV/driver/usr/lib/libze_intel_gpu.so.1"
export LEVEL_ZERO_V1_SDK_PATH="$AUDIO_ENV/driver/usr"
# The optional ARK kernel requires CPU instructions absent on this laptop.
export VLLM_XPU_INC_WNA16_BACKEND=w4a16
export HF_HOME="$AUDIO_ENV/huggingface"
export VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 OMP_NUM_THREADS=4
exec "$AUDIO_ENV/venv/bin/vllm" serve "$AUDIO_ENV/models/gemma-4-E2B-it-W4A16-AutoRound" \
  --served-model-name keystroke-audio --host 127.0.0.1 --port 18782 \
  --dtype bfloat16 --max-model-len 16384 --max-num-seqs 1 \
  --max-num-batched-tokens 1024 --kv-cache-memory-bytes 536870912 \
  --gpu-memory-utilization 0.25 --enable-prefix-caching \
  --limit-mm-per-prompt '{"audio":1,"image":0,"video":0}' \
  --mm-processor-cache-gb 0 --enforce-eager
