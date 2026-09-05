# Flint: architecture deliberations and review handoff

Prepared 2026-09-06. This is a working prototype and a decision brief, not an approved architecture. Read the review prompt at the end together with this checkout. The repository is local; no remote or publication is part of this handoff.

## What we want to build

Flint should be a beautifully designed, Raycast-inspired replacement for the entire Omarchy menu. It should feel immediate when opened or searched, stay inexpensive while hidden, and fit into Omarchy's existing desktop and community ecosystem.

The central product constraint is **everything is an extension**: the shell owns presentation, navigation, result composition and generic execution plumbing; capabilities live in modules that contributors can add without editing the shell. This does not mean every extension needs its own process, package, window or renderer.

Initial capabilities are the complete Omarchy menu, applications, calculator, clipboard history, unit/time-zone conversion, emoji, screen color picking, and AI/web continuation. As useful local matches run out, a query should still offer Google, ChatGPT and Claude. AI settings should expose a preferred provider and desktop/CLI choices; the prototype also offers browser mode. Configuration must be both hand-editable and available through menus, with extensions declaring their own settings.

The user explicitly wants better fuzzy matching **after the architecture is settled**. Frecency alone is insufficient, but choosing or implementing a replacement matcher is deferred. The current matcher is a provisional implementation.

## Where the discussion stands

The first build chose native QML for the interface and a resident Python process for extensions. The user then challenged the additional runtime and asked whether we should simply clone Omarchy's menu plugin, evolve it, and distribute community capabilities through the existing Omarchy plugin ecosystem.

That is now the leading proposal: **one Omarchy menu plugin, developed from the stock menu contract, with QML/JavaScript for ordinary capability logic**. Maintained extensions would ship in this repository and accept PRs; independently maintained capabilities would be ordinary Omarchy plugins that integrate with Flint. The interface and behavioral work in this prototype can inform that implementation.

This is not yet an agreed migration plan. In particular, discovery between plugins, the published replacement mechanism, settings ownership, and the need for any worker runtime remain open. Fable should challenge this proposal against the actual code and supported Omarchy APIs.

## What exists today

The current menu UI was written afresh. It was **not produced by cloning and retaining the stock `Menu.qml` implementation**. Its root manifest declares `menu` and `bar-widget`, `keepLoaded: true`, and `omarchy.clonedFrom: omarchy.menu`. Manifest validation passes, but native installation and full replacement behavior remain untested.

For review, `bin/flint` starts a separate Quickshell configuration from `shell.qml`. Its QML interface communicates over JSON lines with one resident Python host. Nine bundled Python extensions run inside that host. Optional external providers use a separate experimental command protocol and are disabled by default.

```text
Current review build
  bin/flint → separate Quickshell instance → Flint.qml + ui/
                                             ↕ JSON lines
                                          flint/host.py
                                             ├─ bundled Python extensions
                                             └─ optional external query processes

Proposed production direction — contract still to be decided
  existing Omarchy shell
    ├─ Flint menu plugin → shared views, navigation, provider registry
    │                       └─ bundled QML/JS capabilities
    ├─ existing application/clipboard/theme services
    └─ community Omarchy plugins → agreed Flint capability interface
```

The Dell Copilot key has been rebound locally to this checkout's `bin/flint` for real use. That is a development shortcut, not a native plugin installation. The regular Omarchy menu remains available. The binding and personal configuration live outside this repository.

### Code map

