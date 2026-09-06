# Resident Codex subscription experiment

Uses the installed `codex app-server --stdio` (tested with Codex 0.153.2) and
its existing managed ChatGPT sign-in. This is the supported client integration
path; it is not a public API key obtained from a subscription. The app-server
handles token refresh. If no account is signed in, use `codex login` normally.
No code here opens credential files or copies bearer tokens.

Official references: [app-server](https://developers.openai.com/codex/app-server),
[authentication](https://developers.openai.com/codex/auth),
[fast mode](https://developers.openai.com/codex/speed), and
[GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna).
Luna has no native audio input, so this path retains a transcription model.
Fast mode consumes subscription allowance at its configured higher rate; it
is not a latency guarantee.

## Reproduce

```sh
python experiments/codex-cloud/benchmark.py --output /tmp/luna.json
python experiments/codex-cloud/agent_probe.py
python experiments/codex-cloud/local_baseline.py --output /tmp/local-classifier.json
```

The first script sends six synthetic text prompts, three per service tier.
It keeps one app-server alive, starts ephemeral read-only threads, disables
shell and web tools, uses low reasoning and a constrained JSON output schema,
and records stream timestamps, returned tier, token usage, and routing accuracy.
Server-initiated tool/approval requests are declined. The second script permits
one read-only agent task: read `/etc/os-release` and report the OS name. Its
output defaults to `/tmp/keystroke-luna-agent-probe.json`.

## Initial results, 2026-09-06

The account advertised the exact requested model `gpt-5.6-luna`. Requests for
`fast` returned the `priority` tier. All six classifier outputs were correct;
no tools ran. Raw results: [initial.json](results/initial.json).

| Requested tier | Median first text | Median completed turn | Completed turn range |
| --- | ---: | ---: | ---: |
| Fast | 2.90 s | 3.74 s | 2.98–5.20 s |
| Default | 2.57 s | 2.95 s | 2.75–3.18 s |

App-server initialization took 0.48 s. Thread creation took 0.04–0.43 s and is
recorded separately. Each classification carried roughly 10.5–10.7k input
tokens from the Codex environment, including context beyond the short routing
prompt. Cache hits varied from zero to 9,984 tokens. This is a measurement of
the actual embedded Codex path, not a minimal public API completion.

The [read-only agent probe](results/agent-read.json) started its terminal
action after **5.73 s**, produced its first answer text after **9.16 s**, and
finished after **9.37 s**. Its only command was `cat /etc/os-release`; it
correctly identified Omarchy. No desktop configuration was changed.

These small samples demonstrate capability and expose multi-second latency;
they do not establish a reliable speed ranking. Initial tier order was fast
then default; cache state, routing, network, and output lengths were not
controlled. The benchmark now preserves notifications that arrive before RPC
responses so early stream events cannot be dropped. A second run reverses tier
order: [confirmation.json](results/confirmation.json). All six routes were again
correct, with no tools observed. Median completed turns were **2.75 s fast**
(first text 2.48 s) and **2.94 s default** (first text 2.63 s). This second run
shows a small fast-tier advantage; the two runs together do not demonstrate a
consistent large improvement.

The installed Q4_0 Gemma / llama-server classified the same three synthetic
phrases correctly: [local-baseline.json](results/local-baseline.json).
First text took 1.15 s on the first request and 0.21 s on subsequent requests;
completed responses took 1.78 s, 0.85 s, and 0.83 s. The model was already
resident. This tiny prompt used only 89–93 input tokens, versus Codex's larger
agent context, so it compares practical request paths rather than isolated
model performance. It is not a benchmark of the full installed command catalog.

## Integration implication

Keep this resident as the capable agent option, while local extension actions
stay immediate. Stream “working” and actual command events instead of waiting
for a final answer. Reuse an agent thread for follow-up corrections, but do not
accumulate unrelated commands indefinitely. A production bridge still needs
action approval UI, cancellation, clear completion/failure states, capability
discovery, and tests of the real desktop focus lifecycle.
