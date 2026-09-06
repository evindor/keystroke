# Architecture

Keystroke is one Omarchy `menu` plugin. Everything runs in `omarchy-shell`'s QML engine; local queries stay synchronous and never wait for Codex. Speech has its own daemon; the optional Codex transport stays warm for ten idle minutes.

```text
omarchy-shell
  └─ Keystroke.qml (menu entry point, keepLoaded)
       ├─ window, keys, navigation stack, dmenu protocol, effects, config, frecency
       ├─ providers/Registry.qml
       │    ├─ bundled: OmarchyMenu, Applications, Calculator, Converter, Colors,
       │    │           Emoji, Clipboard, Files, Codex, AiWeb, Extensions, SettingsProvider
       │    └─ community: shell.serviceFor(<plugin id>) for every enabled plugin
       │                  whose manifest carries "x-keystroke"
       ├─ providers/Extensions.qml   install/update/remove/toggle community providers through
       │                             Omarchy's plugin scripts; discovery from extensions/index.json
       │                             and the marketplace catalog (core/Extensions.js)
       ├─ core/*.js   Match (fuzzy matcher + tiers), SettingsTree, Frecency, Settings, VoiceBindings, Intent, Calculator, Units, Colors, Emoji, AiTargets, Files, Extensions
       ├─ omarchy/MenuModel.js   vendored stock menu model (parse, merge, routes, guards)
       ├─ voice/VoiceSession.qml   voxtype recording lifecycle, live transcript and audio levels
       ├─ codex/      AppServer, CodexSession, ConversationView, Policy
       └─ ui/         ResultRow, PreviewPane, Keycap, VoiceWave
```

## Voice