| Files | Responsibility / review focus |
| --- | --- |
| [Flint.qml](../Flint.qml), [ui/](../ui/) | Window, focus, navigation, stable result model, previews, input handling, backend transport and dmenu replies. Consider separating these responsibilities. |
| [manifest.json](../manifest.json), [BarWidget.qml](../BarWidget.qml) | Native plugin entry points and replacement metadata; bar widget adapted from Omarchy. |
| [shell.qml](../shell.qml), [bin/flint](../bin/flint) | Separate development harness and IPC launcher; not the intended production runtime. |
| [flint/host.py](../flint/host.py) | Discovery, concurrent queries, result ordering, action tokens, activation and generic effects. |
| [flint/api.py](../flint/api.py) | Result helpers, basic matcher, JSONC parser, bounded subprocess execution. |
| [flint/config.py](../flint/config.py), [flint/usage.py](../flint/usage.py) | Typed configuration and persistent frecency. |
| [extensions/](../extensions/) | Applications, Omarchy, calculator, converter, clipboard, emoji, colors, AI and settings; each has a manifest and implementation. |
| [examples/hello/](../examples/hello/), [extensions.md](extensions.md) | Experimental external-provider protocol; not a stable public SDK. |
| [tests/](../tests/), [verification.md](verification.md) | Backend tests, live UI smoke checks and measurement limitations. |

## Fit with Omarchy: plugin, clone, or separate application?

The inspected machine has Omarchy **4.0.2-1**, Quickshell **0.3.1-1**, and Qt **6.11.2**. Omarchy already uses Quickshell/QML for its menu. GTK4 is available, but a separate GTK application would require another integration surface and would not directly reuse QML components. Nothing measured so far proves that GTK or a new compiled application would perform better for this workload.

