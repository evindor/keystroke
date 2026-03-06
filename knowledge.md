# Keystroke Launcher — Knowledge Base

Lessons learned building a Raycast-like launcher for Hyprland/Omarchy in Rust + GTK4.

## GTK4 Layer Shell (Wayland overlays)

```rust
use gtk4_layer_shell::{Edge, KeyboardMode, Layer, LayerShell};

window.init_layer_shell();
window.set_layer(Layer::Overlay);
window.set_namespace(Some("my-app"));          // Option<&str>!
window.set_keyboard_mode(KeyboardMode::Exclusive); // captures all input
window.set_exclusive_zone(-1);                 // float over content
```

**Use trait methods** (`LayerShell` on `ApplicationWindow`), NOT free functions (`gtk4_layer_shell::init_for_window` etc.) — the free functions don't exist in 0.7.

### Centering an overlay

Anchor nothing (default) → window centers on screen, sizes to content.
Set width via `container.set_width_request(680)` not CSS — GTK4 doesn't support CSS `min-width`/`max-width`.

### Layer rules for blur (in Hyprland config)

```conf
layerrule = blur, my-namespace
layerrule = ignorealpha 0.3, my-namespace
```

### Layer surfaces in hyprctl

Layer shell windows don't appear in `hyprctl clients -j`. Query them with:
```bash
hyprctl layers -j | jq '.. | objects | select(.namespace? == "keystroke")'
```

---

## GTK4 API quirks (0.10)

