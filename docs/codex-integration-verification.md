# Codex integration checkpoint — 2026-09-06

Implemented on the Intel Core Ultra X7 358H / Arc B390 laptop, Omarchy 4.0.2,
Codex CLI 0.153.2 and desktop 26.901.20858. The v1 voice tag is unchanged.

## Delivered

- Dedicated Codex provider with inline quick questions, streamed selectable
  Markdown, web-search activity and links, voice/typed follow-ups, steering,
  interruption, latest-answer copy, saved drafts and recent questions.
- Normal root results: Ask Codex here and Open task in Codex. `? ` prioritizes
  inline Ask; Ctrl+Enter on that row opens an external task. Clipboard retains
  its existing copy/paste alternate action and original prose.
- Generic optional provider views; local queries remain synchronous. A single
  owned app-server warms without model inference and exits after ten idle minutes.
- Model, tier, desktop/CLI destination and working-folder settings. Default:
  GPT-5.6 Luna / low / Fast, managed Codex login, exact CLI version gate.
- Quick mode disables local execution/environments, inherited MCP, connected apps,
  plugins and hooks through actual configuration. Web search remains available.
- Explicit scoped tasks in the Codex provider: desktop settings (`~/.config`) or
  a configured working folder. Command/file/permission approvals and user questions
  render in a scrollable panel; unsupported requests direct the user to Codex.
- Same-conversation continuation waits for interruption and **exits the owned
  server**. Unsubscribe alone retains a writer lease and is insufficient.
- No credential extraction, Codex database edits, blind Enter dispatch, or automatic
  replay after disconnection. Desktop new-task launch prefills for manual submission.

## Checks performed

Production QML session/view tests cover early streaming events, final-text
reconciliation, full dictation preservation, Enter-to-stop without sending, manual
correction cancellation, keyboard decline, quick-mode rejection of approval
requests, normal interruption, new questions, process failure/draft preservation,
and writer release before handoff. Existing palette/voice/clipboard/time-zone
checks and 92 QML unit/lifecycle assertions pass; qmllint completes with metadata/unqualified-access
warnings, including existing Omarchy/Quickshell type-resolution warnings.

The installed shared shell completed a real question with no error: first text
2486 ms, completion 2721 ms. The conversation view was rendered offscreen and visually inspected; the final
installed empty panel was also captured and checked in the shared shell. Existing
palette dictation tests cover host routing with synthetic events.

A durable app-server conversation retained a remembered label across a follow-up
and a server restart. Desktop's normal history reader recognized all four turns.
A separate saved question resumed through `codex exec resume`; it remembered
“copper lantern” and explicitly ran a harmless command printing `CLI_TOOL_OK`.
Desktop then read both turns of that same conversation. Quick-question instructions
did not prevent intentional native task execution after handoff. The destination
can select its own configured model: the CLI test resumed with its default Astra.

The installed desktop route `codex://threads/<id>` opened successfully. Trying a
second writer while desktop already owned the question correctly failed; this
motivated exiting the Keystroke server before launch. Desktop cold-start behavior
and future desktop versions remain compatibility checks, not guaranteed contracts.

A live quick-mode attempt to create a test file reported no local tools; the file
was absent and no command/file/MCP events occurred. A separate quick question
emitted a real `webSearch` event and returned the official Python venv link.
A real explicit agent task read the installed Omarchy skill, changed only a
throwaway `appearance.txt` from `rounding = 4` to `rounding = 12`, and verified it.
Actual window appearance was not changed. Approval rendering/decisions were tested
with protocol fixtures; an actual out-of-scope approval interaction needs a user test.

## Latency and memory

[Reproducible benchmark and raw data](../experiments/codex-cloud/results/questions.json):
15 distinct short prompts, both tiers in alternating order, 30 completed turns,
no tool activity. Nearest-rank p95; only 15 observations per tier.

| Measurement | Fast | Standard |
| --- | ---: | ---: |
| Median first text | 2473 ms | 2579 ms |
| p95 first text | 6979 ms | 3709 ms |
| Median first sentence | 2828 ms | 2925 ms |
| Median completion | 3009 ms | 3317 ms |
| p95 completion | 7921 ms | 4289 ms |

App-server initialization was 186 ms. At the end, its process used 131 MiB PSS,
183 MiB RSS and about 79 MiB private clean+dirty memory. This is one process
snapshot with desktop already running, not total system/GPU memory or a power
measurement. The first prompt used 5381 input tokens, below the earlier classifier
experiment's roughly 10.5k. Disabling host skill discovery in a separate probe did
not materially reduce context, so that extra override was not adopted.

The proposed two-second median/four-second p95 first-text targets were **not met**.
Fast helped median completion slightly but had a slower outlier; this sample does
not establish its tail-latency advantage. Standard remains selectable. Network
outages/quota failures are handled as explicit errors without replay; the automated
regression injects process failure rather than disrupting this machine's network.

## Speech and cleanup

Vulkan voxtype remains active with Whisper small and whole-request revision.
A [quantized turbo comparison](../experiments/speech/README.md) found no accuracy
benefit on six easy synthetic phrases and higher load-inclusive latency, so small
remains the default. Human-speech accuracy, longer dictation, resident stop latency
and power need further measurement; no unsupported improvement claim is made.

Disabled and removed Keystroke's vLLM and llama service units, native audio/model
code, model-only tests, backend selectors/downloaders and runnable Gemma experiments.
Installation replaces the deployed tree, removing obsolete QML and helper files.
Short historical findings remain in git/documentation; no Ollama implementation
was present in this checkout.

Removed the Keystroke Gemma weights/projector, quantized vLLM model, isolated Python
and Intel runtime, launchers/private cache, and 159 attributable package-cache
entries/partial downloads. Dedicated-data cleanup measured 9.3 GiB freed; cache
cleanup measured about 5.0 GiB more. Allocated directory sizes were larger because
of hardlinks/shared storage. Voxtype's models/binaries, build toolchain, system
Vulkan drivers and user worktrees were preserved. No full unquantized 10.2 GB model
was established in the disk inventory.