The [plugin development guide](https://plugins.omarchy.org/develop.html) recommends starting with a built-in of the same kind, editing a user-owned clone, and sharing the existing shell process. It prohibits a second Quickshell process for a plugin. It also requires valid entry points, a namespaced ID, and a plugin tree without symlinks. This makes the current separate harness useful for review, but unsuitable as the production integration pattern.

Inspection of the installed source found:

- `/usr/share/omarchy/bin/omarchy-menu` forwards toggle/summon/hide/call to `omarchy.menu`, including menu routes.
- `/usr/share/omarchy/shell/plugins/menu/Menu.qml` and `MenuModel.js` implement more than presentation: navigation, definitions, providers and dmenu compatibility.
- `/usr/share/omarchy/shell/services/PluginRegistry.qml`, particularly `resolveEnabledId()`, redirects the built-in ID to an enabled clone whose `omarchy.clonedFrom` matches. Preserving that route matters for existing callers.
- `shell.appLibrary` supplies shared native application metadata. Existing Omarchy clipboard history and emoji data avoid duplicate capture and data sources.
- Stock definitions come from `/usr/share/omarchy/default/omarchy/omarchy-menu.jsonc`, with user overrides in `~/.config/omarchy/extensions/omarchy-menu.jsonc`.

The guide's generic finished example removes `clonedFrom` before publication. A deliberate menu replacement needs a specific answer here: **what is the supported published replacement mechanism that preserves calls to `omarchy.menu` and restores the original on disable/removal?** Do not infer that a generic clock example settles this, or blindly remove the field. `community.flint` is also a provisional identity; a permanent publishing namespace is undecided.

The preferred approach is to retain or adapt the stock menu's compatibility machinery while replacing its presentation and adding extensibility. Whether that means starting a clean clone and moving our views into it, or bringing the necessary stock pieces into this checkout, needs a code-level comparison. Maintaining a fork of the whole distribution is outside the intended scope. Copied upstream code must retain attribution and have an update strategy; the repository already retains Omarchy's MIT notice.

## The Python question and stack choices

QML JavaScript runs inside Qt's QML engine. **It is not a separate Node/JavaScript process, and QML does not require Python.** The extra process here was an implementation choice.

Python made it quick to build a language-independent protocol, bounded arithmetic parsing with `ast`, IANA time zones with `zoneinfo`, and asynchronous subprocess cancellation using its standard library. It has no pip dependencies in this prototype. Its costs include another resident runtime, JSON serialization, duplicate lifecycle/configuration code, and a second extension system to maintain.

Moving ordinary logic to QML/JS could remove that plumbing, but it is not automatically a performance win. A long-running JS function can block the shared shell. Likewise, Python `async` functions do not move CPU work onto another thread: the bundled extensions share one event loop, so a blocking provider can delay all host responses. Only the external command path currently has process-level cancellation and timeout containment.

| Option | Why consider it | What needs evidence |
| --- | --- | --- |
| QML/JS in the existing Omarchy shell | Closest ecosystem fit; shared services and runtime; leading choice for ordinary menu logic. | UI-thread work, available APIs, parser/time-zone correctness, extension failure behavior. |
| QML/JS plus a small on-demand helper | Keep rare expensive work or missing functionality outside the UI. | Whether launch latency and repeated process creation cost more than a persistent worker. |
| QML plus a resident Python worker | Reuse the working prototype and standard-library functionality. | A concrete workload justifying its resident cost and continued protocol complexity. |
| A compiled worker or Qt module | Potentially appropriate for a measured bottleneck or unavailable Qt functionality. | Build/distribution/ABI burden versus a demonstrated gain; not a default rewrite target. |
| Standalone GTK4 or separate Qt application | More independence from shell internals. | A compelling benefit sufficient to justify new integration and lifecycle work. |

The provisional recommendation is QML/JS for the shell and lightweight capabilities, using existing native services first. Decide whether any helper survives **per capability and measured need**. Do not replace the calculator with `eval`, lose DST handling, or start a new interpreter on every keystroke simply to remove a resident Python host.

## Extensions through Omarchy's ecosystem

The user's proposed distribution model is:

1. Maintained capabilities live in this repository and are reviewed through PRs.
2. Community authors publish independent Omarchy plugins that add Flint capabilities. Omarchy remains responsible for their installation, updating and enabling/disabling.

“Plugin for a plugin” describes a dependency, not an existing Flint API. Omarchy has menu/service and other shell plugin kinds; it does not currently define a Flint search-provider kind. Two ideas are under consideration: a service plugin registering a provider object through a supported host interface, or Flint discovering namespaced capability metadata from Omarchy's plugin registry. Neither integration mechanism has been demonstrated. A publicly supported way for plugins to find each other must be verified before selecting either.

Questions the contract must answer:

- **Lifecycle:** registration before or after Flint loads; absent Flint; enable/disable; reload; removal; unregistration; interrupted work; incompatible versions; duplicate IDs; reference cleanup.
- **Minimal API:** stable provider/result IDs, query scopes, cancellation, incremental results, error reporting, activation, settings schema and optional previews. Keep view rendering generic where possible. Whether arbitrary QML views are needed initially is open.
- **Ownership:** should bundled capabilities and external plugins implement the same interface? Which generic services belong in the core? Avoid accumulating capability-specific branches in `Flint.qml` or the registry.
- **Scheduling:** cheap synchronous results versus asynchronous work, bounded outputs, query generations, lazy activation, and no work while hidden unless a capability genuinely needs it. Cancellation cannot preempt a blocking function in the UI thread.
- **Ranking:** common result semantics and score ranges so a provider cannot accidentally dominate everything. Current providers can supply numeric scores; the future policy is unsettled.
- **Settings and state:** one authoritative configuration per setting, migration/versioning, unknown-field preservation, and a clear distinction between a plugin being installed, enabled in Omarchy, and enabled as a Flint provider.

The current `~/.config/flint/extensions/` command protocol is an experiment, not a commitment to a second marketplace. Decide whether to remove it, retain it only for workers, or expose it as an optional adapter after the native contract is clear.

### Trust and failure containment

Use **maintained/reviewed**, not “confirmed safe,” for bundled extensions. The guide states that Omarchy plugins are unsandboxed and share the user's permissions and shell process. Marketplace distribution is not a sandbox. In-process extension code can perform file/command access or freeze the shell.

The prototype validates its own action messages and bounds external process time/output, but neither that validation nor a separate process is a security sandbox. Bundled Python code also runs with full user access. Review whether a worker option is needed for reliability; actual security isolation would require a separate, explicit design. Provenance, optional-provider activation and error visibility should remain understandable without presenting declarative permissions as enforced OS isolation.

## Behavior to preserve from the review build

User testing led to these fixes, already implemented before this handoff:

- Removed the overlapping orange top line; aligned the search icon and brand labels. Compact layout is now the default at 640 logical pixels, with a 760-pixel Comfortable option in Appearance settings.
- Bare `22` produces a calculator result. `22+` retains a disabled calculation preview; `22+1` produces a copyable result.
- Typing keeps previous rows visible while updated results arrive. Stable IDs update existing delegates, stale responses are rejected, and a loading hint is delayed rather than flashing on every keystroke. Activation waits for current results.
- Strong application-name matches get priority over incidental configuration matches. Frecency learns application/menu selections with a 14-day half-life and bounded bonus. It records dispatch, not confirmed successful launch.
- Escape immediately closes the window. Left Arrow/Backspace go back when the search is empty; text editing remains normal otherwise. Entering or leaving a submenu resets selection to the first row; a stationary pointer cannot carry the previous row selection into the new menu.

Frecency stores hashed provider/result IDs, weights and timestamps in local state, not query text, prompts or clipboard contents. Hashing IDs is not a security boundary. Better fuzzy matching remains deferred; eventually evaluate typo tolerance, abbreviations, word boundaries and relevance using realistic application/menu queries, with frecency as a separate ranking signal.

## Performance evidence and what it does not prove

See [verification.md](verification.md) for the measurement table. The **original build, before the feedback fixes**, had warm in-process query medians of 0.08–0.32 ms for the measured non-emoji cases and 4.00 ms for emoji. These samples excluded startup, IPC, debounce, rendering and launching. They are not end-to-end responsiveness results.

A three-second hidden sample after UI/screenshot checks showed **420.0 MiB RSS for standalone Quickshell and 27.0 MiB RSS for Python**, with CPU counters increasing by 2 and 0 ticks respectively. RSS includes shared mappings. This is neither exclusive memory accounting nor a battery test, and the footprint is not satisfactory evidence for the lightweight goal. Do not add these figures and label the sum incremental cost to Omarchy.

The current input debounce is 24 ms. The host coalesces fast results within a window of up to 16 ms; it does not necessarily wait 16 ms if every provider finishes sooner. The empty-state loading hint waits 180 ms. Launches are dispatched after a 70 ms delay intended to release the keyboard-grabbing window. These are provisional tuning choices, not performance guarantees. Configuration is reread per query, external command providers can spawn per eligible query, and model updates use dynamic roles; all deserve profiling if retained.

There is no recurring search timer while hidden and no additional clipboard capture watcher. That reduces avoidable work, but battery impact is still unmeasured. Sharing the Omarchy process should avoid a duplicate Qt runtime; its actual marginal memory, wakeups and GPU cost remain unknown.

Ask Fable to propose repeatable measurements and explicit budgets for:

- Hotkey-to-first-frame and query-to-correct-results latency, warm/cold and p50/p95/p99, including fast typing and slow providers.
- Frame time, dropped frames, allocations, delegate churn, image/icon caches and long-session memory growth.
- Incremental PSS/private memory, CPU wakeups and GPU activity relative to unmodified Omarchy: hidden, opening, typing, previewing and closing.
- Extension startup, cancellation, timeout/failure recovery and large indexes; first-party only versus multiple community providers.
- Battery/power under controlled comparable conditions, including the cost of retaining versus starting a worker.

The [Qt Quick performance guide](https://doc.qt.io/qt-6/qtquick-performance.html) supports asynchronous, event-driven work and profiling actual binding/JS/rendering costs. A smaller process count alone is not sufficient evidence for a faster or more efficient design.

## Compatibility, settings and other open work

| Area | Current behavior / outstanding decision |
| --- | --- |
| Omarchy menu parity | Adapter indexed 320 stock entries / 263 actions, including user JSONC overrides, links, guards and dynamic providers. Indexing is not proof every action works. Guards/provider outputs are cached, so freshness also needs review. |
| Routes and dmenu | Direct leaf routes currently show a command for explicit activation instead of immediately running it on summon. Caller width/height is normalized to Flint's card. Simultaneous callers, cancellation during reload and exact stock protocol parity still need testing. |
| Native lifecycle | Installation, bar integration, existing keybindings/IPC, disable/restore, hot reload, shell restart and removal have not been exercised in the shared shell. Manifest validation does not establish these. |
| Settings | Prototype uses `~/.config/flint/config.json`, typed manifest schemas and atomic writes. Decide whether native Omarchy configuration should own these settings, or a separate file remains justified. Define migration, concurrent edits, defaults, disabled providers and a settings entry that stays recoverable. |
| Appearance | Compact/Comfortable, accent and preview settings exist. Theme/font tokens, contrast, text scaling, accessibility, IME, multi-monitor placement and focus behavior need broader checks. Preserve Flint's visual identity while adapting to Omarchy. |
| App launching | Shared native metadata is available; standalone mode uses Quickshell DesktopEntries. Review launch semantics, desktop actions, hidden apps and cache invalidation against Omarchy's app library. The user manually confirmed Google Chrome launches. |
| Calculator/converter | Bounded arithmetic and unit tables work; IANA time-zone conversion rejects DST gaps/folds. Precision, locale, dates/city ambiguity, parser coverage and equivalent correctness after any port remain open. Currency is not implemented. |
| Clipboard/emoji/colors | Reuse installed history/data; clipboard search is scoped, not included in every global query. Text/image copy and screen picker integration need broader end-to-end checks. Avoid a duplicate watcher and sensitive result/log leakage. |
| AI continuation | Fallbacks use configured provider and a single shared launch mode. Desktop/browser actions copy the prompt for manual paste. Installed Claude advertises a New Chat link; installed ChatGPT does not, so Flint only opens its app. CLI mode passes literal prompt arguments to Codex/Claude. Typing does not send a network request. |
| AI decisions | Verify installed applications and current supported deep links; define missing-target fallback, per-provider versus shared mode, and how much prompt handoff automation is actually possible. Desktop/CLI flows have not been tested end to end. Do not promise that opening an app always creates a populated new chat. |
| Errors and maintainability | Review worker exits/restarts, outstanding activations during navigation/reload, stale results and confirmation state. The prototype favors compact code; assess decomposition, dependency boundaries and diagnostics before extending its API. |
| Distribution | Permanent name/ID, minimum Omarchy version, dependency declaration, upstream update strategy, release packaging and provider compatibility policy are undecided. No remote is configured. |

## Verification status

At handoff, **27 backend tests** and **nine live UI test groups** passed, and the plugin validator accepted the checkout. The UI checks cover row stability/selection, installed Chrome ranking, calculations/conversions/colors, fallbacks/settings, Omarchy root/fonts and dmenu select/input/cancel. These are review-harness tests, not proof of native replacement compatibility.

The user manually confirmed calculator copy/paste and a Chrome launch. Automated checks avoid invoking stock menu actions or launching AI sessions. Screenshots under `assets/` document the rendered prototype. Installed Quickshell metadata produces lint warnings despite successful runtime loading; standalone scanning also flags the native bar's `qs.Ui` import. Full in-shell import and lifecycle validation is still pending.

## Proposed next sequence, subject to review

1. Review the stock menu and this prototype together. Agree on core boundaries, runtime choice and the supported replacement mechanism before expanding functionality.
2. Establish a native menu clone with parity for stock lifecycle/routes/dmenu; measure its baseline and carry over the accepted UI fixes.
3. Demonstrate one bundled capability and one independent Omarchy plugin using the proposed provider/settings contract, including disable/reload/removal. Keep this experiment small before declaring a public API.
4. Move remaining capabilities with their behavioral tests, retaining helpers only where justified. Verify live app/clipboard/AI behavior and performance in the shared shell.
5. Improve fuzzy matching and calibrate ranking/frecency against real queries once those boundaries are settled. Prepare distribution only after integration and performance checks.

## References for the reviewer

The local installed source above is the tested environment; online branches can move. Verify differences instead of assuming that the latest web example exactly matches this machine.

- [Omarchy plugin development guide](https://plugins.omarchy.org/develop.html) — guide raised by the user, including cloning, runtime contract and validation.
- [Omarchy shell reference](https://github.com/basecamp/omarchy/blob/quattro/docs/omarchy-shell.md) and [shell plugins manual](https://github.com/basecamp/omarchy/blob/quattro/manual/32-shell-plugins.md) — official upstream contracts to compare with installed source.
- [Quickshell guide](https://quickshell.org/docs/v0.3.0/guide/) — runtime/component guidance.
- [Qt Quick performance considerations](https://doc.qt.io/qt-6/qtquick-performance.html) — profiling and UI-thread guidance.
- [README](../README.md), [earlier architecture note](architecture.md), [experimental API](extensions.md), [verification record](verification.md) — implementation-specific context.

## Prompt to give Fable

```text
Review this Flint checkout as an independent architecture and code reviewer.
Start with docs/fable-review.md, then inspect the implementation and the
installed/upstream Omarchy menu and plugin APIs. The document distinguishes
the current prototype, the leading proposal, and unresolved decisions;
challenge all three where the evidence warrants it.

We want a Raycast-inspired, complete Omarchy menu replacement with excellent
responsiveness, low idle/battery cost, and an architecture in which every
capability is an extension. Maintained extensions should ship in our repo;
community capabilities should preferably use Omarchy's existing plugin
ecosystem. Settings must be editable in a config file and generated menus.

The working build is QML plus a resident Python host. The leading alternative
is a clone of the native Omarchy menu, QML/JS capabilities, and an agreed
interface for other Omarchy plugins. QML embeds JavaScript; Python is an
implementation choice, not a prerequisite. Assess whether any worker runtime
is justified for specific capabilities instead of assuming a rewrite or
equating fewer processes with better performance.

Please produce:

1. A clear recommendation on clone/adapt versus separate application, stack,
   core responsibilities, and which current pieces to keep, replace or remove.
   Compare realistic alternatives and explain the important tradeoffs.
2. A supported Omarchy integration design: lifecycle, menu/IPC/dmenu parity,
   shared services, settings ownership, theme integration, and community
   provider discovery/versioning. Resolve or explicitly flag the publishing
   tension around omarchy.clonedFrom and restoration of the original menu.
   Do not invent an Omarchy extension API or assume cross-plugin discovery
   exists; cite the documented API or source that makes the design possible.
3. Prioritized code findings with file/line references and concrete user or
   performance consequences. Focus on correctness, UI blocking, cancellation,
   stale results/actions, subprocess lifecycle, caching, model/rendering cost,
   plugin reload/disable, configuration, and maintainability. Distinguish
   demonstrated bugs from hypotheses needing measurement. Assess trust and
   failure containment without treating a process or permission manifest as
   a sandbox.
4. A practical performance test plan and proposed acceptance budgets: real
   hotkey/query latency, frame time, incremental PSS/private memory, idle
   wakeups/GPU work, long-session behavior and battery/power. The historical
   backend timings and standalone RSS in the handoff do not prove production
   performance. Identify the smallest experiments needed to choose a runtime.
5. A staged migration/validation plan that preserves the accepted UX fixes
   and demonstrates one separately distributed Omarchy provider before the
   public contract is frozen. End with the few decisions that require the
   owner's input, ordered by impact.

Better fuzzy matching is explicitly deferred until the architecture is
settled. Review its future boundary and interaction with frecency, but do not
choose or implement a new matcher now. Include the settings and AI handoff
requirements in your architectural assessment; distinguish implemented
behavior from desired desktop/CLI capabilities that still need verification.

This request is for review and recommendations. Do not rewrite the project,
install/replace the active menu, publish it, or add a Git remote. Read-only
inspection and isolated checks are welcome; live UI tests manipulate the
user's review palette, so describe any further interactive validation needed.
Use primary Omarchy/Quickshell/Qt sources and state version assumptions.
```
