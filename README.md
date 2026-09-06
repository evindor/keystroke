# Keystroke

A Raycast-inspired command palette that **replaces the Omarchy menu**. One native Omarchy `menu` plugin, written in QML/JavaScript, running inside the existing `omarchy-shell` process. No extra runtime, no resident helper, nothing running while it is hidden.

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
- Assistant hand-offs open the target with your prompt already in its composer, nothing goes through the clipboard: Claude desktop via `claude://claude.ai/new?q=…` (the same link Anthropic's own GNOME search provider uses), the Codex desktop app (which is what the Linux "ChatGPT" package installs) via `codex://threads/new?prompt=…`, or in the browser `claude.ai/new?q=` and `chatgpt.com/?prompt=` (`?q=` sends immediately when **Send immediately in the browser** is on). CLI mode opens a terminal with `claude` or `codex` and the prompt as a literal argument. A missing app or CLI falls back to the browser and the row says so.
- `↑`/`↓` or `Ctrl+P`/`Ctrl+N` move, `PageUp`/`PageDown` jump six rows, `↵` or `→` activates, `Ctrl+↵` runs a row's alternate action (terminal for files and folders), `Esc` closes immediately, `Ctrl+U` clears the query, `←`/`Backspace` on an empty query goes back, `Del` on an application offers to uninstall it, `Ctrl+,` opens Settings, `Ctrl+K` opens the selected provider's settings.
- Destructive Omarchy actions (shutdown, reboot, logout, hibernate, removals, config resets) ask for confirmation; turn this off in Settings → Omarchy.
- Selections of apps and Omarchy commands earn a bounded frecency bonus (14-day half-life). State lives in `~/.local/state/keystroke/usage.json` as hashed ids only.
- Speak the query instead of typing it (see [Voice](#voice)): hold the hotkey, or tap it a second time, and the query field becomes a string that moves with your voice.

Every `omarchy menu` route works as before: submenus open scoped (`omarchy menu toggle system`), leaf aliases run immediately (`omarchy menu summon reminder-set`), `apps` opens the Applications provider. Pickers honor `width`/`maxHeight`; a new picker request cancels a pending one (the stock menu left the first caller waiting).

## Voice

Keystroke dictates through [voxtype](https://voxtype.io), the dictation daemon Omarchy installs from Install › AI › Dictation. Nothing else is needed: Keystroke Settings › Voice shows **Voxtype voice command integration**, on by default as soon as `voxtype` is on the PATH, and the screen offers Omarchy's installer when it is not.

Two ways in, both while the palette is open:

- **Tap the hotkey again.** The second tap of `Super+Space` starts listening instead of closing the palette; a third tap stops. `Esc` and clicking outside still close. Set **Second tap of the hotkey** to *Close* to keep the stock toggle.
- **Hold the hotkey.** Press `Super+Space` and keep it down: after Hyprland's key-repeat delay (250 ms in Omarchy) the palette starts listening, and releasing the chord stops it, in either order. This needs two Hyprland bindings on the same key: a long-press bind and a release bind. Settings › Voice › **Hold-to-talk bindings** writes them into `~/.config/hypr/bindings.lua` inside a marked block (confirmation first, then `hyprctl reload`); **Hotkeys to hold** lists the combos, comma-separated, if you open the palette with more than one key. The block is plain Lua you can also paste yourself:

  ```lua
  -- >>> keystroke voice: hold the palette hotkey to dictate (written by Keystroke Settings › Voice)
  o.bind("SUPER + SPACE", nil, "omarchy-shell shell call omarchy.menu voiceHold '{}'", { long_press = true })
  o.bind("SUPER + SPACE", nil, "omarchy-shell shell call omarchy.menu voiceRelease '{}'", { release = true })
  -- <<< keystroke voice
  ```

While listening, the query field shows a string plucked by the microphone (levels come from voxtype's own audio bridge) and the footer says how to finish. Releasing or tapping stops the recording and shows *Transcribing…*; the transcript then **replaces the query** and the matches update. Nothing is activated on its own: `↵` runs the selected row as usual. Pressing `↵` while still listening stops the recording first and runs the top match once the text is in. Typing while listening cancels the recording; typing while transcribing keeps what you type. voxtype's own overlay stays hidden for these recordings (`--no-osd`), the transcript never goes through the clipboard or the virtual keyboard, and the temporary transcript file in `$XDG_RUNTIME_DIR` is removed after every recording.

Model, language, VAD and everything else are voxtype's settings (`voxtype configure`). Whisper transcribes silence as "Thank you." now and then; voxtype's VAD filters that when enabled. With the daemon stopped the palette says so instead of listening.

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

Omarchy ≥ 4.0.2 (Quickshell 0.3, Qt 6.11). `python3` is used only for IANA time-zone conversion, on demand. Omarchy's MIT-licensed menu model is vendored in [omarchy/MenuModel.js](omarchy/MenuModel.js); see [LICENSE](LICENSE).
