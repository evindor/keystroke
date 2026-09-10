# Translate

Google Translate inside the [Keystroke](../../README.md) command palette, without an account or an API key. Type `tr bonjour` and the translation is the top row; Enter copies it, Ctrl+Enter pastes it into the app you came from. The reverse translation sits under it as a sanity check, every other target language you configured follows, and an editor view shows all of them for longer text, with dictation.

It is a port of the Raycast [google-translate](https://github.com/raycast/extensions/tree/a5090e97075f2e65e331127456797d9561b5e2b0/extensions/google-translate) extension: same keyless endpoint, same same-language fallback and double-way translation, same preferences where they make sense in a palette.

## Turn it on

Extensions ship with Keystroke switched off. Type `ext`, open **Extensions → Translate**, and confirm **Enabled** (or Keystroke Settings → Translate → Enabled).

## Use

| Query | Result |
| --- | --- |
| `tr bonjour` · `translate bonjour` | detect the language, translate into your first target |
| `tr fr good morning` · `tr french good morning` | an explicit target, by code or English name |
| `bonjour to english` · `how are you in spanish` | the natural form, no prefix needed |
| `tr` alone, or the Translate screen | offers the current selection and the target picker |
| Translate screen, then any text | no prefix needed on the extension's own screen |

Rows for a translation:

- **The translation** (the answer row). Enter copies, Ctrl+Enter pastes (or the other way round, see *Default action*). The preview pane shows the full text, and the dictionary entries for a single word.
- **Back to <language>**: the translation translated back, the way Raycast's double-way translate works.
- **One row per further target language**, in your configured order. When the text is already in your first target language (English typed with English first), the next target becomes the answer instead of an echo.
- **Did you mean …**: Google's spelling correction; Enter retries with it.
- **Open in the editor**, **Open in Google Translate**, and **Speak** when playback is on and `mpv` is installed.

`tr` is the extension's declared prefix: typing it shows *Translate · to: …* under the search field and the `[to] <text>` placeholders after the caret, `/` lists it with every other command, and Settings → Translate → **Prefix** renames it. The natural form (`bonjour to english`) needs no prefix at all.

Two-letter codes that are also English words (`it`, `is`, `no`, `so`, `to`, `hi`, …) are not read as targets, so `tr it is raining` translates the sentence; write `tr italian …` for Italian.

**The selection.** When the palette opens with text selected (or, failing that, on the clipboard), the root lists **Translate the selection**: Enter opens the editor with it, Ctrl+Enter copies its translation. `tr` alone and the Translate screen add **Copy the translated selection** and **Paste the translated selection**, which close the palette at once and deliver with a notification when the answer lands. Turn this off with *Offer the selected text* if you do not want the palette reading the selection when it opens.

**The editor** (Enter on *Open in the editor*, or the selection row): a multi-line editor on top, one block per target language below, then the reverse translation. Enter copies the main translation and closes, Ctrl+Enter pastes it, Shift+Enter inserts a new line, Ctrl+O opens translate.google.com, Ctrl+S speaks. Your voice hotkey dictates into it.

**Target languages.** Settings hold the codes as a comma-separated list, but the place to change them is the picker: Translate screen → **Target languages** (or type `targets` there). Every language Google supports is a row; Enter adds or removes it, chosen ones are listed first with their position. Type to find one (`germ`, `ua`); the unfiltered list shows the first 120 rows, the palette's cap. Up to six targets.

## Settings

Keystroke Settings → Translate:

- **Target languages**: codes in order, default `en,fr`. Use the picker described above.
- **Translate from**: Detect by default; a fixed source language when detection gets it wrong.
- **Default action**: Copy (default) or Paste into the focused app. The other one is on Ctrl+Enter.
- **Prioritise cross-language results**: when the text is already in one of your targets, that echo goes last (default off, matching Raycast).
- **Offer the selected text**: read the selection when the palette opens (default on).
- **Offer pronunciation playback**: a Speak row and Ctrl+S in the editor, through `mpv` (default off).
- **HTTP proxy**: passed to `curl --proxy`; the escape hatch for rate limiting and geo-blocking.

Values live under `providers.translate` in `~/.config/omarchy/keystroke.json`.

## What it does on your machine

Everything below only happens once the extension is turned on.

- **Network**: `curl` to `https://translate.google.com/translate_a/single`, the undocumented endpoint the translate.google.com page uses (`client=dict-chrome-ex`), the same one the Raycast extension calls. It sends the text, the source and target codes and nothing else: no account, no key, no token. Requests go out 350 ms after you stop typing, one per (text, source, target); responses are cached for the session so backspacing and repeats are free. An HTTP 429 pauses requests for a minute. The `tk` token the Raycast port computes is not validated for this client and is not sent. Text over 2 KB in the URL goes as a POST body. *Speak* streams `https://translate.google.com/translate_tts` through `mpv`. *Open in Google Translate* opens the website with `xdg-open`.
- **Processes on every palette open**: `wl-paste` to read the selection (off with *Offer the selected text*). Once, `command -v mpv` when playback is on.
- **Paste**: `wl-copy` followed by `wtype -M shift -k Insert -m shift`, the same Shift+Insert Keystroke's dictation uses. The text is a positional argument, never part of a shell string.
- **Notifications**: `omarchy-notification-send` when a translated selection has been copied or pasted, or failed.
- No files are written. Nothing runs before the switch. No sudo, no daemons, no downloads.

## Limits

- The endpoint is undocumented and outside Google's terms of service; it is rate-limited per address and can change without notice. If Google changes the response, the row says *Translation unavailable* and the status line says the answer could not be read: that is the moment to fix `core/Translate.js`, whose parser is covered by captured fixtures (`tests/Fixtures.js`). Regenerate a fixture with:

  ```sh
  curl 'https://translate.google.com/translate_a/single?client=dict-chrome-ex&sl=auto&tl=fr&hl=fr&dt=t&dt=rm&dt=ld&dt=qca&ie=UTF-8&oe=UTF-8&otf=1&ssel=0&tsel=0&kc=7&q=hello%20world'
  ```

- Paste uses Shift+Insert; an app that does not bind it gets the clipboard only.
- *Speak* needs `mpv`; without it the row is hidden.
- Like every extension, this one runs unsandboxed inside your shell with your permissions once you turn it on. `Service.qml` and `core/Translate.js` are short; read them first.

## Layout

- `extension.json`: name, version, description, icon and `apiVersion` for the Extensions screen; read without loading any code.
- `Service.qml`: the provider object, the curl processes, the debounce, the cache, the selection probe and the editor's draft.
- `TranslateView.qml`: the editor view.
- `core/Translate.js`: the query grammar, request building, response parsing and rows as pure functions.
- `core/Languages.js`: the 250 languages Google accepts, from the Raycast extension (MIT).
- `assets/icon.svg`: the icon on rows, in Settings and on the Extensions screen.
- `tests/tst_translate.qml`: unit tests over captured responses, run by `bin/keystroke check-extensions`; `tests/palette_check.py` drives the real palette offscreen with a fake `curl` (set `KEYSTROKE_CAPTURE_DIR` to a folder to get PNGs of the rows and the view).
