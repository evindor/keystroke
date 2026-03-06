# Keystroke — Design Specification

A Raycast-like launcher for Hyprland/Omarchy that replaces hotkey memorization with fuzzy, frecency-ranked command search.

---

## Core Concept

User presses ALT+SPACE (configurable). A centered overlay appears with a text input. Below it: the most recently/frequently used commands. As the user types, results fuzzy-filter in real time. Select one → it executes. Over time, the system learns the user's personal mnemonics: "VS" → "Toggle window split", "br" → "Browser", etc.

---

## Data Source

### Hyprland Bindings (first module)

Fetch all bindings from `hyprctl binds -j` on launch. Returns 188 entries with:

```json
{
  "modmask": 64,
  "key": "W",
  "has_description": true,
  "description": "Close window",
  "dispatcher": "killactive",
  "arg": "",
  "mouse": false,
  "release": false
}
```

**Modmask is a bitmask:**
- `4` = CTRL
- `8` = ALT
- `64` = SUPER
- `1` = SHIFT
- Combined: `65` = SUPER+SHIFT, `68` = SUPER+CTRL, `72` = SUPER+ALT, etc.

We render this as human-readable: `SUPER + W`, `SUPER + SHIFT + F`, etc.

For entries without descriptions (`has_description: false`), we auto-generate a label from `dispatcher + arg` (e.g., `exec ~/.config/hypr/scripts/foo.sh` → `foo.sh`). Users can later assign custom descriptions via the app.

### Future Modules

The architecture is modular. The Hyprland dispatcher is the first "provider." Future providers could include:
- Application launcher (desktop entries)
- System commands (shutdown, reboot, lock)
- Custom user commands
- Clipboard history
- File search

Each provider implements a trait that returns a list of `Command` items.

---

## Architecture

```
┌─────────────────────────────────────────┐
│                  main.rs                │
│  App init, layer shell, signal handler  │
│  PID file, CSS loading                  │
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
│  mod.rs     — Provider trait            │
│  hyprland.rs — hyprctl binds provider   │
├─────────────────────────────────────────┤
│               store.rs                  │
│  JSON persistence for frecency data     │
│  ~/.local/share/keystroke/history.json  │
├─────────────────────────────────────────┤
│               config.rs                 │
│  ~/.config/keystroke/config.toml        │
│  Visible results count, appearance      │
├─────────────────────────────────────────┤
│               theme.rs                  │
│  Parse Omarchy waybar.css theme colors  │
└─────────────────────────────────────────┘
```

### Provider Trait

```rust
trait Provider {
    fn id(&self) -> &str;                    // "hyprland"
    fn commands(&self) -> Vec<Command>;      // fetch/refresh command list
    fn execute(&self, command: &Command);    // run the selected command
}

struct Command {
    id: String,           // unique: "hyprland:killactive"
    label: String,        // "Close window"
    description: String,  // secondary text, optional
    keywords: Vec<String>,// extra searchable terms
    hotkey: Option<String>,// "SUPER + W" (display only)
    provider: String,     // "hyprland"
    data: String,         // provider-specific payload (dispatcher + arg)
}
```

### Hyprland Provider

- On `commands()`: runs `hyprctl binds -j`, parses JSON, builds `Command` list
- On `execute()`: runs `hyprctl dispatch <dispatcher> <arg>`
- Filters out: mouse bindings, media keys (XF86*), release-only bindings
  - Actually — we keep everything. Let the user decide what's useful. Media keys are valid commands ("Volume up", "Next track")
- Refreshes on every show (bindings might change after hyprctl reload)

---

## Ranking Algorithm

### Fuzzy Matching: `nucleo-matcher`

Smith-Waterman with affine gaps. Same scoring constants as FZF:
- +16 per matched char
- +8–10 for boundary matches (after space, delimiter, camelCase)
- +4 for consecutive matches
- -3 gap start, -1 gap extension

We match against: `label` (primary), `keywords`, and `hotkey`.

### Frecency: Exponential Decay (inspired by `fre`)

