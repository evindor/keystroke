# Keystroke with Codex — design proposal

2026-09-06. Approved design. See [implementation verification](codex-integration-verification.md) for delivered behavior, measurements and remaining limits.

Keystroke should make asking a question feel as direct as opening an application. Type or speak into the same palette, get a useful answer there, and carry the conversation into Codex when the work needs more space. Local search, calculations, and clipboard actions stay immediate. Speech recognition stays local on Vulkan; reasoning moves to Codex.

**What the current project gives us**

Reviewed the README, architecture and provider contract, both historical Fable reviews, current palette/voice/activation code, AI launchers, setup scripts, and recorded Codex experiments. The original constraints still fit: one native Omarchy menu replacement, capabilities implemented as providers, cheap operation while hidden, and explicit execution. Keep the `omarchy.clonedFrom` contract and shared shell services.

The useful existing pieces are `VoiceSession`, whole-request transcript revision, the narrow waveform, raw dictation preservation, `ClipboardTransfer`, provider ranking and settings. `AiWeb` currently offers external launch effects only. `PreviewPane` displays a result preview; it is not a conversation view. `AiTargets.clip()` currently truncates prompts to 2,000 characters. That limit must not reach the new Codex path.

**The experience**

| Intention | Palette choice | What happens |
| --- | --- | --- |
| Open an app, calculate, search files | Existing local result | Existing immediate action |
| Ask a question | **Ask Codex here** | Answer streams inside Keystroke |
| Begin substantial work | **Start a task in Codex** | Open the configured desktop app or terminal with the request and selected working context |
| Expand an inline conversation | **Continue in Codex** | Continue its saved history in the configured destination, subject to the handoff compatibility checks below |
| Dictate prose | **Copy to Clipboard** | Enter copies and closes; Ctrl+Enter copies, closes, then pastes after 100 ms |

These are normal results for the current text, not separate launchers the user must visit first. Codex gets its own provider; Claude, ChatGPT web and Google remain external continuations. Remove the duplicate external “Ask Codex” label. Assistant preference controls fallback ordering. Existing concrete local results retain their ranking. An optional `? ` prefix explicitly selects inline Ask and avoids navigating past unrelated fuzzy matches; plain text and voice need no prefix.

When Ask is selected, Enter submits here; Ctrl+Enter chooses the external task path. The footer states the alternate action. Ctrl+Enter on Copy to Clipboard retains paste. Do not make Ctrl+Enter a global Codex shortcut.

After submission the results area becomes a compact conversation panel:

```text
┌─────────────────────────────────────────────────────────┐
│ Codex · Quick question                  Continue ↗      │
│ Why does Bluetooth interfere with Wi-Fi?                │
│                                                         │
│ Both can use the 2.4 GHz band…                           │
│ [streaming answer, readable paragraphs and source links] │
│                                                         │
│ Follow up…                                      ▂▅▃     │
│ Enter Send       Stop       Copy answer       Esc Close │
└─────────────────────────────────────────────────────────┘
```

Keep the latest answer prominent, with earlier turns available by scrolling. Use a dedicated text renderer with selectable text, code blocks, copy controls and source links. Do not squeeze an answer into result subtitles or render arbitrary model HTML. Keep the question visible, avoid moving text under the pointer, and stop automatic scrolling if the user scrolls upward. Expand the composer up to a few lines for longer dictation; cap the waveform's width independently of text length.

Progress is one quiet status line derived from actual events: “Connecting”, “Answering”, “Searching the web”, or a concrete tool activity. No simulated percentage, raw protocol, or raw reasoning display. First answer text replaces the waiting state immediately. The input remains usable throughout.

**Voice, follow-ups and dismissal**

Use the same submission path for keyboard and voice. Preserve the full original transcript for Codex and clipboard; command normalization belongs only to local search. While speaking, revise the whole request using the existing voxtype patch. Once the user starts manual correction, stale transcription must not overwrite it.

At the root, hold/release or tap-to-talk retains today's behavior: finish recording, settle the final transcript, then Enter activates the visible choice. Enter used to stop a recording never also sends it. No cloud requests for partial transcripts and no cloud classifier in front of local results. Warm the transport while the user types or speaks, without making a model request.

