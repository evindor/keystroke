#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_ENV=()
if [[ -n "${KEYSTROKE_AUDIO_MODEL:-}" ]]; then
  MODEL_ENV+=(--setenv="KEYSTROKE_AUDIO_MODEL=$KEYSTROKE_AUDIO_MODEL")
fi
# Transient, bounded experiment. Does not enable anything at login.
exec systemd-run --user --unit=keystroke-audio-experiment --collect \
  --property=MemoryMax=14G --property=MemorySwapMax=0 \
  --property=RuntimeMaxSec=20min --property=TimeoutStopSec=15 \
  --setenv="KEYSTROKE_AUDIO_ENV=${KEYSTROKE_AUDIO_ENV:-$HOME/.local/share/keystroke/experiments/gemma-audio}" \
  "${MODEL_ENV[@]}" \
  /usr/bin/bash "$ROOT/serve.sh" "$@"
