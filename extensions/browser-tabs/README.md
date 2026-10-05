# Browser tabs

Switch to an open browser tab from Keystroke. Turn on **Extensions > Browser
tabs**, then type `@` to list every open tab, or `@ github` to narrow it.
Enter selects the tab in its browser and focuses that browser window.

Works with the browsers Omarchy knows: Chromium, Chrome, Brave, Edge,
Vivaldi, Helium, Firefox, Zen and LibreWolf. Web apps (Omarchy's app-mode
windows) have no tabs and are not listed; use the Windows extension for them.

To bind a key straight to the tab list:

```sh
omarchy-shell shell summon omarchy.menu '{"scope":"browser-tabs","title":"Browser tabs"}'
```

## Chromium-based browsers need one flag

Tabs are read through AT-SPI, the Linux accessibility interface. Firefox,
Zen and LibreWolf expose their tabs there on their own. Chromium, Chrome,
Brave, Edge and Vivaldi expose them only when accessibility was on when they
started, so add this flag to the browser's flags file (for Chromium
`~/.config/chromium-flags.conf`, for Chrome `~/.config/chrome-flags.conf`,
for Brave `~/.config/brave-flags.conf`) and restart the browser:

```
--force-renderer-accessibility
```

This makes the browser build its accessibility tree, which costs some CPU
and memory on heavy pages. Without the flag, `@` says *No browser tabs found*.

## Settings

- **Show tabs in the main search** (on): tab titles match at the root from two
  characters on.
- **Tabs in the main search** (5): at most this many tabs mix into the root.
- **Include application tabs** (off): also list tabs of GTK and Qt
  applications that expose them (Nautilus, Pinta, ...).
- The `@` prefix can be renamed under `providers.browser-tabs` in Keystroke's
  configuration.

## Data access and dependencies

Needs Python 3 with PyGObject and AT-SPI (`python-gobject`, `at-spi2-core`;
both are on a standard Omarchy install).

When the palette opens, the service starts `python3 bin/tabs-helper.py
--json-lines`, the backend of [Everything](https://github.com/brianblakely/omarchy-everything)
(vendored in `everything/`, MIT, see `everything/VENDORED.md`), trimmed to its
Hyprland and AT-SPI adapters. While it runs it:

- sets `org.a11y.Status.IsEnabled` on the session accessibility bus if it was
  off, and restores the previous value when it exits (a small guard process
  restores it even if the helper is killed). `ScreenReaderEnabled` is never
  touched;
- runs `hyprctl -j clients` and walks the accessibility tree of browser
  windows (native tab strips only; it stops at every web page document, so
  page content is never read);
- reads `/proc` for process ancestry, to tie a tab strip to its exact
  Hyprland window.

The palette asks for a rescan every two seconds while it is open (browsers
publish their tab strips late). Queries only filter the last result. Thirty
seconds after the palette closes the helper is asked to shut down. Activating
a tab closes the palette, then runs the tab's own accessibility action and
focuses its window with `hyprctl dispatch`.

Titles are kept in memory only. Nothing is written to disk, nothing touches
the network.

## Tests

```sh
python3 -m unittest tests.test_atspi tests.test_atspi_runtime   # Everything's AT-SPI tests, against the vendored copy
```
