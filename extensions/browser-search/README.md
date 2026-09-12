# Browser search

Search the default browser's saved history and bookmarks from Keystroke. Turn
on **Extensions > Browser search > Enabled**, then type words from a page's
title or URL in the main palette, or use `browser github` to search only the
browser. Enter opens the URL in the default browser; Ctrl+Enter copies it.

**Search history** and **Search bookmarks** are independent switches in the
extension's settings, both on by default. Switching either off excludes that
source from subsequent reads and results. With both off, no browser detection
or data reads run. The extension itself ships disabled like other extensions.
Settings live under `providers.browser-search` in Keystroke's configuration;
the command prefix can also be renamed there.

## Browsers and matching

- Detects the default desktop entry with `xdg-mime query default
  x-scheme-handler/https`, falling back to `xdg-settings get default-web-browser`.
- Supports standard Linux Chromium, Chrome (stable/beta/dev), Brave, Vivaldi,
  Edge and Firefox/Firefox ESR desktop entries, plus the Flatpak desktop IDs
  listed in `bin/search.py`. An unknown browser gets an explanation with the
  explicit command; it never falls back to another browser's data.
- Chromium-family browsers: reads `Default` and `Profile *` directories under
  their standard configuration directory. Honors `XDG_CONFIG_HOME`,
  `CHROME_CONFIG_HOME` and `CHROME_USER_DATA_DIR`. Guest and system profiles
  are excluded. Firefox: reads the profiles declared in `profiles.ini`,
  including absolute profile paths. Up to 32 profiles of the detected browser
  are searched; results open using the browser's normal profile selection.
- Custom desktop launchers, command-line profile/data-directory overrides,
  Snap layouts and browsers outside the supported IDs are not detected.
- At least two characters; all whitespace-separated words must occur in the
  title or URL, case-insensitively. This is literal substring search. Bookmarks
  come first, then recent history. Duplicate URLs become one result, labelled
  Bookmark, History, or both. The root shows up to 8 results; the command and
  provider scope show up to 30. Only HTTP(S) pages are offered; bookmarklets,
  browser-internal URLs and local files are excluded.

## Data access and dependencies

Needs Python 3 (standard-library SQLite and JSON) and `xdg-utils`, with no
setup or download. QML runs one asynchronous `python3 bin/search.py` child
per distinct eligible query and source combination, after the host's typing
pause. New queries cancel obsolete work. The child detects the browser and
reads Chromium's `History` SQLite database and/or `Bookmarks` JSON, or
Firefox's `places.sqlite`; disabled sources are not queried. SQLite is opened
read-only and includes committed WAL data while the browser is running.
It does not copy databases or use `immutable=1`, which could omit live visits.

There are no network calls, persistent indexes, data caches, browser database
edits, installations or background services. The host opens a URL only when
you activate its row. Results are not opted into Keystroke's persisted
frecency. Up to 16 query results stay in the service's memory and are cleared
on each palette open; disabling the extension destroys the service and stops
its child process.

The helper has a two-second data-read budget, a short SQLite lock timeout and
a five-second QML watchdog. Each source/profile returns at most 60 matches;
bookmark JSON is capped at 16 MB. A locked, corrupt or unavailable source
does not suppress matches from readable sources. Errors are shown only for
explicit browser searches. Reopening the palette retries and redetects the
default browser. Changes made in the browser during one palette session may
not appear until the next open.

The readers follow the upstream [Chromium history schema](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/history/core/browser/url_database.cc),
[Chromium profile locations](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/user_data_dir.md)
and [Firefox Places schema](https://searchfox.org/mozilla-central/source/toolkit/components/places/nsPlacesTables.h).

## Verification

```sh
bin/keystroke check-extensions extensions/browser-search
python3 -m unittest discover -s extensions/browser-search/tests -p 'test_*.py'
python3 extensions/browser-search/tests/palette_check.py
```

Tests use synthetic profiles, including live WAL history, source switches,
multiple profiles, Firefox, Flatpak, Unicode, literal SQL-like queries,
corrupt/locked data and unsupported browsers. The offscreen palette test
checks loading, settings, command routing, results, cache refresh and unload.