### CssProvider
- `provider.load_from_data(&css_string)` — NOT `load_from_string` (doesn't exist in 0.10)

### CSS limitations
GTK4 CSS is NOT web CSS. These don't work:
- `min-width`, `max-width`, `min-height`, `max-height` → set programmatically on widgets
- `box-shadow` with blur radius → only simple offsets work
- `transition` → limited support, may cause warnings

Set sizing via widget methods: `widget.set_width_request()`, `widget.set_height_request()`,
`scrolled_window.set_max_content_height()`.

### EventControllerKey and Entry widgets

**Critical:** GTK4's `Entry` widget consumes Return/Enter in the bubble phase (its built-in `activate` signal). To intercept Enter before the Entry sees it:

```rust
let key_controller = gtk4::EventControllerKey::new();
key_controller.set_propagation_phase(gtk4::PropagationPhase::Capture);
window.add_controller(key_controller);
```

This also ensures Escape, arrow keys, and Ctrl+J/K/N/P are captured before any child widget handles them.

### Icon rendering

Two cases:
```rust
// Theme icon name (e.g. "firefox", "signal-desktop")
let image = gtk4::Image::from_icon_name("firefox");
image.set_pixel_size(24);

// Absolute path (e.g. Omarchy webapp icons)
let image = gtk4::Image::from_file("/path/to/icon.png");
image.set_pixel_size(24);
```

Detect which: if the string starts with `/` or contains a file extension → absolute path. Otherwise → theme icon name.

### GApplication ExitCode

`connect_command_line` callback must return `glib::ExitCode`, not an integer:
```rust
app.connect_command_line(|app, _| {
    app.activate();
    0.into()  // NOT just `0`
});
```

### Iterating Box children

GTK4 `Box` has no `.children()` method. Walk with:
```rust
let mut child = container.first_child();
while let Some(c) = child {
    // process c
    child = c.next_sibling();
}
```

---

## GApplication Daemon Pattern

The standard Omarchy pattern for overlay apps (used by Walker, Keystroke):

1. **Daemon mode**: `app --gapplication-service` runs persistently
2. **Toggle**: running `app` again (no flag) sends D-Bus activate to the daemon
3. **No PID files, no signals** — GTK GApplication handles IPC via D-Bus

```rust
let app = gtk4::Application::new(
    Some("com.my.app"),
    gio::ApplicationFlags::HANDLES_COMMAND_LINE,
);

// REQUIRED: without this, second invocations just exit
app.connect_command_line(|app, _| {
    app.activate();
    0.into()
});

app.connect_activate(move |app| {
    if !initialized { /* build UI */ }
    else { /* toggle visibility */ }
});
```

### Hyprland binding
```conf
bindd = ALT, SPACE, My launcher, exec, my-app
```

### Autostart via systemd

XDG autostart at `~/.config/autostart/my-app.desktop`:
```ini
[Desktop Entry]
Name=My App
Exec=my-app --gapplication-service
Type=Application
```

Resilience drop-in at `~/.config/systemd/user/app-my-app@autostart.service.d/restart.conf`:
```ini
[Service]
Restart=always
RestartSec=2
```

---

## Hyprland Keybinding Data

### hyprctl binds -j

Returns all active bindings as JSON. Key fields:

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

### Modmask bitmask

| Bit | Modifier |
|-----|----------|
| 1   | SHIFT    |
| 4   | CTRL     |
| 8   | ALT      |
| 64  | SUPER    |

Combined: 65 = SUPER+SHIFT, 68 = SUPER+CTRL, 72 = SUPER+ALT, 73 = SUPER+ALT+SHIFT, 76 = SUPER+CTRL+ALT.

### bindd format (in config files)

```conf
bindd = MODIFIERS, KEY, Description, dispatcher, [args]
```

Variants: `bindeld` (repeat + release + description), `bindld` (release + description), `bindmd` (mouse + description).

### Executing dispatchers

```rust
Command::new("hyprctl").args(["dispatch", "killactive"]).spawn();
Command::new("hyprctl").args(["dispatch", "exec", "firefox"]).spawn();
```

---

## Omarchy Integration

### Theme colors

Read from `~/.config/omarchy/current/theme/waybar.css`:
```css
@define-color foreground #d3c6aa;
@define-color background #2d353b;
```

Parse with simple string splitting — no regex needed. Re-parse on every show so theme changes take effect without restart.

### Launching apps: uwsm-app

Omarchy runs graphical apps through `uwsm-app` for proper systemd scope tracking:

```rust
// Standard app:
Command::new("uwsm-app").args(["--", "firefox"]).spawn();

// TUI app (Terminal=true in .desktop):
Command::new("uwsm-app").args(["--", "xdg-terminal-exec", "-e", "btop"]).spawn();
```

**Don't double-wrap**: if the Exec string already contains `uwsm-app` or `uwsm app` (e.g. omarchy launch scripts), run it directly via `sh -c`.

### Desktop entry discovery

Scan in order (user-local overrides system):
1. `~/.local/share/applications/*.desktop`
2. `/usr/share/applications/*.desktop`

Omarchy hides unwanted system apps by placing `Hidden=true` stubs in `~/.local/share/applications/`.

Omarchy webapps use absolute icon paths: `Icon=/home/user/.local/share/applications/icons/Claude.png`

### Desktop entry field codes

Strip these from Exec before launching: `%u %U %f %F %i %c %k %d %D %n %N %v %m`. `%%` becomes literal `%`.

---

## Fuzzy Matching: nucleo-matcher

Same Smith-Waterman algorithm as fzf. Scoring: +16 per match, +8–10 boundary bonus, +4 consecutive, -3 gap start, -1 gap extension.

```rust
use nucleo_matcher::{Config, Matcher, Utf32Str};
use nucleo_matcher::pattern::{CaseMatching, Normalization, Pattern};

let mut matcher = Matcher::new(Config::DEFAULT);
let pattern = Pattern::parse("query", CaseMatching::Ignore, Normalization::Smart);

let mut buf = Vec::new();
let haystack = Utf32Str::new("haystack text", &mut buf);
let score: Option<u32> = pattern.score(haystack, &mut matcher);
```

**buf must be cleared between calls** — `Utf32Str::new` writes into it.

Space-separated patterns match independently: `"close win"` matches `"Close window"`.

---

## Frecency: Exponential Decay

Inspired by `fre` (not zoxide's step function). Smooth continuous decay.

```
stored: { score: f64, ref_time: u64 }
decayed_score = score / 2^((now - ref_time) / half_life)
on_bump: new_score = decayed_score + 1.0, ref_time = now
```

Default half-life: 7 days (604800 seconds). Used once/week → steady score. Unused for a month → ~6% of peak.

### Per-query frecency (key insight)

Store frecency per `(query, command_id)` pair, not just per command. This enables mnemonic learning:
- User types "vs", picks "Toggle split" → stored under query "vs"
- After 10 uses, typing "vs" guarantees "Toggle split" at #1
- Even though "vs" is a terrible fuzzy match for "Toggle split"

### Combined ranking formula

```
final_score = fuzzy_score × (1.0 + frecency_weight × ln(combined_frecency + 1))
```

Where `combined_frecency = query_frecency × 2 + global_frecency`. Default `frecency_weight = 0.2`.

Empty query = pure frecency order (most-used commands first).

---

## Provider Architecture

```rust
pub trait Provider {
    fn id(&self) -> &str;
    fn commands(&self) -> Vec<Command>;           // static, called once on show
    fn execute(&self, command: &Command);
    fn query_commands(&self, _query: &str) -> Vec<Command> { vec![] }  // dynamic per-keystroke
}
```

`query_commands()` is for dynamic providers (calculator). Results are prepended at max score.

### Current providers

| Provider | Static commands | Dynamic | Execute action |
|----------|----------------|---------|----------------|
| Hyprland | ~188 bindings | No | `hyprctl dispatch` |
| Apps | ~80 desktop entries | No | `uwsm-app --` or `sh -c` |
| Calculator | None | Yes (on math input) | `wl-copy` to clipboard |

### Config (all optional, sane defaults)

```toml
[appearance]
max_visible_results = 10
width = 680
border_radius = 16

[scoring]
frecency_weight = 0.2
half_life_days = 7

[aliases]
vs = "hyprland:togglesplit"
br = "hyprland:exec:omarchy-launch-browser"
```

---

## Design Principles (established)

1. **No external deps when a simple solution exists** — wrote our own expression parser (recursive descent) and .desktop file parser rather than pulling crates
2. **Modular providers** — new functionality = new provider file implementing the trait
3. **Re-parse everything on show** — theme, config, bindings, desktop entries refreshed each activation, no stale state
4. **Per-query frecency** — the differentiator that enables mnemonic learning
5. **Raycast-like UX** — centered overlay, input on top, results below, keyboard-only navigation
