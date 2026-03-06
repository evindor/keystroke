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

### Milestone 4: Calculator Provider — DONE
- Built-in recursive descent expression parser (no external deps)
- Supports: +, -, *, /, %, ^, **, parentheses, unary minus, decimals
- Execute = copy result to clipboard via wl-copy
- Extended Provider trait with `query_commands()` for dynamic results
- 12 calculator tests

### Milestone 5: Desktop Apps Provider — DONE
- Scans ~/.local/share/applications/ and /usr/share/applications/
- Custom .desktop file parser (no external deps)
- User-local entries override system ones (dedup by filename)
- Filters: Hidden, NoDisplay, TryExec check
- Strips field codes (%u, %U, %f, %F, etc.) from Exec
- Terminal=true apps wrapped with xdg-terminal-exec
- Launch via uwsm-app (Omarchy pattern) — detects if already uwsm-wrapped
- Icons: theme names and absolute paths both supported
- Added icon column to UI (gtk4::Image from icon name or file path)
- 5 apps tests, 41 total

### Key Decisions Made (continued)
- EventControllerKey must use PropagationPhase::Capture to intercept Enter before GTK Entry
- No external deps for expression eval or desktop file parsing — roll our own
- Icon rendering: absolute paths → Image::from_file, theme names → Image::from_icon_name
- Command struct has optional `icon` field
- Apps launched via sh -c to handle complex Exec strings with arguments

### Current State
- 3 providers: Hyprland bindings, Desktop apps, Calculator
- ~188 Hyprland bindings + ~80 desktop apps visible
- Icons display for desktop apps
- Fuzzy search across all providers
- Frecency learning works
- Calculator results appear at top when typing math expressions
- Hyprland binding (ALT+SPACE) active

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
    mod.rs       — Command struct, Provider trait (with query_commands)
    hyprland.rs  — Hyprland keybinding provider
    apps.rs      — Desktop application launcher (XDG .desktop files)
    calculator.rs — Expression evaluator (recursive descent)
```
