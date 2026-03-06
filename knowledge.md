# Rust + GTK4 + Wayland (Layer Shell) — Lessons Learned

From building `window-list-overlay` (2026-03-06). Reference project at `~/Work/tries/2026-03-06-scroller/`.

---

## Crate versions (compatible set)

These must be used together — mixing versions causes trait/type mismatches:

```toml
gtk4 = "0.10"
gtk4-layer-shell = { version = "0.7", features = ["v1_3"] }
glib = "0.21"
gio = "0.21"
gdk4 = "0.10"
```

`gtk4-layer-shell 0.7` wraps `wlr-layer-shell` for Wayland compositors (Hyprland, Sway, etc.).

---

## Layer shell basics

```rust
use gtk4_layer_shell::{Edge, KeyboardMode, Layer, LayerShell};

window.init_layer_shell();
window.set_layer(Layer::Overlay);          // Above everything
window.set_namespace(Some("my-app"));      // Wayland namespace (Option<&str>!)
window.set_keyboard_mode(KeyboardMode::None); // Don't steal focus
window.set_exclusive_zone(-1);             // Float over content, don't push
```

### Anchoring controls sizing and position

- Anchor **one edge** → window centers on the perpendicular axis, content-sized
- Anchor **two opposite edges** (Top+Bottom) → window stretches to fill that axis
- Anchor **Right only** + margin → right-centered panel that sizes to content

```rust
window.set_anchor(Edge::Right, true);
window.set_margin(Edge::Right, 20);
// Result: centered vertically on right edge, content height
```

### Monitor targeting

```rust
window.set_monitor(Some(&monitor));  // Note: Option<&Monitor>
```

Find monitor by connector name:
```rust
let display = gtk4::prelude::WidgetExt::display(&window); // disambiguate from RootExt
let monitors = display.monitors();
for i in 0..monitors.n_items() {
    let obj = monitors.item(i).unwrap();
    let monitor: gdk4::Monitor = obj.downcast().unwrap();
    if monitor.connector().as_deref() == Some("DP-1") { ... }
}
```

**Gotcha:** `window.display()` is ambiguous — both `RootExt` and `WidgetExt` define it. Use `gtk4::prelude::WidgetExt::display(&window)`.

---

## GTK4 API quirks (0.10)

