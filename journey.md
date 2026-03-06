# Keystroke — Development Journey

## Build Plan

1. Project scaffolding (Cargo.toml, directories)
2. Core types (Command struct, Provider trait)
3. Independent modules in parallel: config, store, theme, hyprland provider
4. Engine (fuzzy + frecency ranking)
5. UI (GTK overlay, input, result list)
6. Main (GApplication daemon lifecycle)
7. CSS styling (Raycast-inspired)
8. Build, test, iterate

## Progress

### Milestone 1: Project Scaffolding — DONE
- Cargo.toml with all deps (gtk4 0.10, gtk4-layer-shell 0.7, nucleo-matcher 0.3)
- src/ directory with providers/ subdirectory

### Milestone 2: Core Modules — DONE
All modules built and tested (24 tests passing):

- **providers/mod.rs** — Command struct, Provider trait
- **providers/hyprland.rs** — fetches `hyprctl binds -j`, decodes modmask bitmask, auto-generates labels from binary names, supports custom descriptions
- **config.rs** — TOML config with sane defaults, aliases support
- **store.rs** — frecency with exponential decay (fre-inspired), per-query + global tracking
- **theme.rs** — parses Omarchy waybar.css colors, generates Raycast-style CSS
- **engine.rs** — combines nucleo fuzzy matching with frecency boosting, alias pinning
- **ui.rs** — GTK4 layer shell overlay, input + result list, keyboard navigation (arrows, Ctrl+J/K, Ctrl+N/P)
- **main.rs** — GApplication daemon pattern, toggle on activate, full lifecycle

### Milestone 3: First Successful Build — DONE
- Release build: 1.1MB binary (strip + lto)
- 24 unit tests passing
- Zero warnings
- Successful smoke test (launches, shows overlay, no crashes)

### Key Decisions Made
- **GApplication daemon** (not SIGUSR1) — matches Walker/Omarchy pattern
- **gtk4-layer-shell** uses LayerShell trait methods, not free functions
- Widget sizing (width, height) set programmatically, not via CSS (GTK4 doesn't support CSS min-width/max-width)
- `CssProvider::load_from_data()` not `load_from_string()` (GTK4 0.10)
- `connect_command_line` returns `glib::ExitCode`, use `0.into()`
- Per-query frecency stored as (normalized_query, command_id) → score pairs

### Current State
- App launches and shows overlay with all ~188 Hyprland bindings
- Fuzzy search works
- Frecency learning works
- Keyboard navigation works
- Need to set up Hyprland binding + autostart for real testing

### File Structure
```
Cargo.toml
DESIGN.md
journey.md
knowledge.md
src/
  main.rs        — GApplication daemon, lifecycle, callbacks
  ui.rs          — Layer shell overlay, input, results, navigation
  engine.rs      — Fuzzy + frecency ranking engine
  config.rs      — TOML config parsing
  store.rs       — Frecency persistence (JSON)
  theme.rs       — Omarchy theme colors, CSS generation
  providers/
    mod.rs       — Command struct, Provider trait
    hyprland.rs  — Hyprland keybinding provider
```
