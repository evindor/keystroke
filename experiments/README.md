# Voice v2 experiments

The installed voice checkpoint is `main` / `v1-voice` at `800adb6`.
This branch (`codex/gemma-audio-vllm`) keeps experimental runtimes separate
from the installed palette, voxtype service, and llama-server on port 18781.

## Product direction

Dictate into the existing palette. Watch the complete request improve while
speaking. Ordinary actions remain immediate; clipboard, ChatGPT, and Codex
remain normal options for the same request. For an open-ended request such as
“make my window corners more rounded”, offer an agent that can inspect the
machine, load the applicable Omarchy skill, make the change, and verify it.

The next integration should use two execution paths:

1. Local transcription, full-request revision, and deterministic extension
   actions for responsiveness. Suggest while recording; only execute after
   the user selects an action. Never execute speculative partial speech.
2. A resident Codex app-server for open-ended work. Show progress immediately,
   stream actual action events, support interruption, and preserve the agent
   session for corrections. Permissions and approval handling belong in the
   execution bridge; model size alone does not establish safe execution.

Use generation IDs and cancellation for superseded transcripts and results.
Pre-create the agent session and catalog prefix where possible, but measure
speech-end-to-useful-action latency, not just model token speed. Resolve skills
from the installed environment instead of hard-coding desktop edits. Start
with one explicit “Run with agent” option before considering automatic routing.

## What was tested

- [Codex subscription / GPT-5.6 Luna](codex-cloud/README.md): working managed
  sign-in, streaming classification benchmark, and one real read-only terminal
  action. No authentication tokens are extracted or stored by this code.
- [Gemma 4 audio / Intel XPU](gemma-audio/README.md): isolated driver, Python,
  vLLM runtime, bounded server configuration, and growing-audio benchmark.

Run the offline benchmark protocol checks with:

```sh
python -m unittest discover -s experiments -p 'test_*.py' -v
```

These are exploratory clients, not a shipped agent executor. Their example
catalog is deliberately small and their timings do not measure microphone,
ASR, UI, or end-to-end voice latency.
