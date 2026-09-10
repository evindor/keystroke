# Architecture

Keystroke is one Omarchy `menu` plugin. Everything runs in `omarchy-shell`'s QML engine; local queries stay synchronous and never wait for Codex. Speech has its own daemon; the optional Codex transport stays warm for ten idle minutes.

```text
omarchy-shell
  ├─ BarWidget.qml (bar-widget entry point: the menu button, then the palette's bar items,
  │                 read off the keepLoaded Keystroke instance through shell.panelLoaders)
  └─ Keystroke.qml (menu entry point, keepLoaded)
       ├─ window, keys, navigation stack, dmenu protocol, effects, config, frecency,
       │  bar items (host.setBarItem: one { text, tooltip, payload } per enabled provider)
       ├─ providers/Registry.qml
       │    ├─ bundled: OmarchyMenu, Applications, Calculator, Converter, Colors,
       │    │           Emoji, Clipboard, Files, Hotkeys, Codex, AiWeb, Extensions, SettingsProvider
       │    └─ extensions: Service.qml of every folder under extensions/ (ships with Keystroke) and
       │                   ~/.local/share/keystroke/extensions (local work), created here only once
       │                   the user turns it on; off means never compiled
       ├─ providers/Extensions.qml   the Extensions screen: switches, setup scripts in a visible
       │                             terminal, source links (core/Extensions.js)
       ├─ core/*.js   Match (fuzzy matcher + tiers), Patterns (provider-declared query shapes), SettingsTree, Frecency, Settings, VoiceBindings, Intent, Calculator, Units, Colors, Emoji, AiTargets, Files, Extensions
       ├─ omarchy/MenuModel.js   vendored stock menu model (parse, merge, routes, guards)
       ├─ voice/VoiceSession.qml   voxtype recording lifecycle, optional live transcript and audio levels
       ├─ codex/      AppServer, CodexSession, ConversationView, Policy
       └─ ui/         ResultRow, PreviewPane, Keycap, VoiceWave
```

## Voice

