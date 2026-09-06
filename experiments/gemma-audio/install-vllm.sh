#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/env.sh"
# Pin the Intel wheel explicitly. Without a pin, the mixed nightly/PyPI
# resolver can choose a newer stable CUDA distribution over an XPU prerelease.
VLLM_XPU_WHEEL="${VLLM_XPU_WHEEL:-https://wheels.vllm.ai/1970f3ed4be7fa8620e4ddc4a12c36a8384cfc27/vllm-0.28.1rc1.dev451%2Bg1970f3ed4.xpu-cp38-abi3-manylinux_2_34_x86_64.whl}"
"$AUDIO_ENV/uv-x86_64-unknown-linux-gnu/uv" pip install \
  --python "$AUDIO_ENV/venv/bin/python" "vllm[audio] @ $VLLM_XPU_WHEEL" \
  --extra-index-url https://wheels.vllm.ai/xpu \
  --extra-index-url https://download.pytorch.org/whl/xpu \
  --index-strategy unsafe-best-match
"$AUDIO_ENV/uv-x86_64-unknown-linux-gnu/uv" pip freeze --python "$AUDIO_ENV/venv/bin/python" > "$AUDIO_ENV/requirements.lock.txt"
"$AUDIO_ENV/venv/bin/python" "$ROOT/probe.py"
