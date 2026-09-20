# GIF Search

A small GIPHY browser for Keystroke. Enable **Extensions > GIF Search**, type
`gif happy` and press Enter to open the grid. `gif` opens trending GIFs.
The command prefix can be changed in Keystroke's generated settings screen.

- Type to search; requests wait until typing pauses for 300 ms.
- Up/Down moves between rows. Tab switches from the search field to the grid,
  where Left/Right moves between GIFs. Right at the end of the search text also
  switches into the grid and advances one GIF. Tab returns to search.
- Enter or click uses the default copy action. Ctrl+Enter or Ctrl+click uses the other.
- Previous/Next browses 24 results per page. Esc closes; Backspace in an empty
  search returns to results.
- Copy success or failure appears in the footer.

Settings in **Keystroke Settings > GIF Search**:

- **Default action:** Copy image (default) or Copy link. Swaps Enter and Ctrl+Enter,
  as well as click and Ctrl+click; the footer reflects the selected action.
- **Close after copy:** No (default) or Yes. Closes only after a successful copy;
  failures keep the view open so they can be read and retried.

GIFs are copied as Wayland `image/gif` data. Whether an application pastes and
animates that format depends on the application; copy the link when needed.
Downloads over 25 MB are rejected with a message. No favorites, history, file
exports, square conversion, clips or provider picker.

## How the port works

Studied the [Raycast GIF Search source at the requested commit](https://github.com/raycast/extensions/tree/3c654737b0d566d3103fcdf72221a9f34664bdf2/extensions/gif-search):

- `search.tsx` renders a React grid with provider selection, trending, favorites
  and recents. `useSearchAPI.ts` caches and paginates provider adapters, deduping
  GIFs into a common model.
- `models/giphy.ts` calls Raycast's GIPHY proxy and maps original and preview
  image URLs. Other adapters cover Klipy, GIPHY Clips and Finer Gifs Club.
- `GifActions.tsx` offers file/link/Markdown copy, paste, download and favorites.
  `copyFileToClipboard.ts` downloads to a temporary file (or reuses the favorites
  cache) and calls Raycast's macOS clipboard API.

This is a fresh QML/Python implementation of the core workflow, following
Keystroke's `CONTRIBUTING.md` extension guide and `docs/providers.md` API 1.
`core/Gifs.js` builds literal curl argv, validates results and creates the entry
row; `Service.qml` owns requests, debounce and clipboard state; `GifView.qml`
renders a three-column animated grid using host theme tokens. The Python
standard-library helper replaces macOS file copying with binary `wl-copy` input.
Only the current page is retained in memory. Outdated responses are ignored.

## Dependencies and data access

Requires the existing Keystroke/Quickshell environment, Qt GIF image support,
`curl`, `python3`, and `wl-copy` (wl-clipboard). No setup or package installation.

Nothing executes while disabled. Opening the GIF grid requests trending/search
JSON from `https://gif-search.raycast.com/api/giphy`, the same public proxy the
original uses, without an API key. This is Raycast-operated infrastructure,
not a guaranteed Keystroke service: availability or access may change. Search
phrases are sent to that proxy and GIPHY. Requests have a 15-second timeout and
a 2 MB response limit; errors have an explicit Retry button.

Qt loads animated previews from HTTPS GIPHY media URLs. Copying a GIF downloads
its original from GIPHY with a 20-second socket timeout, validates its GIF header
and size, then passes bytes to `wl-copy --type image/gif`. Copying a link starts
the helper and `wl-copy` without downloading media. The helper accepts only
HTTPS GIPHY URLs, including redirects. The clipboard is changed only on a copy
action. No persistent files, search history or analytics requests are written
by the extension. `wl-copy` retains ownership of the clipboard after the helper
exits, as usual. Disabling stops the extension's running processes.

## Development and verification

From the repository root:

```sh
QT_QPA_PLATFORMTHEME=generic bin/keystroke check-extensions extensions/gif-search
python3 extensions/gif-search/tests/test_copy.py
python3 extensions/gif-search/tests/palette_check.py
```

For local discovery, link this folder into
`~/.local/share/keystroke/extensions/gif-search`, then enable it through Keystroke.
Reload the shell after editing an already loaded service, as the host guide
describes. The implementation does not change Keystroke's core or live settings.

Verified on 2026-09-12: extension validation/lint and QML tests, four Python
clipboard tests, and the real palette offscreen test (including keyboard input)
pass. A live search and animated preview download worked; the production helper
downloaded a 2,987,777-byte original GIF into a fake clipboard receiver. The grid
was visually inspected with that real preview. Desktop app pasting and a live
installation were not exercised.
