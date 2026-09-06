# Keystroke

A Raycast-inspired command palette that **replaces the Omarchy menu**. One native Omarchy `menu` plugin, written in QML/JavaScript, running inside the existing `omarchy-shell` process. The palette uses the existing shell runtime. Speech runs locally on Vulkan; optional Codex reasoning uses the managed subscription through app-server.

Every capability is a provider: applications, the complete Omarchy menu, calculator, unit and time-zone conversion, colors, emoji, clipboard history, files and folders under your home, AI/web continuation, and the settings screens themselves. Community providers are ordinary Omarchy plugins.

## Install

```sh
omarchy plugin add https://github.com/<you>/keystroke.git --enable   # once published
# from this checkout, for development:
bin/keystroke install
```

Enabling Keystroke makes it the menu: `Super+Space`, every `omarchy-menu` binding, `omarchy menu summon <route>`, and the `omarchy-menu-select`/`omarchy-menu-input` pickers all route to it. Disabling or removing it (`omarchy plugin disable evindor.keystroke`, `omarchy plugin remove evindor.keystroke`, or `bin/keystroke uninstall`) restores the stock menu. This works because the manifest declares `omarchy.clonedFrom: "omarchy.menu"`; Omarchy's plugin registry uses that field to route calls for `omarchy.menu` to the enabled replacement and to restore the original afterwards. Keep it.

**Bar-widget quirk (Omarchy 4.0.x).** Keystroke also ships the menu button as a bar widget, so enabling it puts a button in your bar (replacing the stock one in place if you had it). For a third-party plugin, "enabled" means "referenced in shell.json", so removing that button from the bar also disables the menu. If you do not want the button, keep the plugin listed under `plugins[]` in `~/.config/omarchy/shell.json` instead. An upstream issue proposing that clone replacements stay enabled independently of the bar is part of the follow-ups.

The plugin id is `evindor.keystroke` for now; the permanent publishing id may change before the marketplace listing.

## Using it

