#!/usr/bin/env bash
# Source only for the experiment; the installed voice services do not read this.
AUDIO_ENV="${KEYSTROKE_AUDIO_ENV:-$HOME/.local/share/keystroke/experiments/gemma-audio}"
export LD_LIBRARY_PATH="$AUDIO_ENV/driver/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ZE_ENABLE_ALT_DRIVERS="$AUDIO_ENV/driver/usr/lib/libze_intel_gpu.so.1"
export LEVEL_ZERO_V1_SDK_PATH="$AUDIO_ENV/driver/usr"
export HF_HOME="$AUDIO_ENV/huggingface"
export VLLM_NO_USAGE_STATS=1
export DO_NOT_TRACK=1
export OMP_NUM_THREADS=4
