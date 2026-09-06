# Quantized Gemma 4 native audio on Intel XPU

Target machine: Intel Core Ultra X7 358H, Arc B390 integrated GPU
(Panther Lake, PCI 8086:b080), 30 GiB system RAM. GPU and desktop share memory.

**Quantized native audio works on this laptop.** The completed test used
`Vishva007/gemma-4-E2B-it-W4A16-AutoRound` at revision
`b5c22b35dcc1eb28dc20e801300ec221cd754d71`, with vLLM's built-in oneDNN INT4 XPU
backend. It did not use dummy or full-BF16 language-model weights.

## Quantized results

The pinned [checkpoint](https://huggingface.co/Vishva007/gemma-4-E2B-it-W4A16-AutoRound)
retains native audio. Inspection of the actual safetensors found 275 packed
weight tensors. Its active shards total **7.45 GB**, including **5.50 GB of
unquantized embedding tables**, **0.61 GB of audio weights**, and vision weights.
This INT4 format compresses the language-model linear layers; it does not
compress the large per-layer embedding table as the installed GGUF does.
See [weight structure](results/quantized/weight-structure.json) and
[download manifest](results/quantized/download.json). The repository also holds
obsolete shards; the downloader follows the index and excludes those.

The model occupied **6.84 GiB** in vLLM and loaded in **7.70 seconds**. First
server readiness took **108.53 seconds**, including initial kernel compilation
and warmup. The service's cgroup memory was about **11.8 GiB** before inference,
with a **14 GiB** peak. Cgroup memory includes more than model tensors and can
include file cache; these measurements are not interchangeable with GPU model
allocation. The existing llama-server was temporarily stopped during each
experiment and automatically restored afterward.

For a 4.753-second speech fixture, native audio transcription plus command JSON
took **0.892 seconds**, with first text after **0.208 seconds**. First requests
for growing 2- and 4-second prefixes took **0.957** and **0.906 seconds**.
Identical-audio replays were faster and are labeled separately. These timings
start when the WAV request is sent, not when microphone recording begins.
Raw [initial audio results](results/quantized/initial-audio.json) and
[startup/memory results](results/quantized/initial-outcome.json) are preserved.

The first prompt produced valid JSON but sometimes wrongly selected `browser`
for a non-command test sentence. `valid_selection` in the results means the
response has a known ID and the expected structure, **not semantic correctness**.
The revised prompt explicitly distinguishes action requests from descriptions
and unrelated speech. The confirmation corpus contains eight known-text
synthetic recordings: four actions and four negative examples, including a
negated request and an unsupported desktop edit. This is a smoke test, not a
real-world transcription quality benchmark.

The [confirmation summary](results/quantized/confirmation-summary.json) records
**7/8 unique recordings correct** for both normalized transcription and routing
(14/16 including identical replays). Median latency on first requests for those
eight recordings was **0.719 s total**, **0.222 s to first text**. The failure was
“Do not open a browser”, transcribed as “do auto open a browser”, causing a wrong
browser selection. This demonstrates why a known-ID response alone is not
enough to permit automatic execution. No benchmark response executed an action.
The unrelated growing speech fixture now correctly selected null for every
prefix. This second startup took **88.47 s**, with cgroup memory **11.44 GiB**
before inference and **11.37 GiB** afterward; peak remained 14 GiB.
See [confirmation lifecycle](results/quantized/confirmation-outcome.json).

This is a viable native-audio backend for an interactive trial. Keep the
transcript and action visible, preserve explicit activation, and compare real
microphone speech against the existing Whisper path before adopting it. The
resident response latency is promising; initial startup and total service
memory are still materially larger than the installed GGUF runtime.

### Native backend fix

The default AutoRound ARK backend crashed with SIGILL while initializing the
real quantized model. The core's instruction pointer was in
`auto_round_kernel_xpu...so + 0x73241`, at `vcvtusi2ss`, an AVX-512 instruction;
this CPU advertises no AVX-512 support. There was no OOM kill at that failure.
The experiment now sets **`VLLM_XPU_INC_WNA16_BACKEND=w4a16`**, selecting vLLM's
oneDNN path. This is a supported backend selector, not a model-weight patch.
`probe-kernels.py` validates both Triton compilation and the exact INT4 matrix
kernel against known numeric results before loading the model.
The [kernel evidence](results/quantized/kernel-evidence.json) records both the
failure and successful replacement. No third-party runtime files were patched.

The smaller [TheStageAI checkpoint](https://huggingface.co/TheStageAI/gemma-4-E2B-it-qat)
uses custom MLX/edge-lm embedding codecs. Its model card describes dequantizing
to BF16 for vLLM evaluation, so it was not selected as a compressed XPU vLLM
checkpoint. Other compatible INT4 candidates were also about 7.4 GB; see
[candidate metadata](results/quantized/candidates.json).

The supplied [vLLM 0.6.3 OpenVINO guide](https://docs.vllm.ai/en/v0.6.3/getting_started/openvino-installation.html)
is for an older, LLM-only backend; it does not establish Gemma 4 audio support.
The [current OpenVINO plugin](https://github.com/vllm-project/vllm-openvino)
also documents LLM-only support. The old
[XPU guide](https://docs.vllm.ai/en/v0.6.3/getting_started/xpu-installation.html)
predates Gemma 4. This experiment therefore uses the
[current XPU wheel installation](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/).

Current [XPU model validation](https://docs.vllm.ai/en/latest/models/hardware_supported_models/xpu/)
includes larger Gemma 4 models on other Intel hardware. It does not validate
E2B native audio on this particular B390. The local inference tests above provide
that missing evidence for the pinned checkpoint and runtime.

## Earlier BF16 probe, 2026-09-06 (superseded)

The [hardware probe](results/hardware.json) passed: Python 3.12.14, Torch
2.13.0+xpu, B390 detected, a real GPU tensor calculation returned the expected
16, and vLLM selected XPU. The resolved
[Python packages](results/requirements.lock.txt) and
[bootstrap downloads](results/bootstrap.json) are recorded.

The [model compatibility probe](results/compatibility.json) did **not** reach
successful audio inference. With dummy weights, model allocation consumed
**9.45 GiB** and took **14.42 s**; startup then failed compiling Triton because
the Level Zero headers were missing. The bootstrap now supplies those headers
and `env.sh` supplies their SDK path. On retry, startup stopped at its free
memory guard: only **4.34 GiB** free out of 28.61 GiB reported for XPU, below
the requested **12.88 GiB** budget. Cgroup peaks were 7.6G and 3.3G respectively;
those are distinct from GPU allocation and should not be added mechanically.

The experiment was stopped without lowering the memory guard. No OOM or GPU
reset appeared in the kernel log during these tests; the stable voice services
remained active. The transient experiment unit is inactive. The real 10.2 GB
weight file was not downloaded, and there is **no valid native-audio latency or
accuracy result from that BF16 probe**. It did not settle whether quantized
audio would work. The subsequent INT4 test above validates the kernel and
native-audio path with actual model weights.

## Isolated setup

```sh
python experiments/gemma-audio/bootstrap.py
bash experiments/gemma-audio/install-vllm.sh
source experiments/gemma-audio/env.sh
"$AUDIO_ENV/venv/bin/python" experiments/gemma-audio/download-quantized.py
"$AUDIO_ENV/venv/bin/python" experiments/gemma-audio/probe-kernels.py
python experiments/gemma-audio/run-quantized-test.py /path/to/speech.wav \
  --output-dir /tmp/keystroke-quantized-audio
```

Default environment: `~/.local/share/keystroke/experiments/gemma-audio`.
Override with `KEYSTROKE_AUDIO_ENV`. No system packages, autostart services, or
desktop settings are changed. `bootstrap.py` uses package hashes from the
existing Arch repository database, extracts Intel runtime libraries locally,
and installs managed Python 3.12 through uv. It records download hashes in
`bootstrap.json`. Re-running keeps the existing Python environment.

The host initially had a Level Zero loader but no compute driver:
`zeInit(1)` returned `0x78000001`. The extracted runtime
`26.31.39395.13-1` and graphics compiler `1:2.40.13-1` changed that to `0x0`.
The override environment applies only to launched experiment processes.

`launch.sh` starts a transient user unit with a 14 GiB cgroup memory limit,
no swap, and a 20-minute runtime bound. `run-quantized-test.py` temporarily stops
the installed llama-server, starts this unit, tests speech, and restores the
previous service state in a `finally` block, including on interruption.
The five offline protocol tests include restoration after failed startup.
Stop a manually launched unit with
`systemctl --user stop keystroke-audio-experiment`. Inspect output with
`journalctl --user -u keystroke-audio-experiment -f`. Shared GPU allocations
may not all be reflected in cgroup memory accounting; inspect available RAM
and graphics stability during the first run. Use `--load-format dummy` for a
kernel/shape compatibility probe without downloading weights; outputs from
that probe are meaningless and must never be reported as model results.

The installer explicitly pins the Intel XPU wheel at commit
`1970f3ed4be7fa8620e4ddc4a12c36a8384cfc27` and freezes resolved packages in the
environment. An unpinned mixed-index install can select the stable CUDA build
instead. The XPU dependency download is several gigabytes.

`serve.sh` uses only loopback port 18782, separate from the working llama-server
on 18781. Its default is now the downloaded INT4 checkpoint, BF16 activations,
2,048-token context, one active sequence, 256 MiB KV cache, prefix caching,
eager execution, and audio input only. Explicit KV sizing overrides automatic
KV allocation from the GPU utilization fraction; the fraction still participates
in the initial free-memory check. Nothing enables this server at login.

## Measure growing audio

```sh
python experiments/gemma-audio/benchmark.py /path/to/speech.wav \
  --prefix-seconds 2 4 --repeats 2 --output /tmp/gemma-audio.json
```

The client sends whole-request WAV prefixes, always including the full clip,
and requests both a faithful transcript and a known command ID (or null).
Responses are recorded and validated; no returned command executes. Audio is
sent only to a loopback endpoint. Use synthetic or consented test audio.

Each new prefix is labeled separately from an identical-audio replay. Replayed
audio may benefit from caches and is not evidence of live microphone latency.
Multimodal processor caching is disabled for this baseline. Automatic prefix
caching [saves repeated prefill work](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/),
but does not eliminate decode time, initial model loading, or all audio-encoder
work. A resident server still needs lifecycle and resource management.

To reproduce the known-text checks with eSpeak NG installed (or `--espeak` and
`--data` pointing to an extracted local copy):

```sh
python experiments/gemma-audio/make-fixtures.py --output-dir /tmp/gemma-fixtures
python experiments/gemma-audio/run-quantized-test.py /path/to/speech.wav \
  --cases /tmp/gemma-fixtures/cases.json --output-dir /tmp/gemma-confirmation
```

The recorded run used eSpeak NG 1.52.0, en-us, 150 words/minute. Its packages were
extracted under the experiment's `tts/` directory; no system package was
installed. The growing request fixture came from voxtype's
`tests/fixtures/vad/speech_long.wav` (4.753 seconds). The benchmark disables
thinking, requests at most 256 output tokens, and uses a four-command catalog.
Do not extrapolate these measurements to a full command catalog or noisy speech.