- Type anything: apps, Omarchy commands, `sqrt(144) + 15% of 80`, `2m in feet`, `32 F to C`, `10 am in London`, `#ff6644`, `:smile`.
- Search is fuzzy everywhere and reaches into submenus. From the root, `prefp`, `keysepro` and `setaiprv` all land on Keystroke Settings › AI & Web Search › Preferred assistant, `prefcla` on its Claude choice, `sysshut` on System › Shutdown. Letters may skip whole words of the breadcrumb, the words of a query can come in any order (`ai prov`), and descriptions match by word. Inside a submenu the same search covers everything below it.
- Computed answers appear first as answer rows with a preview; matches next; Google and the assistants last.
- Files and folders under `~` join the results from two characters on, found by `fd` (Omarchy ships it; hidden and gitignored entries are skipped unless you turn hidden entries on). The words of the query are literal substrings: the last one has to be in the name, earlier ones anywhere in the path, so `docs readme` finds README files under a docs folder and `bindings lua` the Lua files in a bindings folder. `↵` opens a file with its default app and a folder in your file manager; `Ctrl+↵` opens a terminal in the folder (or in a file's folder). They rank below apps and Omarchy entries on purpose and at most ten of them mix into the root (Settings → Files: files, folders, hidden entries, limit); the Files screen shows up to sixty.
- Assistant hand-offs open the target with your prompt already in its composer, nothing goes through the clipboard: Claude desktop via `claude://claude.ai/new?q=…` (the same link Anthropic's own GNOME search provider uses), the Codex desktop app (which is what the Linux "ChatGPT" package installs) via `codex://threads/new?prompt=…`, or in the browser `claude.ai/new?q=` and `chatgpt.com/?prompt=` (`?q=` sends immediately when **Send immediately in the browser** is on). CLI mode opens a terminal with `claude` or `codex` and the prompt as a literal argument. Claude falls back to its browser route; Codex falls back from desktop to CLI and preserves the request if neither is available.
- `↑`/`↓` or `Ctrl+P`/`Ctrl+N` move, `PageUp`/`PageDown` jump six rows, `↵` or `→` activates, `Ctrl+↵` runs a row's alternate action (terminal for files and folders), `Esc` closes immediately, `Ctrl+U` clears the query, `←`/`Backspace` on an empty query goes back, `Del` on an application offers to uninstall it, `Ctrl+,` opens Settings, `Ctrl+K` opens the selected provider's settings.
- Destructive Omarchy actions (shutdown, reboot, logout, hibernate, removals, config resets) ask for confirmation; turn this off in Settings → Omarchy.
- Selections of apps and Omarchy commands earn a bounded frecency bonus (14-day half-life). State lives in `~/.local/state/keystroke/usage.json` as hashed ids only.
- Speak the query instead of typing it (see [Voice](#voice)): hold the hotkey, or tap it a second time, and the query field becomes a string that moves with your voice.

Every `omarchy menu` route works as before: submenus open scoped (`omarchy menu toggle system`), leaf aliases run immediately (`omarchy menu summon reminder-set`), `apps` opens the Applications provider. Pickers honor `width`/`maxHeight`; a new picker request cancels a pending one (the stock menu left the first caller waiting).

## Voice

Keystroke dictates through [voxtype](https://voxtype.io), the dictation daemon Omarchy installs from Install › AI › Dictation. Nothing else is needed: Keystroke Settings › Voice shows **Voxtype voice command integration**, on by default as soon as `voxtype` is on the PATH, and the screen offers Omarchy's installer when it is not. `bin/keystroke voice-setup` (no root) installs a voxtype build with live words and whole-request revision. See [Speaking commands](#speaking-commands) below.

Two ways in, both while the palette is open:

- **Tap the hotkey again.** The second tap of `Super+Space` starts listening instead of closing the palette; a third tap stops. `Esc` and clicking outside still close. Set **Second tap of the hotkey** to *Close* to keep the stock toggle.
- **Hold the hotkey.** Press `Super+Space` and keep it down: after Hyprland's key-repeat delay (250 ms in Omarchy) the palette starts listening, and releasing the chord stops it, in either order. This needs two Hyprland bindings on the same key: a long-press bind and a release bind. Settings › Voice › **Hold-to-talk bindings** writes them into `~/.config/hypr/bindings.lua` inside a marked block (confirmation first, then `hyprctl reload`); **Hotkeys to hold** lists the combos, comma-separated, if you open the palette with more than one key. The block is plain Lua you can also paste yourself:

  ```lua
  -- >>> keystroke voice: hold the palette hotkey to dictate (written by Keystroke Settings › Voice)
  o.bind("SUPER + SPACE", nil, "omarchy-shell shell call omarchy.menu voiceHold '{}'", { long_press = true })
  o.bind("SUPER + SPACE", nil, "omarchy-shell shell call omarchy.menu voiceRelease '{}'", { release = true })
  -- <<< keystroke voice
  ```

While listening, live words keep most of the query field and a small waveform sits to the right. Matches update while you speak. Releasing the hotkey, tapping it again, or pressing `↵` finishes the recording. **A fresh `↵` after transcription runs the visible selection.** Stopping, a model reply, and a timeout never run a command. Typing or navigating cancels the recording; held Enter repeats are ignored. Voxtype's overlay stays hidden (`--no-osd`), the transcript never goes through the clipboard or virtual keyboard, and temporary transcript files are removed after recording or cancellation.

Model, language, VAD and everything else are voxtype's settings (`voxtype configure`). Whisper transcribes silence as "Thank you." now and then; voxtype's VAD filters that when enabled. With the daemon stopped the palette says so instead of listening.

### Dictate to Clipboard

After speaking or typing in the normal palette, **Copy to Clipboard** appears under **Continue with**, alongside the AI and web options. Select it and press **Enter** to copy the original text and close, or **Ctrl+Enter** to copy, close, wait 100 ms, and paste. Spoken command normalization does not alter the copied text or the prompt handed to an AI app.

The separate **Dictate to Clipboard** launcher remains available, as does `bin/keystroke dictate`. It starts a dedicated prose-only recording with these shortcuts:

- **Enter:** finish recording, copy the final transcript, and close Keystroke.
- **Ctrl+Enter:** finish recording, copy, close, wait 100 ms for focus to return, then send Shift+Insert to paste into the previous window.
- **Escape:** cancel, including a pending copy while final transcription is still running.
- Stopping with the voice hotkey leaves the text open for review; Enter or Ctrl+Enter then completes the action.

Copy must succeed before the window closes. Reopening Keystroke cancels a pending paste. The existing voxtype recording limit is 60 seconds on this machine.

### Speaking commands

Speech and search work together:

1. **Words appear as you speak.** With a streaming engine the daemon mirrors the text so far to `$XDG_RUNTIME_DIR/voxtype/transcript`; the palette shows it in the query field and matches follow each revision. The Keystroke fork now uses complete transcript snapshots for file-output sessions: every word remains revisable, punctuation and deletions are preserved, and a final pass processes the complete recording. Audio is retained through the configured recording-duration limit (60 seconds here). Ordinary live typing retains its rolling-window behavior. Longer requests require more inference work per update. This needs voxtype 1.1's sliding-window streaming plus a small patch that exposes the partials, proposed upstream and meanwhile built from [evindor/voxtype](https://github.com/evindor/voxtype) (branch `feature/live-transcript-file`) by `bin/keystroke voice-setup`. The build lands in `~/.local/share/keystroke/voxtype`, a systemd drop-in makes it the daemon, and the palette prefers it over the packaged binary; delete `~/.config/systemd/user/voxtype.service.d/keystroke.conf` to go back. Whisper on the GPU is what makes streaming keep up: `voxtype setup gpu --enable` (Vulkan) turns a 2.6 s transcription into 0.2 s on an Intel Arc iGPU, and the CPU cannot re-transcribe the rolling window every half second.
2. **The transcript becomes a query.** Trailing punctuation goes, so do a leading launcher verb ("open", "go to") and filler ("the", "please"): "Launch Chrome." is searched as `Chrome`. The fuzzy matcher then ranks as if you had typed it.
3. **Choose what to do.** Local matches stay immediate. Ask Codex here answers inside the palette; Copy to Clipboard preserves the full prose. Only explicit activation sends a cloud request.

To stop speech across reboots: `systemctl --user disable --now voxtype`. Restore it with `systemctl --user enable --now voxtype`. `bin/keystroke voice-setup` builds only Vulkan speech recognition and whole-request revision. No local language model is installed.

### Codex inside Keystroke

Type or speak, then select **Ask Codex here**, or type `? ` before your question to put it first. Answers stream inside the palette. **Enter** sends a follow-up; **Shift+Enter** adds a line; your voice hotkey fills the composer. **Update request** steers a running answer. **Stop** interrupts; **Escape** closes and interrupts. Reopen **Codex → Recent questions** to continue. **Left/Backspace on an empty composer**, or the header’s back arrow, returns to the previous results without closing Keystroke. Buttons and fields use Omarchy’s shared components and follow the current theme.

**Continue in Codex** (Ctrl+Enter in the conversation) saves and hands the same conversation to your configured desktop app or CLI. A running answer stops first. The **Open task in Codex** result opens a new request in that destination; desktop prefills the composer for you to send. Clipboard's Ctrl+Enter still means paste.

Settings → Codex selects the model, Fast/Standard processing, destination and optional working folder. The default is **GPT-5.6 Luna, low effort, Fast** using your existing `codex login`. Fast uses more subscription allowance. Keystroke never reads or copies credentials. This integration pins **Codex CLI 0.153.2**; other versions display a compatibility error.

Quick questions can search the web but cannot execute local commands, edit files or invoke connected apps. Within the Codex scope, **Do this here · desktop settings** starts an explicit agent task scoped to `~/.config`; a configured working folder adds a project task option. Required approvals and questions appear in the panel. Continue in the full app for unsupported capabilities.

Keystroke owns one local `codex app-server` transport process, shuts it down after ten idle minutes, and exits it before handing a conversation to another client. Conversation records remain managed by Codex; Keystroke stores only its recent-question index and drafts. No request is silently replayed after a connection failure.

Local Gemma/vLLM runtimes were retired. See [the integration verification](docs/codex-integration-verification.md) for measured behavior and compatibility limits.

## Settings

One file, hand-editable and hot-reloaded: `~/.config/omarchy/keystroke.json` (see [keystroke.example.json](keystroke.example.json)). The `voice` section holds the integration switch, the second-tap behaviour and the hotkeys the Hyprland block is generated for. Settings screens are generated from each provider's schema; writes are atomic, preserve unknown fields, and are refused while the file fails to parse. Bundled providers default to enabled, community providers to disabled. Appearance: density (compact/comfortable), accent (theme accent or ember/violet/mint), previews on/off. Colors, fonts, radius and spacing follow the active Omarchy theme.

## Providers

Bundled providers live in [providers/](providers/) and are the reference implementation of the contract in [docs/providers.md](docs/providers.md). A community provider is an Omarchy plugin of kind `service` with an `x-keystroke` marker; Omarchy installs, enables, reloads and removes it, and Keystroke finds it through `shell.serviceFor()`. See [examples/keystroke-hello](examples/keystroke-hello/).

Community providers run unsandboxed inside your shell with your permissions, like every Omarchy plugin. Keystroke shows their provenance in Settings and keeps them off until you enable them.

## Verify

```sh
bin/keystroke validate     # omarchy plugin validate
bin/keystroke test         # qmltestrunner unit tests, time-zone helper checks, qmllint
```

[docs/verification.md](docs/verification.md) records what was run on the reference machine, including the temporary in-shell install. [docs/architecture.md](docs/architecture.md) describes the design; [docs/history/](docs/history/) keeps the prototype review that led to it.

## Requirements

Omarchy ≥ 4.0.2 (Quickshell 0.3, Qt 6.11). `python3` is used for IANA time-zone conversion and optional native-audio capture, on demand. Omarchy's MIT-licensed menu model is vendored in [omarchy/MenuModel.js](omarchy/MenuModel.js); see [LICENSE](LICENSE).
