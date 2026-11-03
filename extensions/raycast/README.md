# Raycast

Type `raycast extension` and the Raycast store is the list. There is no setup step. Enter installs the one you pick. A word after that filters the list: `raycast dad jokes`. Installed commands also show up from the root when the name matches, so the next time `dad` is enough.

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

The store list is requested when you type `raycast extension` (or open the Raycast screen). That sends the filter, if you typed one, to `backend.raycast.com`. Installing downloads the zip from the URL in that response, only when the host is `raycast.com` or `raycast-releases.com`. Opening a command runs it in this shell, with your permissions, unsandboxed, same as every other Keystroke extension.

`host/dist/host.js` is the runner, with React already inside it. Nothing else has to be installed for the list or for an extension that only needs `@raycast/api`. Node.js has to be on `PATH`, which it is on this machine. An extension with other npm dependencies gets those with `npm install --ignore-scripts` into its own folder at install time. Unpacking uses `python3`. Copy and paste use `wl-copy`, `wl-paste`, and `wtype` or Keystroke's paste helper. `xdg-open` opens links.

Preferences are the defaults from `package.json`, overridden by `preferences.json` in the extension directory if you create one. There is no preferences screen.