Inside a conversation, voice fills the follow-up composer. Enter sends; Shift+Enter adds a newline. While an answer is running, label submission “Update request” and deliberately steer the active turn; do not silently start a second turn. Keep the draft if steering fails. A future opt-in “send on release” can apply to an explicitly selected Ask conversation, after transcription quality is measured; it is not the initial default.

Stop cancels generation and leaves the partial answer visible. Escape or outside-click closes immediately and requests interruption of an inline turn; cleanup continues offscreen. Reopening the main hotkey opens the normal launcher with a “Resume last question” result, so an old chat cannot take over app launching. Completed and interrupted questions remain available under Codex → Recent questions. Never silently retry a submitted request after a disconnect. A retry or continuation is an explicit user action.

**Conversation continuity is the first technical milestone**

The installed CLI is 0.153.2. Its generated protocol schema contains durable thread creation, project identity, resume, turn streaming and interruption. The desktop package is 26.901.20858. Read-only inspection of its installed route parser confirms a local-conversation route under `codex://threads/<id>` and a new-conversation route accepting prompt/path/project fields. This is implementation evidence, not a documented cross-version compatibility promise. No desktop handoff was run during this design review.

Create durable inline conversations using the same managed Codex home/account as the CLI. Keep Keystroke's own small index of its thread IDs, titles, selected workspace, last-seen state and drafts; Codex owns the conversation record. Separate unrelated questions into separate conversations, and resume only for deliberate follow-ups. Do not use ephemeral threads for the default Ask path, copy credential files, manufacture rollout JSON, or edit Codex's database. Do not promise that private Keystroke history can remain absent from Codex history while also being immediately resumable there; validate the desktop's source/project filters first.

