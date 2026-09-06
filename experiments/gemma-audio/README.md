# Gemma 4 native audio on Intel XPU

Target machine: Intel Core Ultra X7 358H, Arc B390 integrated GPU
(Panther Lake, PCI 8086:b080), 30 GiB system RAM. GPU and desktop share memory.

The supplied [vLLM 0.6.3 OpenVINO guide](https://docs.vllm.ai/en/v0.6.3/getting_started/openvino-installation.html)
is for an older, LLM-only backend; it does not establish Gemma 4 audio support.
The [current OpenVINO plugin](https://github.com/vllm-project/vllm-openvino)
also documents LLM-only support. The old
[XPU guide](https://docs.vllm.ai/en/v0.6.3/getting_started/xpu-installation.html)
predates Gemma 4. This experiment therefore uses the
[current XPU wheel installation](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/).

Current [XPU model validation](https://docs.vllm.ai/en/latest/models/hardware_supported_models/xpu/)
includes larger Gemma 4 models on other Intel hardware. It does not validate
E2B native audio on this particular B390. That must pass a real inference test.

## Observed result, 2026-09-06

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
accuracy result**. The header fix still needs a successful full startup to
validate the remaining kernel path. Current evidence does not justify replacing
the installed quantized llama-server with this BF16 configuration. A smaller,
audio-capable quantized configuration is the next local experiment.

## Isolated setup

```sh
python experiments/gemma-audio/bootstrap.py
bash experiments/gemma-audio/install-vllm.sh
bash experiments/gemma-audio/launch.sh
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
no swap, and a 20-minute runtime bound. Stop it with
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
on 18781. Initial settings: BF16, 4,096-token context, one active sequence,
256 MiB KV cache, prefix caching, eager execution, audio only. BF16 E2B has
roughly five billion total parameters despite its effective-2B name; the
[official recipe](https://recipes.vllm.ai/Google/gemma-4-E2B-it) lists a typical
13 GB requirement. This is larger than a “few GB” target. A validated compressed
audio-capable variant would be a later memory experiment.

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
