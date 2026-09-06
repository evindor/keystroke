# Speech comparison, 2026-09-06

Compared the installed Vulkan voxtype build with Whisper small and the official
[Whisper large-v3-turbo Q5_0](https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-large-v3-turbo-q5_0.bin)
(574 MB). Results are in `results.json`. Both used language `en`, six synthetic
espeak-ng 1.52.0 utterances at 150 words/minute, one file per fresh process.

Both transcribed all six correctly, ignoring punctuation. Small took 539–607 ms;
turbo took 960–1642 ms including model load and file decoding. These are not
resident-daemon stop-to-final or human-speech accuracy measurements. The candidate
did not justify changing the current small default. Whole-request revision stays
enabled. Real user recordings and longer utterances are needed to establish an
accuracy benefit; synthetic short commands are an easy test.

To reproduce against a WAV file, use an isolated TOML file:

```toml
engine = "whisper"
[whisper]
model = "/absolute/path/to/ggml-large-v3-turbo-q5_0.bin"
language = "en"
```

Run `~/.local/share/keystroke/voxtype/voxtype -c /tmp/speech-test.toml transcribe /path/to/speech.wav`.
Repeat with `model = "small"`. Do not use `--model /absolute/path`: this build's
CLI silently falls back to small for unrecognized model names (with a warning),
whereas its config accepts absolute model paths. The invalid preliminary CLI
comparison was excluded from these results. This experiment uses no microphone.
