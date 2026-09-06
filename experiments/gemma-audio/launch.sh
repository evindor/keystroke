#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Transient, bounded experiment. Does not enable anything at login.
exec systemd-run --user --unit=keystroke-audio-experiment --collect \
  --property=MemoryMax=14G --property=MemorySwapMax=0 \
  --property=RuntimeMaxSec=20min --property=TimeoutStopSec=15 \
  --setenv="KEYSTROKE_AUDIO_ENV=${KEYSTROKE_AUDIO_ENV:-$HOME/.local/share/keystroke/experiments/gemma-audio}" \
  /usr/bin/bash "$ROOT/serve.sh" "$@"