The CLI explicitly supports resuming a session by ID. Confirm that the IDs returned for our root conversations resume correctly, preserve cwd and contain the full exchange. [CLI reference](https://learn.chatgpt.com/docs/cli/reference#codex-resume)

Before building the full UI, run a tiny disposable conversation through these checks:

1. Create it through app-server, complete a question and follow-up, restart the client and resume it.
2. Open that exact ID in desktop and CLI. Verify content, history listing, project assignment and a subsequent reply, with the desktop both running and newly opened.
3. Establish ownership during handoff. For the first version, hand off an idle conversation. If generation is active, “Stop and continue in Codex” interrupts and waits for acknowledgement before opening the destination. Do not let two independent clients submit turns on the same conversation simultaneously.
4. Verify that the quick-question permission profile does not prevent an intentional switch to task work in the destination. Reconfiguration is explicit, never an automatic grant of wider access.
5. Test full-length and multiline prompts, quotes, Unicode and long dictation. New desktop launch currently prefills a composer; it does not prove automatic submission. If no supported submit/ownership path is available, label this action “Open task in Codex” and let the user send there. Do not emulate a blind Enter key.

A failed desktop compatibility check should produce a clearly labeled CLI-resume fallback, not a new chat masquerading as the original. Missing destinations leave the inline conversation intact. ChatGPT web is not a same-conversation fallback. Live takeover of running work is a later feature unless these checks establish a reliable shared-server route.

**Implementation shape**

```text
existing Omarchy shell
  Keystroke palette / generic provider view host
    ├─ local providers                         immediate
    ├─ voxtype / Whisper on Vulkan             local speech
    └─ Codex provider
         ├─ conversation view and session state
         ├─ app-server protocol adapter
         │    └─ one managed codex app-server process
         └─ desktop / CLI handoff adapter
```

Propose `providers/Codex.qml`, `codex/CodexSession.qml`, `codex/AppServer.qml`, pure JS protocol/state helpers, and a dedicated conversation view. Prefer QML's asynchronous Process/stdin/stdout support for the initial stdio adapter. Add a helper only if measured transport or lifecycle requirements justify one. Ordinary queries must not pass through the agent process.

Add an optional generic provider-view contract and a view-opening effect. The host owns placement, keyboard focus, navigation and dismissal; the provider owns conversation behavior. Existing API-1 row providers continue to work unchanged. Document ownership, close/disable lifecycle and unsupported-view behavior rather than adding Codex-specific conditionals throughout the root window.

The official app-server interface supplies authentication, history, streaming and approvals over structured messages. Prefer stdio, capture schemas from the tested CLI, and isolate version-dependent behavior in the adapter. The command remains experimental; do not claim general production compatibility. [App-server documentation](https://learn.chatgpt.com/docs/app-server)

Initialize one process asynchronously when the enabled Codex capability is first warmed; retain it across palette opens. Do not spawn one per question, continuously poll while hidden, or send dummy inference for warmth. Start with a proposed ten-minute idle shutdown when no turn, approval or handoff is active; measure the trade-off. No additional inference server or weights. Never attach to or kill the desktop app's private server. Disabling the provider shuts down only the process Keystroke owns.

Track request, connection, thread, turn and item identity separately. Handle notifications arriving before RPC responses, coalesce text updates at frame cadence, bound logs/output, and reconcile final items without duplicating streamed text. Preserve drafts on startup failure, loss of network, quota exhaustion and process exit. After a crash, resume saved state and show uncertainty; never replay a possibly executed turn automatically. A shell restart should leave a resumable conversation and terminate the owned child cleanly.

Use existing managed ChatGPT sign-in, which provides subscription access. Codex handles its credentials; Keystroke displays account readiness and routes login through the normal flow. [Authentication](https://learn.chatgpt.com/docs/auth)

**Quick questions and agent actions**

Quick Ask should answer and, when needed, search the web internally without opening another application. Its capability profile excludes local shell execution, file mutation, computer control and connected-app side effects. Establish that restriction through actual supported tool/configuration controls, not a prompt alone. Audit inherited plugins, MCP, hooks, skills and environment tools; `approvalPolicy: never` is not a no-tools policy, and a read-only filesystem does not prevent remote side effects. This is a release gate for the quick-question experience.

General questions use a neutral working context. Let the user deliberately attach a file or choose a project later; do not infer a workspace from a window title or automatically send clipboard/screen contents. A visible context chip makes the selected scope legible. A request requiring machine changes can offer “Continue as a task” with the original conversation.

For the later in-palette agent experience, reuse Codex's enforced permission boundaries and approval mechanism. Routine authorized work within a scope should proceed smoothly; commands, file diffs and requested expansions get a compact review surface when required. Model capability does not replace the permission boundary. [Sandbox and approvals](https://learn.chatgpt.com/docs/sandboxing)

“Make my window corners rounder” is the first proposed action acceptance case: select the desktop-settings context, load the Omarchy skill, inspect the actual configuration, make the scoped edit, verify it and report the result. Use Codex's skill discovery instead of copying all skills into a giant system prompt. Skills load their full instructions when selected. [Skills](https://learn.chatgpt.com/docs/build-skills)

Do not turn arbitrary answer text into a shell effect. If Keystroke later exposes provider actions to the agent, use explicit typed tools and the same host permission/confirmation path. Prefer portable skills/MCP for capabilities needed after handoff; client-only tools can make a resumed conversation dependent on Keystroke being present.

**Speed and resource budget**

Start evaluation with the requested GPT-5.6 Luna, low effort and Fast mode when available; discover availability and show the effective selection. Keep a user-visible Standard/Fast setting. Fast consumes more subscription allowance; it does not eliminate transport or tool-start latency. [Fast mode](https://learn.chatgpt.com/docs/agent-configuration/speed)

The committed experiment measured fast completed-turn medians of 2.75–3.74 seconds and about 0.48 seconds to initialize app-server. These are earlier small classifier samples, not new quick-answer benchmarks. They also carried about 10.5k input tokens from the agent environment. Test a deliberately lean question context, short useful answers, and transport reuse before claiming improvement. See `experiments/codex-cloud/README.md` and its recorded results.

Proposed acceptance targets: palette feedback below 100 ms; local search unaffected; warm first useful text below two seconds median and four seconds p95 on the reference network; transcription settles within one second p95 for short utterances. These are targets to measure, not promises. Record cold/warm startup, final-speech-to-submit, first text, first useful sentence, completion, cancellation and handoff separately over at least 30 varied prompts. Compare tiers in alternating order, short and long dictation, online/offline recovery, and user speech as well as fixtures.

Measure incremental PSS/private memory, child processes, GPU allocation, wakeups and power with the desktop already open and closed. Aim for less than 300 MiB incremental idle Codex integration memory and a roughly 1–1.5 GiB total speech-plus-bridge working budget as an initial hypothesis. The current desktop app's own Codex process is about 295 MiB RSS, so “local process” does not mean free. Speech-model choice must fit measured interactive latency and power, not a disk-size ratio.

The configured speech model is already Whisper `small`; `base.en` is also on disk. “Upgrade the base speech model” is interpreted as improving the underlying transcription model, not switching down to the model literally named `base`. Keep `small` as the baseline, then compare a quantized larger Whisper candidate supported by the installed Vulkan build. Do not download it or change the default until the benchmark is selected for implementation.

**Retiring local LLMs**

During this review vLLM remained enabled and active, using about 7.9 GiB in its service cgroup; llama-server was already disabled. No services, runtime config or model files were changed during planning.

Migration begins by selecting the retained voxtype path, disabling local model assistance, checking live dictation and clipboard, then stopping and disabling both Keystroke LLM services. The existing `voice-backend voxtype` helper currently re-enables llama-server, so do not use it unchanged as the removal procedure.

Remove native Gemma audio capture/inference, `AudioSession`, `AudioIntent`, `Assist`, LLM-specific suggestion state, backend switches, service units, setup/download paths and model-only tests. Keep normalization and speech lifecycle tests. Split speech setup from the obsolete LLM installer. Remove runnable Gemma/vLLM experiments and the local baseline script; retain a short historical findings note and useful Codex benchmark evidence. Update README, architecture, provider/catalog documentation, example config, status commands and installation cleanup so upgrading does not leave stale deployed files. Keep the existing v1 tag/history; no history rewriting is needed.

Read-only disk inventory, rounded allocated sizes:

| Path under `~/.local/share/keystroke/` | Size | Treatment |
| --- | ---: | --- |
| `models/` | 3.2 GiB | Remove Gemma Q4_0 and the Q8_0 multimodal projector |
| `experiments/gemma-audio/` | 17 GiB | Remove its quantized model, 8.9 GiB Python environment, isolated drivers and private download cache |
| `llama/`, `vllm/` | About 93 MiB | Remove launchers/runtime |
| `voxtype/`, `toolchain/` | About 285 MiB | Retain speech binaries and build dependencies |

This identifies about 20 GiB to reclaim, subject to filesystem sharing and cache accounting. Inspect `~/.cache/vllm`, experiment-specific package/download caches, partial downloads and coredumps for attributable remnants. The private Hugging Face directory currently contains only about 32 MiB; no full unquantized 10.2 GB model was established in this inventory. Do not claim it exists or delete unrelated shared caches. There is no Ollama implementation identified in this checkout; remove any Keystroke-owned remnants discovered, not unrelated installations. Preserve `~/.local/share/voxtype/models`, user configuration, system Intel/Vulkan drivers and the user's `.claude/` worktrees. Verify freed disk space and absence of model processes/listeners afterward.

**Delivery order after approval**

1. Retire local LLM services, code and attributable disk artifacts; restore and verify Vulkan dictation without model assistance.
2. Prove durable conversation, tool restrictions, full-prompt transport and desktop/CLI handoff with the installed versions. Resolve any destination limitation before committing the UX to it.
3. Build the Codex provider and inline conversation view: streaming, follow-ups, stop/close, recent questions, errors, settings and external continuation.
4. Tune speech quality and measured latency; test in the real shared shell with both typing and dictation. Include Enter-repeat, stale transcript, selected-row stability, clipboard paste/focus, offline/quota errors, cancellation and duplicate-submission cases.
5. Add scoped agent execution inside the palette, with Omarchy skill loading, activity and approval views. Start with the window-rounding case, then expand to project/file tasks and selected context.

The review checkpoint is the interaction model and migration order above. Implementation, downloads, deletions, installation and any new commit wait for the user's response.