### CssProvider
- Use `provider.load_from_data(&css_string)` — NOT `load_from_string` (doesn't exist in 0.10)

### Icon resolution
- `gio::Icon::to_string()` returns `Option<GString>`, not `String`
- Convert: `icon.to_string().map(|s| s.into())`

### Desktop app info
```rust
gio::DesktopAppInfo::new("firefox.desktop")  // returns Option<DesktopAppInfo>
```
Try multiple patterns: exact class, lowercase, last dotted segment (e.g., `com.mitchellh.ghostty` → `ghostty`).

---

## Signal handling (Unix signals in GTK event loop)

No `signal-hook` crate needed — glib handles it natively:

```rust
glib::source::unix_signal_add_local(libc::SIGUSR1, move || {
    // runs on GTK main thread, safe to touch widgets
    glib::ControlFlow::Continue  // keep listening
});
```

PID file pattern for external signal delivery:
```rust
fs::write("/tmp/my-app.pid", std::process::id().to_string());
// External: kill -USR1 $(cat /tmp/my-app.pid)
```

---

## Sharing state in signal/timer closures

Single-threaded GTK app — use `Rc<RefCell<T>>`, no `Arc/Mutex` needed:

```rust
let overlay = Rc::new(RefCell::new(MyWidget::new()));

// Clone Rc for each closure
let overlay_clone = Rc::clone(&overlay);
glib::timeout_add_local(Duration::from_millis(200), move || {
    overlay_clone.borrow().do_something();
    glib::ControlFlow::Continue
});
```

---

## Detecting physical key state (evdev)

**Problem:** Hyprland `bindr = , Super_L` doesn't fire after Super was used as a modifier (SUPER+u). The release event is swallowed.

**Solution:** Poll `/dev/input/` devices directly using `EVIOCGKEY` ioctl.

### Finding the right keyboard device

Many `/dev/input/event*` devices respond to `EVIOCGKEY` but only actual keyboards track modifier keys. **Must filter by capability:**

```rust
// EVIOCGBIT(EV_KEY) — get device key capabilities
let mut caps = [0u8; KEY_BYTES];
ioctl(fd, eviocgbit_key(), caps.as_mut_ptr());
// Check if KEY_LEFTMETA (125) bit is set in capabilities
if caps[125 / 8] & (1 << (125 % 8)) != 0 { /* this device has Super */ }
```

**Critical:** USB keyboards often expose multiple interfaces (HID main + keyboard + consumer). The first event device that responds to EVIOCGKEY may NOT be the one tracking real key state. Always check **all** devices and use the one(s) that actually report `KEY_LEFTMETA` in their capabilities.

### Polling pattern

```rust
// On show: start 50ms timer
glib::timeout_add_local(Duration::from_millis(50), move || {
    if !keys::is_super_pressed(&keyboards) {
        overlay.hide();
        return glib::ControlFlow::Break;
    }
    glib::ControlFlow::Continue
});
```

### ioctl numbers

```rust
const KEY_LEFTMETA: usize = 125;
const KEY_CNT: usize = 0x300;
const KEY_BYTES: usize = (KEY_CNT + 7) / 8; // 96

// _IOR('E', nr, size) = (2 << 30) | (size << 16) | ('E' << 8) | nr
fn ior(nr: c_ulong, size: c_ulong) -> c_ulong {
    (2 << 30) | (size << 16) | ((b'E' as c_ulong) << 8) | nr
}
fn eviocgkey()     -> c_ulong { ior(0x18, KEY_BYTES as _) }  // current key state
fn eviocgbit_key() -> c_ulong { ior(0x21, KEY_BYTES as _) }  // key capabilities
```

**Requires:** User in `input` group (`id -Gn | grep input`).

---

## Hyprland integration

### Querying state via hyprctl

```rust
fn hyprctl(args: &[&str]) -> Option<String> {
    let output = Command::new("hyprctl").args(args).output().ok()?;
    if output.status.success() { Some(String::from_utf8_lossy(&output.stdout).to_string()) }
    else { None }
}
// hyprctl monitors -j, hyprctl clients -j, hyprctl activewindow -j
```

Serde structs use `#[serde(rename_all = "camelCase")]` for hyprctl JSON.

### Bindings for key hold/release

```conf
# Press detection works fine:
bind = , Super_L, exec, show.sh

# Release detection is BROKEN when Super was used as modifier:
bindr = , Super_L, exec, hide.sh        # ← doesn't fire after SUPER+u
bindr = SUPER, Super_L, exec, hide.sh   # ← also doesn't fire
```

**Use evdev polling instead for release detection.** Only the show binding goes in Hyprland config.

### Debounce pattern (shell script)

Prevents flash on quick SUPER+1 combos. Only debounce show, not hide:

```bash
# Cancel previous pending
[ -f /tmp/show.pid ] && kill "$(cat /tmp/show.pid)" 2>/dev/null && rm -f /tmp/show.pid
# 200ms delay
( sleep 0.2; kill -USR1 "$(cat /tmp/overlay.pid)"; rm -f /tmp/show.pid ) &
echo $! > /tmp/show.pid
```

---

## Theme integration (Omarchy)

Read colors from `~/.config/omarchy/current/theme/waybar.css`:

```css
@define-color foreground #d3c6aa;
@define-color background #2d353b;
```

Parse with simple string splitting (no regex crate needed). Generate dynamic CSS with `alpha()` for transparency. Re-parse on every show so theme changes take effect without restart.

---

## Scrolling layout quirks

Hyprland scroller plugin `layoutopt:direction` is interpreted in **pre-transform coordinates**:
- Portrait monitor (rotated 90°): use `direction:right` to get visual down-scrolling
- Landscape monitor: use `direction:down` to get visual right-scrolling

This is counterintuitive — the directions appear swapped from what you'd expect.

---

## Project structure reference

```
Cargo.toml
src/
  main.rs        - Application, PID file, signal handlers, CSS, timers
  overlay.rs     - Layer shell window, UI building
  hyprland.rs    - hyprctl JSON queries
  icons.rs       - Desktop app icon resolution
  keys.rs        - evdev keyboard polling
  theme.rs       - Parse waybar.css colors, generate CSS
  style.css      - Static base CSS (include_str!)
```

## Build + deploy

```bash
cargo build --release
ln -sf $(pwd)/target/release/my-app ~/.config/hypr/scripts/my-app
# In autostart.conf:
exec-once = ~/.config/hypr/scripts/my-app
```

`[profile.release]` with `strip = true` and `lto = true` for small binaries.
