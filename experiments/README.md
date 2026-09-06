# Keystroke experiments

The retained [Codex benchmark](codex-cloud/README.md) uses the supported app-server and managed subscription login. `python3 experiments/test_protocols.py` checks its event ordering offline.

Local Gemma audio and text runtimes were removed in the Codex integration checkpoint. Quantized Gemma 4 E2B W4A16 did run on Intel XPU with vLLM, but measured model allocation was 6.84 GiB and total service memory about 12.4 GiB; startup was roughly 90 seconds. Those resource costs did not fit the laptop experience. Earlier code and detailed results remain in git history (`0325fb6`). The v1 voice tag is unchanged.

Keystroke now retains Vulkan Whisper for speech and uses Codex for reasoning. See [current verification](../docs/codex-integration-verification.md).
