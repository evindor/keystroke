# Private-data-free Keystroke captures

These tools render the production Keystroke QML UI with public demo content.
They are developer tools, not a production capture API. They do not modify
Keystroke itself.

## The offscreen way (default)

```sh
python3 tools/showcase/offscreen.py              # every scene → site/assets/screenshots/
python3 tools/showcase/offscreen.py commands help   # a few, by name
```

`offscreen.py` never touches the desktop. It runs the real `Keystroke.qml`,
with every bundled provider and the shipped extensions, under Quickshell's
offscreen platform, scaled 4x so the 640x540 card becomes the 2560x2160 PNG
`site/check.py` expects. The palette lives in a fake HOME (demo files, a demo
clipboard history, `keystroke.json` with Timer and Translate on, and a link
to `~/.local/state/omarchy/current` so the captures wear the desktop's
current theme), with a fake `curl` that answers Translate from a table, a
`wl-paste` that finds no selection, and a fake `OMARCHY_PATH` whose
`omarchy-menu-keybindings` prints demo binds. Every row on screen is what
the providers compute. The three states the real palette cannot reach
offline (the Applications list, a Codex conversation, a live recording) come
from the fixture palette below, run through the same offscreen window. The
Timer's countdown in the bar is the real `BarWidget.qml` against a fake bar,
saved as `bar-timer.png`. Set `KEYSTROKE_SHOWCASE_DEBUG=1` to see
Quickshell's log. Review the PNGs before publishing.

## The fixture palette (staged states, and the live-shell way)

## Why a temporary plugin

Normal providers can read personal clipboard history, files, recent questions,
and settings. `prepare.py` copies the actual palette, ResultRow, PreviewPane,
VoiceWave and ConversationView components into `/tmp/keystroke-showcase-plugin`.
It replaces provider discovery and voice transport with fixtures, redirects
HOME reads to an empty temporary path, disables queries and activation, and
adds a `grabToImage` capture method. Calculator and color results run the actual
providers, unit conversions run core/Units.js, and timezone examples run the
actual helper with an explicit date. Other rows are sample data following the
provider contract. The conversation and voice waveform are staged states.

`capture.py` temporarily copies this artifact into
`~/.config/omarchy/plugins/local.keystroke-showcase-<unique-id>`, enables it as an
independent overlay, and captures only the QML card. This write outside normal
Keystroke data folders is necessary to let the existing shell host it. It does
not replace the user's menu, read their provider data, use the mic, or capture
other desktop content. Cleanup disables and removes the temporary plugin and
rescans in a `finally` block. The unique path avoids Quickshell's component cache.
An interrupted/killed process may require manual removal of the temporary plugin.

## Reproduce on Omarchy

Run deliberately, with access to the user's shell and plugin directory:

```sh
python3 tools/showcase/prepare.py
python3 tools/showcase/fixtures.py
python3 tools/showcase/capture.py
```

Capture temporarily brings an overlay into view and rescans plugins. Review the
fixture source and generated PNGs before publishing. Do not substitute user data.
PNG output: `site/assets/screenshots/`, 2560 x 2160 on the reference desktop.
`prepare.py` honours `KEYSTROKE_SHOWCASE_DEST` and `KEYSTROKE_SHOWCASE_HOME`,
`fixtures.py` honours `KEYSTROKE_SHOWCASE_FIXTURES`; `offscreen.py` uses those.
These are screenshot fixtures, not an end-to-end functional test of the providers.
The product's actual behavior checks live in `tests/`.

## Share cards

`social.html` composes the screenshots in a code-native graphic layout. It does
not generate or redraw the app interface. All source images remain untouched.
`export-social.cjs` needs Playwright and Chromium. Set `PLAYWRIGHT_MODULE` to the
installed module directory if it is not on Node's module path; optionally set
`CHROMIUM_PATH`. Exports go to `/tmp/keystroke-press-kit/`.

```sh
node tools/showcase/export-social.cjs
```

Review the exports, copy `social-card.png` into `site/assets/`, and place the
landscape, square and individual cards in the desired sharing directory.
