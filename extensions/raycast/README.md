# Raycast

Install an extension from the [Raycast store](https://www.raycast.com/store) and run it inside Keystroke. Enable **Extensions → Raycast**, run **Run setup** once, then type `ray dad jokes` and install **Dad Jokes**. Enter on **Random Dad Joke** opens it in the palette.

`ray` with nothing after it lists what you have installed and the first page of the store. A query searches `https://backend.raycast.com/api/v1/store_listings/search`. Enter installs. On the Raycast screen, **Uninstall** removes a bundle you already downloaded. Installed commands also show up in the main palette when your query matches their name, so the next time you can type `dad` instead of `ray`.

Inside a command:

- Type to filter a list, or to talk to the extension when it does its own search
- Up and Down move, Enter runs the first action, Ctrl+Enter the second, Ctrl+K the rest
- Esc steps back through the extension's own screens, then returns to Keystroke
- A detail shows its markdown, a form its fields

## How it fetches an extension

Vicinae does not clone [raycast/extensions](https://github.com/raycast/extensions). It asks Raycast's store API for the listing and downloads the zip from `download_url` (a signed URL on `extensions.raycast-releases.com`). The archive is one folder deep: `dad-jokes/package.json`, `dad-jokes/index.js`, `dad-jokes/assets/`. Keystroke does the same. The directory it keeps is `store.raycast.<name>`, which is the id Vicinae uses, under `~/.local/share/keystroke/raycast/extensions` (or `$XDG_DATA_HOME` instead of `~/.local/share`).

The zip is already built. It `require`s `@raycast/api` and `react`. Those are not Raycast's app. The host in `host/` is a small compatibility layer adapted from [Nanolight](https://github.com/justrach/nanolight)'s Raycast host (MIT, Copyright 2026 Rach Pradhan; see `host/NOTICE`). It renders List, Detail and Form to JSON, and this extension's QML draws that JSON. On Linux, Vicinae also reads a compatibility sheet from `https://api.vicinae.com/v1/raycast/get-compat`. Keystroke caches that for a day and shows Works, Partial or Unlikely when the sheet has an entry. A missing entry does not block the install.

## What works, and what does not

Lists, details, forms, action panels, toasts, HUD, clipboard copy and paste, and `open` of a URL or file are wired up. Local storage and the cache are files inside the extension directory. `@raycast/utils` is usually already inside the store bundle.

AI, OAuth, the menu bar, and macOS-only pieces (Finder selection, real app control) throw a clear "not supported" error if the extension calls them and does not catch it. Grid is shown as a list. A dropdown on a list is not drawn. Native Swift or Rust commands are not in the store zip and will not run. Plenty of extensions assume macOS and will fail; the confirmation before install says so.

Paste uses Keystroke's `bin/keystroke-paste` when this folder is the shipped extension, and `wtype` otherwise. Copy uses `wl-copy`.

## Limits and dependencies

Nothing runs while the extension is off. Turning it on runs `bin/host status`, which reads the extensions directory and, if the cache is stale, fetches the Vicinae compatibility sheet.

`ray`, or the Raycast screen, then requests the store. That sends your search text to `backend.raycast.com`. Installing downloads the zip from the URL in that response, only when the host is `raycast.com` or `raycast-releases.com`. Extra npm dependencies other than `@raycast/api` and `@raycast/utils` are installed with `npm install --ignore-scripts` into that extension's folder. Opening a command starts `node` and runs the extension's JavaScript in this shell, with your permissions, unsandboxed, same as every other Keystroke extension.

**Run setup** copies `host/runtime-package.json` and the lockfile to `~/.local/share/keystroke/raycast/runtime` and runs `npm ci --omit=dev --ignore-scripts`. The lockfile pins `react@19.2.0` and `react-reconciler@0.31.0`; `npm ci` checks the registry hashes. Node.js 20 or newer has to be on `PATH` already. Setup does not use sudo and does not write inside the plugin folder.

Also used, and not downloaded by setup: `python3` (to unpack the zip), `npm`, `wl-copy`, `wl-paste`, `xdg-open`, and either `wtype` or Keystroke's paste helper.

Preferences are the defaults from `package.json`, overridden by `preferences.json` in the extension directory if you create one. There is no preferences screen.
