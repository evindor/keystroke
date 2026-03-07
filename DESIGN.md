# Keystroke — Design Specification

A Raycast-like launcher for Hyprland/Omarchy that replaces hotkey memorization with fuzzy, frecency-ranked command search.

---

## Core Concept

User presses ALT+SPACE (configurable). A centered overlay appears with a text input. Below it: the most recently/frequently used commands. As the user types, results fuzzy-filter in real time. Select one → it executes. Over time, the system learns the user's personal mnemonics: "mwl" → "Move window left", "cr" → "Resize column", etc.

---

## Data Source: Dispatch Catalog

Keystroke uses a **curated dispatch catalog** as its primary data source. The catalog lives at `~/.local/share/keystroke/catalog.toml` and contains ~70 human-authored dispatch entries organized by category.

**Key insight:** Dispatches are the primitive, keybindings are just one (limited) trigger mechanism. Hyprland has 60+ core dispatchers, 20+ layoutmsg sub-commands, and plugin dispatchers — most of which will never have keybindings. Keystroke surfaces the entire dispatch API as a command palette.

### Parameter Tiers

**Tier 1 — Finite sets (pre-expanded):** Directions, workspace numbers, on/off states get separate catalog entries. Each is a distinct action with mnemonic potential.

```toml
[[dispatch]]
dispatcher = "movewindow"
arg = "l"
label = "Move window left"
keywords = ["move", "left", "window"]
```

**Tier 2 — Open-ended (parameterized):** Rename text, resize values, and other arbitrary input use templates with trigger prefixes.

```toml
[[dispatch]]
dispatcher = "renameworkspace"
label = "Rename workspace"
keywords = ["rename", "name", "workspace"]
arg_template = "{active_workspace} {input}"
triggers = ["rw", "rename"]
```

Trigger flow: `rw awesome` → "Rename workspace → 'awesome'" → executes `hyprctl dispatch renameworkspace 1 awesome`

### Layout-Aware Filtering

Entries can be tagged with a `layout` field. Only entries matching the configured layout (or untagged entries) appear. Set `dispatches.layout = "scrolling"` in config to see scrolling-specific layoutmsg commands.

### Other Providers

The architecture is modular via the Provider trait:
- **Apps provider**: Scans desktop entries for application launching
- **Calculator**: Evaluates math expressions inline
- Future: clipboard history, file search, system commands

---

## Architecture

```
┌─────────────────────────────────────────┐
│                  main.rs                │
│  App init, layer shell, signal handler  │
│  Catalog loading, provider construction │
├─────────────────────────────────────────┤
│                  ui.rs                  │
│  GTK overlay window, input field,       │
│  result list, keyboard navigation       │
├─────────────────────────────────────────┤
│                engine.rs                │
│  Fuzzy matching (nucleo-matcher)        │
│  Frecency scoring, result ranking       │
│  Combines provider results              │
├─────────────────────────────────────────┤
│              providers/                 │
│  mod.rs      — Provider trait           │
│  hyprland.rs — Dispatch catalog provider│
│  apps.rs     — Desktop entry provider   │
│  calculator.rs — Math expression eval   │
├─────────────────────────────────────────┤
│               store.rs                  │
│  JSON persistence for frecency data     │
│  ~/.local/share/keystroke/history.json  │
├─────────────────────────────────────────┤
│               config.rs                 │
│  ~/.config/keystroke/config.toml        │
│  Catalog loading from data dir          │
│  CatalogEntry struct, layout filtering  │
├─────────────────────────────────────────┤
│               theme.rs                  │
│  Parse Omarchy waybar.css theme colors  │
└─────────────────────────────────────────┘
```

### Provider Trait

```rust
trait Provider {
    fn id(&self) -> &str;                    // "dispatch", "apps", "calculator"
    fn commands(&self) -> Vec<Command>;      // fetch/refresh command list
    fn execute(&self, command: &Command);    // run the selected command
    fn query_commands(&self, query: &str) -> Vec<Command>; // dynamic commands
}

struct Command {
    id: String,           // unique: "dispatch:killactive", "dispatch:movewindow:l"
    label: String,        // "Close active window", "Move window left"
    keywords: Vec<String>,// extra searchable terms
    hotkey: Option<String>,// display only
    icon: Option<String>, // theme name or path
    provider: String,     // "dispatch"
    data: String,         // execution payload: "killactive", "movewindow l"
}
```

### Dispatch Provider

- On `commands()`: builds Command list from parsed catalog entries (static entries only)
- On `query_commands()`: matches trigger prefixes, resolves templates, returns parameterized commands
- On `execute()`: runs `hyprctl dispatch <dispatcher> <arg>`
- Catalog loaded once per show, filtered by layout

---

## Catalog Format

### Default Catalog: `~/.local/share/keystroke/catalog.toml`

Written on first run from embedded defaults. ~68 entries organized by category:

| Category | Count | Examples |
|---|---|---|
| Window Management | 10 | killactive, togglefloating, pin, centerwindow |
| Window Movement | 8 | movefocus l/r/u/d, movewindow l/r/u/d |
| Window Focus | 4 | cyclenext, focusurgentorlast |
| Workspaces | 12 | workspace 1-10, togglespecialworkspace, renameworkspace |
| Groups | 6 | togglegroup, changegroupactive, lockgroups |
| System | 4 | dpms off/on, exit, forcerendererreload |
| Monitor | 3 | focusmonitor, movecurrentworkspacetomonitor |
| Layout: Scrolling | 10 | colresize, fit, swapcol, promote |
| Layout: Dwindle | 3 | togglesplit, swapsplit, preselect |
| Layout: Master | 8 | swapwithmaster, focusmaster, mfact |