`voice/VoiceSession.qml` drives the voxtype daemon that Omarchy ships, one recording at a time: `voxtype record start --file <runtime>/keystroke-voice.txt --no-osd` (voxtype hides its own overlay for tools that draw their own), `voxtype-audio-bridge` for peak/RMS frames at 100 Hz while listening (it reads the daemon's audio socket; nothing else touches the microphone), then `voxtype record stop --wait --json` whose `text` becomes the query. The daemon's state file is watched so a recording the daemon ends on its own (its max duration) is still collected, with the transcript file as fallback. Idle cost: one `FileView` on the state file; detection (`command -v voxtype`) runs at load and at most every 30 s on open.

Two triggers, both host-owned in `Keystroke.qml`:

- **Tap.** The hotkey's second press reaches the plugin as the shell's `close()` (toggle → hide). With the integration on and the palette in palette mode, that call starts a recording instead of closing, and the next one stops it. `Esc`, the scrim and `omarchy menu summon` still close or reset. An explicit `omarchy menu close` takes the same path; nothing in Omarchy calls it.
- **Hold.** Hyprland is the only party that knows the key is still down, so two user-side bindings feed IPC methods: a long-press bind (`bindo`, fires after the keyboard repeat delay whichever order the keys are released in later) calls `voiceHold`, and a release bind (`bindr`) calls `voiceRelease`. Hyprland's release bind only fires while the modifier is still held (`handleKeybinds` compares the current modmask), and it swallows the hotkey's own release, so the palette also ends a hold when the modifier's release (`Key_Super_L`/`Key_Meta`) reaches the search field, which Hyprland does deliver. A tap's release must not end anything, so the modifier release only counts when the recording was started by a hold. `core/VoiceBindings.js` generates the block for `~/.config/hypr/bindings.lua`, recognises it by its markers and rewrites it in place; the Settings row confirms, writes atomically and runs `hyprctl reload`.

`↵` while listening only stops recording; a fresh Enter after transcription activates the visible selection. Any other non-modifier key cancels the recording and pending suggestion before behaving as usual. The transcript replaces the query through the normal `edited()` path, so ranking, previews and frecency are untouched.

**Binary and configuration.** `VoiceSession` resolves `voxtype` from the user's `PATH` and takes the audio bridge from the same directory (falling back to `voxtype-audio-bridge` on `PATH`). Keystroke does not install another build, write a systemd drop-in, or edit Voxtype's config. Its only behavior overrides are scoped to its own recording: `--file` keeps the result out of the user's configured output target and `--no-osd` avoids drawing two recording interfaces. Every other Voxtype choice remains the user's.

**Live words.** Live partials are opportunistic. While listening, the session watches `$XDG_RUNTIME_DIR/voxtype/transcript` through a `FileView` behind a `Loader` plus an 80 ms poll (a mirror writer may replace the file by rename). If the running daemon publishes that integration file, `partial(text)` updates the query and results as speech arrives. If it does not, the path stays absent and the final transcript still arrives through `record stop --wait --json`, with the requested transcript file as fallback. This keeps current Voxtype releases useful without opting the user into an experimental build or streaming configuration.

**Query.** `core/Intent.normalize()` turns the transcript into a query: trailing punctuation, a leading launcher verb and filler words are dropped ("Launch Chrome." → `Chrome`), because the matcher treats punctuation as literal characters and AND-s the words.

**Activation.** Enter while recording only stops it; Enter while transcribing is consumed. A fresh Enter activates the selected local result or explicit Codex/clipboard choice. The complete original transcript is passed separately as `ctx.rawQuery`; normalization applies to local matching only.

**Recording cancellation.** Cancellation retires the CLI transcript reader before sending `record cancel`, then removes temporary output after the cancellation acknowledges. New recordings are rejected during that brief cleanup window, preventing an old `--wait` or cleanup from interfering with the next session. A daemon finishing streaming directly into idle also triggers final transcript collection.

## Codex

`providers/Codex.qml` owns the durable session and an optional provider view. `codex/AppServer.qml` speaks asynchronous JSONL RPC to one version-checked `codex app-server --stdio`. It initializes, reads configured capabilities/model/account readiness, correlates responses, bounds logs and enforces startup/request deadlines. It never attaches to the desktop's private server. Ten idle minutes shut down the child; resuming rehydrates the saved conversation.

`CodexSession.qml` tracks connection, thread, turn and item identities; reconciles early notifications and final items; coalesces deltas every 32 ms; handles interruption, drafts, scoped approvals and questions. Escape requests interruption offscreen. A ten-second unacknowledged interruption closes the connection without retrying the request. Codex owns history; `~/.local/state/keystroke/codex.json` is an atomic forty-entry index with drafts.

Quick mode explicitly disables shell, code execution, local environments, inherited MCP, connected apps, plugins and hooks, while retaining web search. Agent mode is deliberately selected with a visible working directory and Codex workspace-write/on-request permissions. No answer text is interpreted as an effect. Handoff stops an active turn and exits the owned server: unsubscribe alone retains Codex's writer lease and prevents another client from resuming.

`ConversationView.qml` provides selectable Markdown, source links, follow-up dictation, steering and a scrollable approval view. The root hosts it through the generic provider-view effect and resumes normal launcher behavior on the next summon.

## Query flow

Selection learning is the final ranking pass, after lexical and semantic matching.
Remembered rows retain their general frecency bonus (12 points for one selection,
capped at 36). A choice for the same normalized query and scope adds a separate
72-point first-selection bonus, capped at 108, so a preferred file can overcome
the file provider's score discount. Both weights decay with a 14-day half-life.
Only current matching candidates in the item tier are reordered; learning cannot
revive filtered rows or overtake computed answers. Query-specific choices share
the existing bounded usage store as hashed keys, with no raw query text. Old usage
data remains valid; query preferences start with selections made after this update.
Query case and repeated whitespace are normalized; different prefixes and scopes
learn independently. No embedding model or retraining is required for learning.

Keystrokes debounce 25 ms; asynchronous refreshes respect that pending pause, while Enter flushes it immediately. A refresh (`host.requery(options)`) is coalesced per event-loop turn; when it names its provider (`{ provider, catalog: false }`) only that provider is queried again and the other providers' rows for the unchanged query are reused. Then the host calls `query(ctx)` on every enabled provider (root) or the owning provider (scoped). Before each call the host tests the provider's declared `patterns` (`core/Patterns.js`, compiled once per registry rebuild in `providers/Registry.qml`) against the query: the matched ids reach the provider as `ctx.patterns`, and the largest boost is added in `normalize()` to every row the provider returns that already has a positive score. Providers return rows synchronously. Anything slow (guards, dynamic menu providers, the time-zone helper) returns what it has, calls `ctx.pending()`, and later calls `host.requery()`; the host re-runs the query and keeps the selection. Rows are normalized, ranked by host-owned tiers (`answer > item > fallback`), scored within a tier, and reconciled into a fixed-role `ListModel` by uid so delegates update in place while typing. Previews are read from the selected row's JS object, never copied into the model.

## Omarchy menu parity

`providers/OmarchyMenu.qml` is a port of the stock `Menu.qml` logic over the vendored `MenuModel.js`: default plus user JSONC (watched, merged per key), aliases and links through `resolveRoute`, leaf routes executed on summon, `when`/`checked` guards evaluated as one batch on load and on every open (never per query), the `fonts` (volatile) and `power-profiles` providers loaded on submenu entry or search and cached for the session, actions run through `Util.execDetached` (`bash -lc`). The `apps` submenu is the Applications provider, which uses `shell.appLibrary` for entries, hidden filters, icons, launch feedback and uninstall.

## Integration points used

All from Omarchy 4.0.2 source: property injection of `shell`, `manifest`, `pluginRegistry` (`shell.qml`), `open/close/opened` and `shell call` methods, `PluginRegistry.resolveEnabledId` and `restoreCloneSource` keyed by `omarchy.clonedFrom`, `Color.menu.*`, `Style.font.menuFamily`, `Style.space`, `Style.cornerRadius`, `Style.gapsOut`, `Border.surfaceSpec`, `BorderSurface`, `ConfirmDialog`, `PointerMoveGate`, `Util.execDetached/execArgv/alpha/fileUrl/shellQuote`. The layer namespace is `omarchy-menu` so the stock no-animation layer rule applies.

## Files

`providers/Files.qml` runs `fd` outside the UI thread for each distinct query under the home directory. The default fuzzy mode translates each word into an escaped subsequence regex; literal mode keeps the old substring behavior. The final word must match the basename, and preceding words match relative path components. Spaces and slashes separate terms. This fixes `dwnlds`: previously literal candidate generation discarded Downloads before fuzzy ranking ever saw it.

At the root, `~` restricts providers to Files and bypasses embeddings. `~dwnlds`, `~ dwnlds`, and `~/dwnlds` all work. Bare `~` shows a typing hint without walking the disk. The `searchMode` setting selects `fuzzy` (default), `literal`, or `prefix` (only explicit file search at the root). The Files screen and `~` always use fuzzy search. Existing file/folder/hidden settings still apply; gitignore rules remain respected.

Each walk uses two threads, stops after 400 candidates, and has a three-second watchdog. New queries cancel obsolete walks; a summon caches at most 32 queries. Queries need two characters and are bounded to 128 characters/eight terms. NUL-delimited output preserves unusual filenames, and argv avoids shell interpolation. QML rechecks paths below home and ranks the bounded candidates with `Match.match`, retaining the 0.55 file weight and final host-owned selection learning. The main palette shows its configured limit; `~` and the Files screen show up to 60. There is no persistent filesystem index or model for file search. A broad query can hit the candidate cap before reaching the best match; deeper paths or longer queries help. Slow disks and hidden trees may reach the watchdog and return partial results.

`↵` uses `xdg-open`; `Ctrl+↵` opens a terminal in the selected directory (or a file's parent).

## Hotkeys

`providers/Hotkeys.qml` puts Omarchy's Hyprland keybindings at the root of the palette, named by what they do, with the keys as the row's accessory. It does not read `hyprctl binds` itself: Omarchy's `omarchy-menu-keybindings` (the script behind `Super+K`, which Keystroke already renders over the dmenu protocol) already merges Lua and conf binds, resolves `code:` keys through the keymap, cleans dispatcher arguments, orders the list and caches it under `~/.cache/omarchy/`. The provider sources that script with `--print` (defining its functions with the display lines sent to `/dev/null`) and calls its `output_binding_records`, which prints one record per bind: `"SUPER + F … → Full screen\tlua\thl.dsp.window.fullscreen(…)"`. `core/Hotkeys.js` parses those records, merges a label bound twice to the same action into one row listing both combos (Browser on `Super + Shift + ↵` and `Super + Shift + B`), spells the keys the way the palette's own hints do, and scores rows with `Match.match` on the label, the combo and, for `exec` binds, the command; a query that spells a combo exactly (`super f`) gets a bonus over binds that merely contain those keys. Activation returns an `exec` effect whose argv sources the same script and calls its `dispatch_binding` with the dispatcher and argument as literal arguments, so running a row does what pressing the keys does (Lua expressions through `hyprctl dispatch`, `exec` through `hl.dsp.exec_cmd`, `sendshortcut` through `send_key_state`). Binds whose dispatcher the script could not resolve (Lua closures such as Close window, Universal copy) are shown disabled with "Only from the keyboard". The list is reloaded at most once per 30 s on summon; the script's own cache makes that a hash of `hyprctl binds` and a `cat`.

## Helpers

The optional Codex and speech transports are described above. File search uses `fd`. `helpers/timezone.py` QML's JavaScript has no IANA zone data; the converter spawns the helper once per distinct time query after a regex gate matches, with a 1 s timeout, and caches the answer. The helper owns the grammar (abbreviations such as `pt`/`cet`/`ist`, city and country names, IANA zones, UTC offsets, `now in <zone>`, relative dates); the gate in `core/Units.js` only checks that the query is time-shaped. Answers marked `live` ("now in london") are re-run every 30 s while shown.

## Settings and state

`~/.config/omarchy/keystroke.json` (FileView, watched, atomic writes; `core/Settings.js` validates against provider schemas, preserves unknown fields, refuses to overwrite a file that does not parse). `~/.local/state/keystroke/usage.json` holds frecency (`core/Frecency.js`: md5 of provider/row id, decaying weights, 2000-entry cap). Enable/disable of the plugin itself stays in Omarchy's `shell.json`.

## Matching

`core/Match.js` is fzf's FuzzyMatchV2 (Smith-Waterman with affine gaps and bonuses for word starts, camelCase and digits) tuned for a palette: the per-letter score is smaller than fzf's so letters on word starts dominate, a gap never costs more than a few letters so skipping a whole breadcrumb segment is cheap, and matches below 40 % of a perfect prefix are dropped. A row is scored on up to four haystacks: its title, its breadcrumb path below the current scope (× 0.97), its identifiers such as aliases, ids and config keys (× 0.92), and its description, which is prose and only matches when every query word is a prefix of a word in it (flat 50). Query words are AND-ed in any order. Normalised scores put a whole-word prefix at 100 and an exact title at 120; providers add small constant lifts on top (actions +3, confident app matches +45) and frecency reorders within the item tier only.

Every provider that owns a tree searches all of it when a query is present: the Omarchy menu scores descendants of the active submenu against their relative breadcrumb, and `core/SettingsTree.js` flattens every settings screen, setting and enum choice into nodes with breadcrumbs so `keysepro` reaches Keystroke Settings › AI & Web Search › Preferred assistant from the root and `prefcla` selects its Claude choice directly. Prepared haystacks and joined strings are cached per distinct string, and providers cache their breadcrumbs, so a keystroke costs one DP pass per candidate; the test suite times a 700-row worst case (every row matching) at about 10 ms in the QML engine.

## Deferred

Match highlighting in rows and a permanent publishing id.

## Smart Match

`matching/Session.qml` manages one CPU helper, at most one in-flight request and one
latest queued request. `helpers/matching-start.py` fetches the fixed Model2Vec
revision (pinned SHA-256 digests, no client library), then execs the compiled engine
(`matching/engine`, Rust: the BERT WordPiece tokenizer, mean pooling over the
safetensors embedding table and cosine ranking; the shipped static
`matching/bin/keystroke-matching` when its manifest matches this machine and the
source, otherwise built once per source revision with `cargo`). Without cargo it
provisions the hash-locked Python runtime and execs `matching-worker.py`, which
speaks the same protocol. Off stops the process immediately, a model change replaces
it, and two minutes of inactivity unloads it (the engine reloads in about 60 ms).
Errors retain lexical search and expose a retry in Settings > Matching. See
`matching/README.md` for storage, installation, protocol and model details.

Per keystroke the host does no catalog work: catalogs are enumerated once per summon,
scope or configuration change and after a provider's `requery()`, kept with their
intent descriptions, memoized lexical words/families and, per set of intent
constraints, the filtered documents and a digest identifying them. The digest keys
the request so an unchanged catalog is never serialized or re-sent. Frecency keys
are memoized hashes (item hash, colon, query-context hash) computed once per row
and once per query, never inside the sort. `tools/profile_palette.py` measures each
phase offscreen against this machine's real providers.

The host gathers available catalog rows from opted-in providers and root navigation
rows from remaining bundled providers, applies intent/scope constraints, and sends
only metadata to the helper. Cache keys include the query, scope, model and catalog.
Late replies are ignored; removed entries cannot be revived by an old response.
`core/SmartMatch.js` combines exact/fuzzy scores, bounded typo recovery, app aliases
and semantic suggestions without promoting them above explicit computed answers.
Equivalent commands retain the stricter confirmation, and async result reordering
preserves a user-selected UID. Typed provider arguments keep their case; spoken
arithmetic normalization is a separate whole-expression parser in `core/Intent.js`.

Curated intent sentences are paired with original titles and MD5 fingerprints of
source definitions, preventing accidental reuse after ordinary catalog customization.
These are metadata identity checks, not a security boundary. For menu entries the
source key is `[action,target,provider].join(String.fromCharCode(31))`; for hotkeys it is dispatcher,
a unit separator and argument; for apps it is the displayed name. No machine-specific
command strings are shipped in the fingerprint map. Changed entries use live metadata.