```rust
struct FrecencyEntry {
    score: f64,           // accumulated score
    reference_time: u64,  // epoch when score was last updated
}
```

On access:
```
current_score = stored_score / 2^((now - reference_time) / half_life)
new_score = current_score + 1.0
```

Half-life: **7 days** (604800 seconds). An item used once a week maintains steady score. Items not used for a month fade to ~6% of peak.

### Combined Ranking

**When query is empty** (just opened): pure frecency order. Show the user's most-used commands.

**When query has text:**
```
final_score = fuzzy_score × (1.0 + 0.2 × ln(frecency + 1))
```

- Fuzzy score dominates (it's the multiplied base)
- Frecency provides a mild boost — enough to break ties and surface learned mnemonics
- Weight `0.2` is tunable in config

### Per-Query Frecency

This is the key insight for mnemonic learning. We store frecency **per (query → command) pair**, not just per command globally.

```json
{
  "global": {
    "hyprland:killactive": { "score": 15.0, "ref_time": 1709740800 }
  },
  "queries": {
    "vs": {
      "hyprland:togglesplit": { "score": 42.0, "ref_time": 1709740800 }
    },
    "br": {
      "hyprland:exec:omarchy-launch-browser": { "score": 30.0, "ref_time": 1709740800 }
    }
  }
}
```

When ranking with query "vs":
1. Get fuzzy scores for all commands against "vs"
2. Look up per-query frecency for "vs" → boost matching commands
3. Also fold in global frecency with lower weight

This means typing "VS" eventually guarantees "Toggle window split" is #1, even though "VS" is a terrible fuzzy match for those words — the per-query frecency overwhelms it.

---

## UI Design

### Window

- **Layer**: Overlay (above everything)
- **Position**: Centered on active monitor
- **Size**: 680px wide, height adapts to results (max 10 visible by default)
- **Keyboard mode**: Exclusive (captures all input)
- **Namespace**: `keystroke`

### Layout

```
┌──────────────────────────────────────────────┐
│  ┌────────────────────────────────────────┐   │
│  │  🔍  Type a command...                │   │  ← input field
│  └────────────────────────────────────────┘   │
│                                              │
│  ┌────────────────────────────────────────┐   │
│  │ ▸ Close window              SUPER + W  │   │  ← selected (highlighted)
│  ├────────────────────────────────────────┤   │
│  │   Toggle floating/tiling    SUPER + T  │   │
│  ├────────────────────────────────────────┤   │
│  │   Full screen               SUPER + F  │   │
│  ├────────────────────────────────────────┤   │
│  │   Terminal              SUPER + Return  │   │
│  ├────────────────────────────────────────┤   │
│  │   Browser         SUPER + SHIFT + B    │   │
│  ├────────────────────────────────────────┤   │
│  │   ...                                  │   │
│  └────────────────────────────────────────┘   │
│                                              │
└──────────────────────────────────────────────┘
```

### Visual Style (Raycast-inspired)

- **Background**: semi-transparent dark with blur (compositor-side blur via Hyprland layer rules)
- **Corners**: generous border-radius (16px) (configurable)
- **Input**: large font (18-20px), prominent, with subtle border-bottom separator
- **Results**: clean rows, ~44px height each
  - Left: command label (primary text, white/foreground)
  - Right: hotkey in faded secondary color, monospace
  - Selected row: subtle highlight background
- **Typography**: system sans-serif, clean weights
- **Colors**: pulled from Omarchy theme (`waybar.css`) for consistency
- **Transitions**: no heavy animation — instant show/hide (speed is king for a launcher)
- **Drop shadow**: subtle box-shadow for floating feel

### Hyprland Layer Rules (for blur)

```conf
layerrule = blur, keystroke
layerrule = ignorealpha 0.3, keystroke
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

On execute: record the (query, command) pair in frecency store, then dismiss.

---

## Configuration

File: `~/.config/keystroke/config.toml`

```toml
[appearance]
max_visible_results = 10    # how many results to show
width = 680                 # window width in pixels
border_radius = 16          # corner radius in pixels

[scoring]
frecency_weight = 0.2      # how much frecency boosts fuzzy score
half_life_days = 7          # frecency decay half-life

[providers]
hyprland = true             # enable hyprland bindings provider

[aliases]
vs = "hyprland:togglesplit"
br = "hyprland:exec:omarchy-launch-browser"
term = "hyprland:exec:uwsm-app -- xdg-terminal-exec"
```

Sane defaults for everything. Config file is optional — app works with zero configuration. Aliases are explicit mnemonics — typing "vs" will always show "Toggle window split" at #1 regardless of frecency.

---

## Lifecycle

1. **Start**: app launches (autostart or manual), loads config, creates hidden GTK window
2. **Activate** (ALT+SPACE via Hyprland bind):
   - Show overlay
   - Fetch `hyprctl binds -j` (fresh every time)
   - Load frecency data from JSON
   - Focus input field
   - Display top frecency commands (empty query state)
3. **Search**: user types → nucleo scores all commands → combine with frecency → display ranked results
4. **Execute**: user hits Enter →
   - Provider executes the command (`hyprctl dispatch ...`)
   - Frecency store updated with (query, command) and (global, command)
   - Overlay hides
5. **Dismiss**: Escape → hide, no side effects

### Show/Hide Mechanism: GApplication Daemon (same pattern as Walker)

Following the established Omarchy pattern, keystroke runs as a **GTK GApplication daemon**:

1. **Daemon mode**: `keystroke --gapplication-service` runs persistently, creates the hidden overlay window
2. **Activation**: running `keystroke` again (without `--gapplication-service`) acts as a **client** — GTK's GApplication detects the running instance via D-Bus and sends an `activate` signal to the daemon, which toggles the overlay
3. **No PID files, no signals** — D-Bus handles all IPC

```conf
# In hyprland config:
bindd = ALT, SPACE, Keystroke launcher, exec, keystroke
```

Each press runs the binary. If the daemon is running, it receives an `activate` signal and toggles visibility. If not running, the binary becomes the daemon and shows immediately.

### Autostart (systemd)

XDG autostart desktop entry at `~/.config/autostart/keystroke.desktop`:

```ini
[Desktop Entry]
Name=Keystroke
Exec=keystroke --gapplication-service
Type=Application
X-GNOME-Autostart-enabled=true
```

systemd picks this up via `systemd-xdg-autostart-generator`. Add a restart drop-in for resilience:

```ini
# ~/.config/systemd/user/app-keystroke@autostart.service.d/restart.conf
[Service]
Restart=always
RestartSec=2
```

---

## Data Storage

### Frecency: `~/.local/share/keystroke/history.json`

```json
{
  "version": 1,
  "global": {
    "<command_id>": { "score": 15.0, "ref_time": 1709740800 }
  },
  "queries": {
    "<normalized_query>": {
      "<command_id>": { "score": 42.0, "ref_time": 1709740800 }
    }
  }
}
```

### User Descriptions: `~/.local/share/keystroke/descriptions.json`

For overriding/adding descriptions to bindings that lack them:

```json
{
  "hyprland:exec:~/.config/hypr/scripts/window-list-show.sh": "Window list overlay"
}
```

---

## Crate Dependencies

```toml
[dependencies]
gtk4 = "0.10"
gtk4-layer-shell = { version = "0.7", features = ["v1_3"] }
glib = "0.21"
gio = "0.21"
gdk4 = "0.10"
nucleo-matcher = "0.3"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
toml = "0.8"
libc = "0.2"

[profile.release]
strip = true
lto = true
```

---

## Open Questions for Later

1. **Multi-word queries**: "close win" should match "Close window". Nucleo handles this natively with space-separated pattern tokens.
2. **Provider priority**: when multiple providers return similar commands, how to rank across providers? (solve when we add provider #2)
3. **Explicit aliases/mnemonics UI**: how does the user set "vs = toggle split" from within the app? (v2 feature — maybe Ctrl+A on a selected result to "alias" it)
4. **Submap support**: Hyprland submaps create nested binding contexts. Parse `submap` field from binds JSON if non-empty. (handle when needed)
