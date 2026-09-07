# Keystroke

A Raycast-style command palette that **replaces the Omarchy menu**. One native Omarchy `menu` plugin in QML and JavaScript, running inside the existing `omarchy-shell` process, themed by whatever Omarchy theme is active. Type, or speak, what you want: apps, the whole Omarchy menu, calculations, conversions, colors, emoji, clipboard history, files, Codex, and anything a community extension adds.

<p align="center"><a href="https://evindor.github.io/keystroke/"><img src="site/assets/social-card.png" alt="Keystroke: Raycast-style power for Omarchy" width="960"></a></p>

**[Explore the feature showcase and installation guide →](https://evindor.github.io/keystroke/)**

Screenshots show the real Omarchy interface with public demo data.

## Install

```sh
omarchy plugin add https://github.com/evindor/keystroke.git --enable
```

That is all. Enabling Keystroke makes it the menu: `Super+Space`, every `omarchy-menu` binding, `omarchy menu summon <route>`, and the `omarchy-menu-select`/`omarchy-menu-input` pickers all route to it. Disabling or removing it (`omarchy plugin disable evindor.keystroke`, `omarchy plugin remove evindor.keystroke`) restores the stock menu. This works because the manifest declares `omarchy.clonedFrom: "omarchy.menu"`; Omarchy's plugin registry routes calls for `omarchy.menu` to the enabled replacement and restores the original afterwards. The plugin id `evindor.keystroke` is permanent.

From a checkout, `bin/keystroke install` copies the tree into `~/.config/omarchy/plugins/evindor.keystroke` (no symlinks) and enables it; `bin/keystroke uninstall` reverses that.

**Bar-widget note (Omarchy 4.0.x).** Keystroke also ships the menu button as a bar widget, so enabling it puts a button in your bar (replacing the stock one in place if you had it). For a third-party plugin, "enabled" means "referenced in shell.json", so removing that button from the bar also disables the menu. If you do not want the button, keep the plugin listed under `plugins[]` in `~/.config/omarchy/shell.json` instead.

Requires Omarchy ≥ 4.0.2 (Quickshell 0.3, Qt 6.11). Like every Omarchy plugin, Keystroke runs unsandboxed inside your shell with your permissions; the code is here to read.

## What it does

<table>
<tr>
<td><img src="site/assets/screenshots/calculator.png" alt="Calculator answer" width="360"></td>
<td><img src="site/assets/screenshots/converter.png" alt="Unit conversion" width="360"></td>
</tr>
<tr>
<td><img src="site/assets/screenshots/fuzzy.png" alt="Fuzzy search into settings" width="360"></td>
<td><img src="site/assets/screenshots/extensions.png" alt="Extensions screen" width="360"></td>
</tr>
</table>

- **Type anything**: apps, Omarchy commands, `sqrt(144) + 15% of 80`, `2m in feet`, `32 F to C`, `10 am in London`, `#ff6644`, `:smile`, `readme`, `timer 10m tea`.
- **Fuzzy everywhere, into submenus.** From the root, `prefp`, `keysepro` and `setaiprv` all land on Keystroke Settings › AI & Web Search › Preferred assistant, `prefcla` on its Claude choice, `sysshut` on System › Shutdown. Letters may skip whole words of the breadcrumb, words can come in any order (`ai prov`), descriptions match by word. Inside a submenu the same search covers everything below it.
- **Answers first.** Computed results appear as answer rows with a preview; matches next; Google and the assistants last.
- **Files and folders** under `~` join the results from two characters on, found by `fd` (hidden and gitignored entries are skipped unless you turn hidden entries on). The words of the query are literal substrings: the last one has to be in the name, earlier ones anywhere in the path, so `docs readme` finds README files under a docs folder. `↵` opens a file with its default app and a folder in your file manager; `Ctrl+↵` opens a terminal there. At most ten mix into the root (Settings → Files); the Files screen shows up to sixty.
- **Hotkeys you have not learned yet.** Every Omarchy keybinding is a row at the root, named by what it does, with the keys next to it: `flcrn` shows **Full screen** with `Super + F`, `super f` finds the same bind by its keys, `screenshot` finds the one that runs `omarchy-capture-screenshot`. `↵` runs the bind exactly as pressing it would (the list and the dispatch both come from `omarchy-menu-keybindings`, the script behind `Super+K`); the keys shown are the suggestion for next time, and frecency lifts what you actually use. The **Hotkeys** screen lists all of them in the `Super+K` order. Binds Omarchy cannot run from a menu (Lua closures such as **Close window**) are shown greyed so the keys can still be learned. At most ten mix into the root (Settings → Hotkeys).
- **Assistant hand-offs** open the target with your prompt already in its composer, nothing goes through the clipboard: Claude desktop via `claude://claude.ai/new?q=…`, the Codex desktop app via `codex://threads/new?prompt=…`, or the browser (`claude.ai/new?q=`, `chatgpt.com/?prompt=`; `?q=` sends immediately when **Send immediately in the browser** is on). CLI mode opens a terminal with `claude` or `codex` and the prompt as a literal argument.
- **Keys**: `↑`/`↓` or `Ctrl+P`/`Ctrl+N` move, `PageUp`/`PageDown` jump six rows, `↵` or `→` activates, `Ctrl+↵` runs a row's alternate action, `Esc` closes, `Ctrl+U` clears the query, `←`/`Backspace` on an empty query goes back, `Del` on an application offers to uninstall it, `Ctrl+,` opens Settings, `Ctrl+K` opens the selected provider's settings.
- **Destructive Omarchy actions** (shutdown, reboot, logout, hibernate, removals, config resets) ask for confirmation; turn this off in Settings → Omarchy.
- **Frecency.** Selections of apps, Omarchy commands and hotkeys earn a bounded bonus (14-day half-life). State lives in `~/.local/state/keystroke/usage.json` as hashed ids only.
- **Every `omarchy menu` route works as before**: submenus open scoped (`omarchy menu toggle system`), leaf aliases run immediately (`omarchy menu summon reminder-set`), `apps` opens the Applications provider. Pickers honor `width`/`maxHeight`; a new picker request cancels a pending one.

## Extensions

Keystroke is extension-first: anyone can publish a provider as an ordinary Omarchy plugin, and Keystroke installs, updates, enables and removes it from inside the palette.

<p align="center"><img src="site/assets/screenshots/extension-detail.png" alt="One extension's screen" width="720"></p>

Type `ext` and open **Extensions**:

- **Installed** lists every extension, on or off, with its version. `↵` opens its screen: **Enabled** (Keystroke's switch, which also loads the plugin into the shell when needed), **Loaded in omarchy-shell** (Omarchy's switch), **Settings**, **Check for updates** / **Update now**, **Open repository**, **Remove**. `Ctrl+↵` on the list row toggles it.
- **Discover** merges two sources: the curated [Keystroke index](extensions/index.json) and the [Omarchy plugin marketplace](https://plugins.omarchy.org), where an extension is recognised by naming Keystroke in its id, name, description or tags. Both are cached for an hour under `~/.cache/keystroke`; **Refresh catalog** fetches them again.
- **Any git URL** or `owner/repo` shorthand typed on the Extensions screen offers an install row.
- **Check for updates** fetches every git-managed extension without merging; **Update all** appears when something is behind.

Every install and removal asks for confirmation and states that the code runs unsandboxed in your shell. The work is done by Omarchy's own scripts (`omarchy plugin add --yes --enable`, `omarchy plugin update --yes`, `omarchy plugin remove --yes`), which refuse git transport helpers, validate the manifest and reject symlinks, so the palette and the CLI never disagree. Because the shell reloads all plugins after an install or removal, the palette closes for a moment and a notification confirms the outcome. Extensions installed from the palette are enabled at once; extensions installed with `omarchy plugin add` start off until you turn them on.

**Write one.** An extension is an Omarchy plugin of kind `service` whose manifest carries `"x-keystroke": { "apiVersion": 1 }` and whose `Service.qml` exposes a `provider` object with `query(ctx)`. The published reference is [keystroke-timer](https://github.com/evindor/keystroke-timer) (a GitHub template: countdown timers with settings, a scoped screen, a service that outlives the palette and unit tests); the minimal one is [examples/keystroke-hello](examples/keystroke-hello/). The contract is [docs/providers.md](docs/providers.md); the step-by-step guide for people and coding agents, including publishing to the marketplace and to the index, is [AGENTS.md](AGENTS.md).

<p align="center"><img src="site/assets/screenshots/timer.png" alt="The Timer extension answering timer 25m focus" width="720"></p>

## Voice

Keystroke dictates through [voxtype](https://voxtype.io), the dictation daemon Omarchy installs from Install › AI › Dictation. Keystroke Settings › Voice shows **Voxtype voice command integration**, on by default as soon as `voxtype` is on the PATH, and offers Omarchy's installer when it is not. `bin/keystroke voice-setup` (no root) installs a voxtype build with live words and whole-request revision, compiled from Keystroke's fork of voxtype at one fixed commit (`FORK_COMMIT` in `helpers/voice-setup.sh`, checked out detached and verified before anything is built), never from a moving branch.

Two ways in, both while the palette is open:

- **Tap the hotkey again.** The second tap of `Super+Space` starts listening instead of closing the palette; a third tap stops. Set **Second tap of the hotkey** to *Close* to keep the stock toggle.
- **Hold the hotkey.** Keep `Super+Space` down: after Hyprland's key-repeat delay the palette starts listening, and releasing the chord stops it. This needs a long-press bind and a release bind on the same key; Settings › Voice › **Hold-to-talk bindings** writes them into `~/.config/hypr/bindings.lua` inside a marked block (confirmation first, then `hyprctl reload`). The block is plain Lua you can also paste yourself:

  ```lua
  -- >>> keystroke voice: hold the palette hotkey to dictate (written by Keystroke Settings › Voice)
  o.bind("SUPER + SPACE", nil, "omarchy-shell shell call omarchy.menu voiceHold '{}'", { long_press = true })
  o.bind("SUPER + SPACE", nil, "omarchy-shell shell call omarchy.menu voiceRelease '{}'", { release = true })
  -- <<< keystroke voice
  ```

While listening, live words fill the query field and a small waveform sits to the right; matches update as you speak. Releasing the hotkey, tapping it again, or pressing `↵` finishes the recording, and a fresh `↵` after transcription runs the visible selection. Typing or navigating cancels the recording. Voxtype's overlay stays hidden, the transcript never goes through the clipboard or a virtual keyboard, and temporary transcript files are removed afterwards. Trailing punctuation, a leading launcher verb ("open", "go to") and filler are dropped before matching, so "Launch Chrome." is searched as `Chrome`.

**Copy to Clipboard** appears under **Continue with** after any spoken or typed query: `↵` copies the original text and closes, `Ctrl+↵` copies, closes and pastes into the previous window. The separate **Dictate to Clipboard** launcher (`bin/keystroke dictate`) starts a prose-only recording with the same keys.

Model, language and VAD are voxtype's settings (`voxtype configure`). Whisper on the GPU is what makes live words keep up: `voxtype setup gpu --enable` (Vulkan). With the daemon stopped the palette says so instead of listening.

## Codex inside Keystroke

<p align="center"><img src="site/assets/screenshots/codex.png" alt="The Codex screen" width="720"></p>

Type or speak, then select **Ask Codex here**, or type `? ` before your question. Answers stream inside the palette. `↵` sends a follow-up, `Shift+↵` adds a line, your voice hotkey fills the composer, **Stop** interrupts, `Esc` closes. **Codex → Recent questions** continues a conversation; **Continue in Codex** (`Ctrl+↵`) hands it to your desktop app or CLI; **Open task in Codex** opens a new request there. Settings → Codex selects the model, Fast/Standard processing, destination and an optional working folder; the default is GPT-5.6 Luna using your existing `codex login`. Keystroke owns one local `codex app-server` process, shuts it down after ten idle minutes, never reads credentials, and stores only its recent-question index and drafts. This integration pins Codex CLI 0.153.2. Details and limits: [docs/codex-integration-verification.md](docs/codex-integration-verification.md).

## Settings

<p align="center"><img src="site/assets/screenshots/settings.png" alt="Keystroke Settings" width="720"></p>

One file, hand-editable and hot-reloaded: `~/.config/omarchy/keystroke.json` (see [keystroke.example.json](keystroke.example.json)). Settings screens are generated from each provider's schema; writes are atomic, preserve unknown fields, and are refused while the file fails to parse. Every screen, setting and choice is searchable from the palette root through its breadcrumb. Appearance: density (compact/comfortable), accent (theme accent or ember/violet/mint), previews on/off. Colors, fonts, radius and spacing follow the active Omarchy theme.

## Verify

```sh
bin/keystroke validate     # omarchy plugin validate
bin/keystroke test         # qmltestrunner unit tests, Quickshell integration checks, qmllint
```

[docs/verification.md](docs/verification.md) records what was run on the reference machine; [docs/architecture.md](docs/architecture.md) describes the design; [AGENTS.md](AGENTS.md) is the contributor guide.

## License

MIT, see [LICENSE](LICENSE). Omarchy's MIT-licensed menu model is vendored in [omarchy/MenuModel.js](omarchy/MenuModel.js).