`voice/VoiceSession.qml` drives the voxtype daemon that Omarchy ships, one recording at a time: `voxtype record start --file <runtime>/keystroke-voice.txt --no-osd` (voxtype hides its own overlay for tools that draw their own), `voxtype-audio-bridge` for peak/RMS frames at 100 Hz while listening (it reads the daemon's audio socket; nothing else touches the microphone), then `voxtype record stop --wait --json` whose `text` becomes the query. The daemon's state file is watched so a recording the daemon ends on its own (its max duration) is still collected, with the transcript file as fallback. Idle cost: one `FileView` on the state file; detection (`command -v voxtype`) runs at load and at most every 30 s on open.

Two triggers, both host-owned in `Keystroke.qml`:

- **Tap.** The hotkey's second press reaches the plugin as the shell's `close()` (toggle → hide). With the integration on and the palette in palette mode, that call starts a recording instead of closing, and the next one stops it. `Esc`, the scrim and `omarchy menu summon` still close or reset. An explicit `omarchy menu close` takes the same path; nothing in Omarchy calls it.
- **Hold.** Hyprland is the only party that knows the key is still down, so two user-side bindings feed IPC methods: a long-press bind (`bindo`, fires after the keyboard repeat delay whichever order the keys are released in later) calls `voiceHold`, and a release bind (`bindr`) calls `voiceRelease`. Hyprland's release bind only fires while the modifier is still held (`handleKeybinds` compares the current modmask), and it swallows the hotkey's own release, so the palette also ends a hold when the modifier's release (`Key_Super_L`/`Key_Meta`) reaches the search field, which Hyprland does deliver. A tap's release must not end anything, so the modifier release only counts when the recording was started by a hold. `core/VoiceBindings.js` generates the block for `~/.config/hypr/bindings.lua`, recognises it by its markers and rewrites it in place; the Settings row confirms, writes atomically and runs `hyprctl reload`.

`↵` while listening only stops recording; a fresh Enter after transcription activates the visible selection. Any other non-modifier key cancels the recording and pending suggestion before behaving as usual. The transcript replaces the query through the normal `edited()` path, so ranking, previews and frecency are untouched.

**Binary.** `VoiceSession` prefers `~/.local/share/keystroke/voxtype/voxtype` (the build `bin/keystroke voice-setup` installs: voxtype 1.1 with the live transcript mirror, whisper on Vulkan) and falls back to `voxtype` on the PATH; the audio bridge is taken from the same directory. Every CLI call uses that binary, so the client and the daemon (a systemd drop-in points `voxtype.service` at the same file) never disagree on the `--wait` protocol.

**Live words.** Streaming engines (`[whisper] streaming = true`) make the daemon rewrite `$XDG_RUNTIME_DIR/voxtype/transcript` after every partial, final and revision event with the session's text so far, atomically by rename, empty at session start and removed at idle (the patch in `feature/live-transcript-file`, proposed upstream). While listening the session loads that file through a `FileView` behind a `Loader` plus an 80 ms poll (a watcher can lose the inode across renames) and emits `partial(text)` on change; the host puts the text in the query field and runs the normal debounced query, so the results follow the speech. The final transcript still comes from `record stop --wait --json` (the same patch publishes the completion sidecar for streaming file sessions), with the transcript file as fallback.

**Query.** `core/Intent.normalize()` turns the transcript into a query: trailing punctuation, a leading launcher verb and filler words are dropped ("Launch Chrome." → `Chrome`), because the matcher treats punctuation as literal characters and AND-s the words.

**Activation.** Enter while recording only stops it; Enter while transcribing is consumed. A fresh Enter activates the selected local result or explicit Codex/clipboard choice. The complete original transcript is passed separately as `ctx.rawQuery`; normalization applies to local matching only.

**Recording cancellation.** Cancellation retires the CLI transcript reader before sending `record cancel`, then removes temporary output after the cancellation acknowledges. New recordings are rejected during that brief cleanup window, preventing an old `--wait` or cleanup from interfering with the next session. A daemon finishing streaming directly into idle also triggers final transcript collection.

## Codex

`providers/Codex.qml` owns the durable session and an optional provider view. `codex/AppServer.qml` speaks asynchronous JSONL RPC to one version-checked `codex app-server --stdio`. It initializes, reads configured capabilities/model/account readiness, correlates responses, bounds logs and enforces startup/request deadlines. It never attaches to the desktop's private server. Ten idle minutes shut down the child; resuming rehydrates the saved conversation.

`CodexSession.qml` tracks connection, thread, turn and item identities; reconciles early notifications and final items; coalesces deltas every 32 ms; handles interruption, drafts, scoped approvals and questions. Escape requests interruption offscreen. A ten-second unacknowledged interruption closes the connection without retrying the request. Codex owns history; `~/.local/state/keystroke/codex.json` is an atomic forty-entry index with drafts.

Quick mode explicitly disables shell, code execution, local environments, inherited MCP, connected apps, plugins and hooks, while retaining web search. Agent mode is deliberately selected with a visible working directory and Codex workspace-write/on-request permissions. No answer text is interpreted as an effect. Handoff stops an active turn and exits the owned server: unsubscribe alone retains Codex's writer lease and prevents another client from resuming.

`ConversationView.qml` provides selectable Markdown, source links, follow-up dictation, steering and a scrollable approval view. The root hosts it through the generic provider-view effect and resumes normal launcher behavior on the next summon.

## Query flow

Keystrokes debounce 16 ms, then the host calls `query(ctx)` on every enabled provider (root) or the owning provider (scoped). Providers return rows synchronously. Anything slow (guards, dynamic menu providers, the time-zone helper) returns what it has, calls `ctx.pending()`, and later calls `host.requery()`; the host re-runs the query and keeps the selection. Rows are normalized, ranked by host-owned tiers (`answer > item > fallback`), scored within a tier, and reconciled into a fixed-role `ListModel` by uid so delegates update in place while typing. Previews are read from the selected row's JS object, never copied into the model.

## Omarchy menu parity

`providers/OmarchyMenu.qml` is a port of the stock `Menu.qml` logic over the vendored `MenuModel.js`: default plus user JSONC (watched, merged per key), aliases and links through `resolveRoute`, leaf routes executed on summon, `when`/`checked` guards evaluated as one batch on load and on every open (never per query), the `fonts` (volatile) and `power-profiles` providers loaded on submenu entry or search and cached for the session, actions run through `Util.execDetached` (`bash -lc`). The `apps` submenu is the Applications provider, which uses `shell.appLibrary` for entries, hidden filters, icons, launch feedback and uninstall.

## Integration points used

All from Omarchy 4.0.2 source: property injection of `shell`, `manifest`, `pluginRegistry` (`shell.qml`), `open/close/opened` and `shell call` methods, `PluginRegistry.resolveEnabledId` and `restoreCloneSource` keyed by `omarchy.clonedFrom`, `shell.serviceFor` for service plugins, `Color.menu.*`, `Style.font.menuFamily`, `Style.space`, `Style.cornerRadius`, `Style.gapsOut`, `Border.surfaceSpec`, `BorderSurface`, `ConfirmDialog`, `PointerMoveGate`, `Util.execDetached/execArgv/alpha/fileUrl/shellQuote`. The layer namespace is `omarchy-menu` so the stock no-animation layer rule applies.

## Files

`providers/Files.qml` runs `fd` (in Omarchy's base packages) once per distinct query, bounded by `--max-results 400`, from the home folder, with the query words AND-ed as case-insensitive literal substrings of the path, the last one anchored to the final segment (otherwise one matching folder floods the list with its children); a newer query kills a run still walking, a 3 s watchdog keeps whatever was printed, and results are cached for the length of one summon. `core/Files.js` builds the argv (regex-escaped words after `--and=` and `--`, so nothing is read as a flag), parses the output, re-checks the words against the path below `~` (fd matched the absolute path), scores the candidates with `Match.match` on the file name and the relative path at 0.55 weight with a floor of 12, and keeps the best `limit` (default 10 at the root, 60 in the Files screen). No index lives in the heap: a gitignore-respecting walk of a typical home takes tens of milliseconds, a hidden-inclusive one of 280 k entries about 200 ms. `↵` is `xdg-open`; `Ctrl+↵` is the host's alternate activation (`row.altAction`), here `setsid uwsm-app -- xdg-terminal-exec --dir=…` as Omarchy's own launchers do.

## Helpers

The optional Codex and speech transports are described above. File search uses `fd`. `helpers/timezone.py` QML's JavaScript has no IANA zone data; the converter spawns the helper once per distinct time query after a regex gate matches, with a 1 s timeout, and caches the answer.

## Settings and state

`~/.config/omarchy/keystroke.json` (FileView, watched, atomic writes; `core/Settings.js` validates against provider schemas, preserves unknown fields, refuses to overwrite a file that does not parse). `~/.local/state/keystroke/usage.json` holds frecency (`core/Frecency.js`: md5 of provider/row id, decaying weights, 2000-entry cap). Enable/disable of the plugin itself stays in Omarchy's `shell.json`.

## Matching

`core/Match.js` is fzf's FuzzyMatchV2 (Smith-Waterman with affine gaps and bonuses for word starts, camelCase and digits) tuned for a palette: the per-letter score is smaller than fzf's so letters on word starts dominate, a gap never costs more than a few letters so skipping a whole breadcrumb segment is cheap, and matches below 40 % of a perfect prefix are dropped. A row is scored on up to four haystacks: its title, its breadcrumb path below the current scope (× 0.97), its identifiers such as aliases, ids and config keys (× 0.92), and its description, which is prose and only matches when every query word is a prefix of a word in it (flat 50). Query words are AND-ed in any order. Normalised scores put a whole-word prefix at 100 and an exact title at 120; providers add small constant lifts on top (actions +3, confident app matches +45) and frecency reorders within the item tier only.

Every provider that owns a tree searches all of it when a query is present: the Omarchy menu scores descendants of the active submenu against their relative breadcrumb, and `core/SettingsTree.js` flattens every settings screen, setting and enum choice into nodes with breadcrumbs so `keysepro` reaches Keystroke Settings › AI & Web Search › Preferred assistant from the root and `prefcla` selects its Claude choice directly. Prepared haystacks and joined strings are cached per distinct string, and providers cache their breadcrumbs, so a keystroke costs one DP pass per candidate; the test suite times a 700-row worst case (every row matching) at about 10 ms in the QML engine.

## Deferred

Match highlighting in rows and a permanent publishing id.
