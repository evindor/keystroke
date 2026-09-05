# Keystroke

A Raycast-inspired command palette that **replaces the Omarchy menu**. One native Omarchy `menu` plugin, written in QML/JavaScript, running inside the existing `omarchy-shell` process. No extra runtime, no resident helper, nothing running while it is hidden.

Every capability is a provider: applications, the complete Omarchy menu, calculator, unit and time-zone conversion, colors, emoji, clipboard history, AI/web continuation, and the settings screens themselves. Community providers are ordinary Omarchy plugins.

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
- Computed answers appear first as answer rows with a preview; matches next; Google and the assistants last.
- Assistant hand-offs open the target with your prompt already in its composer, nothing goes through the clipboard: Claude desktop via `claude://claude.ai/new?q=…` (the same link Anthropic's own GNOME search provider uses), the Codex desktop app (which is what the Linux "ChatGPT" package installs) via `codex://threads/new?prompt=…`, or in the browser `claude.ai/new?q=` and `chatgpt.com/?prompt=` (`?q=` sends immediately when **Send immediately in the browser** is on). CLI mode opens a terminal with `claude` or `codex` and the prompt as a literal argument. A missing app or CLI falls back to the browser and the row says so.
- `↑`/`↓` or `Ctrl+P`/`Ctrl+N` move, `PageUp`/`PageDown` jump six rows, `↵` or `→` activates, `Esc` closes immediately, `Ctrl+U` clears the query, `←`/`Backspace` on an empty query goes back, `Del` on an application offers to uninstall it, `Ctrl+,` opens Settings, `Ctrl+K` opens the selected provider's settings.
- Destructive Omarchy actions (shutdown, reboot, logout, hibernate, removals, config resets) ask for confirmation; turn this off in Settings → Omarchy.
- Selections of apps and Omarchy commands earn a bounded frecency bonus (14-day half-life). State lives in `~/.local/state/keystroke/usage.json` as hashed ids only.

Every `omarchy menu` route works as before: submenus open scoped (`omarchy menu toggle system`), leaf aliases run immediately (`omarchy menu summon reminder-set`), `apps` opens the Applications provider. Pickers honor `width`/`maxHeight`; a new picker request cancels a pending one (the stock menu left the first caller waiting).

## Settings

One file, hand-editable and hot-reloaded: `~/.config/omarchy/keystroke.json` (see [keystroke.example.json](keystroke.example.json)). Settings screens are generated from each provider's schema; writes are atomic, preserve unknown fields, and are refused while the file fails to parse. Bundled providers default to enabled, community providers to disabled. Appearance: density (compact/comfortable), accent (theme accent or ember/violet/mint), previews on/off. Colors, fonts, radius and spacing follow the active Omarchy theme.

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