Only ~55 entries visible at once (layout-specific entries filtered by config).

### Entry Fields

```toml
[[dispatch]]
dispatcher = "layoutmsg"        # required: Hyprland dispatcher name
arg = "colresize all 0.5"       # optional: fixed argument
label = "Resize all columns"    # required: human-readable label
keywords = ["resize", "column"] # optional: extra searchable terms
arg_template = "colresize {input}" # optional: parameterized template
triggers = ["cr"]               # optional: trigger prefixes for parameterized
layout = "scrolling"            # optional: only show when this layout is active
```

---

## Ranking Algorithm

### Fuzzy Matching: `nucleo-matcher`

Smith-Waterman with affine gaps. Matches against: `label` (primary), `keywords`, and `hotkey`. Word-boundary bonuses make mnemonic shortcuts work: "mwl" matches **M**ove **W**indow **L**eft.

### Frecency: Exponential Decay

```
current_score = stored_score / 2^((now - reference_time) / half_life)
```

Half-life: **7 days**. Items not used for a month fade to ~6% of peak.

### Combined Ranking

**Empty query:** pure frecency order (most-used commands first).

**With query:**
```
final_score = fuzzy_score × (1.0 + 0.2 × ln(frecency + 1))
```

### Per-Query Frecency (Mnemonic Learning)

Frecency stored per (query → command) pair. Typing "mwl" → selecting "Move window left" → next time "mwl" instantly surfaces it at #1.

---

## Configuration

### Config: `~/.config/keystroke/config.toml`

```toml
[appearance]
max_visible_results = 10
width = 680
border_radius = 16

[scoring]
frecency_weight = 0.2
half_life_days = 7

[providers]
dispatches = true

[dispatches]
layout = "scrolling"

# User-defined dispatches (added to catalog)
[[dispatches.add]]
dispatcher = "exec"
arg = "my-script.sh"
label = "Run my script"
keywords = ["script"]

# Hide default catalog entries by ID
[dispatches.hide]
ids = ["dispatch:exit", "dispatch:dpms:off"]

[aliases]
mwl = "dispatch:movewindow:l"
cr = "dispatch:layoutmsg:colresize"
```

---

## UI Design

### Window

- **Layer**: Overlay (above everything)
- **Position**: Centered on active monitor
- **Size**: 680px wide, height adapts to results (max 10 visible)
- **Keyboard mode**: Exclusive
- **Namespace**: `keystroke`

### Layout

```
┌──────────────────────────────────────────────┐
│  ┌────────────────────────────────────────┐   │
│  │  Type a command...                     │   │  ← input field
│  └────────────────────────────────────────┘   │
│                                              │
│  ┌────────────────────────────────────────┐   │
│  │ ▸ Close active window                  │   │  ← selected
│  ├────────────────────────────────────────┤   │
│  │   Move window left                     │   │
│  ├────────────────────────────────────────┤   │
│  │   Toggle floating                      │   │
│  ├────────────────────────────────────────┤   │
│  │   Switch to workspace 1               │   │
│  ├────────────────────────────────────────┤   │
│  │   Pin window to all workspaces        │   │
│  └────────────────────────────────────────┘   │
│                                              │
└──────────────────────────────────────────────┘
```

### Interaction

| Key | Action |
|---|---|
| Type | Filter results in real-time |
| ↑ / ↓ | Navigate results |
| Enter | Execute selected command, close |
| Escape | Close without executing |
| Ctrl+J / Ctrl+K | Navigate results (vim-style) |
| Ctrl+N / Ctrl+P | Navigate results (emacs-style) |

### Visual Style

- Semi-transparent dark background with compositor blur
- 16px border-radius, drop shadow
- Colors from Omarchy theme (`waybar.css`)
- Clean typography, no heavy animation

### Hyprland Layer Rules

```conf
layerrule = blur, keystroke
layerrule = ignorealpha 0.3, keystroke
```

---

## Lifecycle

1. **Start**: app launches, loads config, creates hidden GTK window
2. **Activate** (ALT+SPACE):
   - Show overlay
   - Load catalog from disk, filter by layout
   - Load frecency data
   - Display top frecency commands (empty query)
3. **Search**: user types → fuzzy match + frecency → ranked results
4. **Execute**: Enter →
   - `hyprctl dispatch <dispatcher> <arg>`
   - Frecency updated with (query, command) pair
   - Overlay hides
5. **Dismiss**: Escape → hide

### GApplication Daemon Pattern

```conf
# Hyprland config:
bindd = ALT, SPACE, Keystroke launcher, exec, keystroke
```

Each press runs the binary. GTK GApplication detects the running instance via D-Bus and toggles visibility.

---

## Data Storage

### Frecency: `~/.local/share/keystroke/history.json`

### Catalog: `~/.local/share/keystroke/catalog.toml`

Written on first run from embedded defaults. User-editable. Overrides via `config.toml` preferred.

---

## Command IDs

Format: `dispatch:{dispatcher}` or `dispatch:{dispatcher}:{arg}`

Examples:
- `dispatch:killactive`
- `dispatch:movewindow:l`
- `dispatch:layoutmsg:colresize all 0.5`
- `dispatch:workspace:3`
