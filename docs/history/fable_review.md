# Fable review: architecture, Omarchy fit, code, performance, naming

Written 2026-09-06 against commit `4137378` on this machine: Omarchy 4.0.2-1, Quickshell 0.3.1-1, Qt 6.11.2, Python 3.14.7. Everything cited below was read from the checkout or from `/usr/share/omarchy`; the two web guides (develop, publish) were read the same day. Nothing was installed, replaced, or committed. Backend tests (27) pass and `omarchy plugin validate` accepts the checkout.

The handoff in `fable-review.md` framed three things: the prototype, the leading proposal, and the open decisions. Short version of my verdict on each:

- **The prototype** is a good behavioral and visual reference with real bugs in the Omarchy adapter and a transport design that cannot meet the "cheap while hidden, instant when opened" goal in the shared shell.
- **The leading proposal** (one native Omarchy menu plugin, QML/JS capabilities, community capabilities as ordinary Omarchy plugins) is right, and the installed source supports it more directly than the handoff feared. The replacement/restore mechanism already exists and is used on this very machine.
- **The open decisions** mostly collapse once you accept two facts: `omarchy.clonedFrom` is the routing key and must stay, and Omarchy's `service` plugin kind plus `shell.serviceFor()` is the supported way for another plugin to hand this one a live object.

---

## 1. Recommendation

**Build one Omarchy-native `menu` plugin in QML/JS, in-process, and retire the Python host.** Keep this prototype as the UX spec (rows, previews, stable-row updates, keyboard model, settings screens, frecency rules) and port capability logic module by module.

Why this and not the alternatives:

| Option | Verdict | Decisive reason |
| --- | --- | --- |
| Native menu plugin, QML/JS | **Do this** | Shares the Qt runtime, theme, app library, plugin lifecycle, hot reload, and every existing caller of `omarchy.menu`. Zero extra processes while hidden. |
| QML + resident Python host (current) | Reject for production | `keepLoaded: true` in `manifest.json:13` plus `Process { running: true }` in `Flint.qml:281-286` means a Python interpreter starts at login and lives forever. With `keepLoaded: false` every summon pays interpreter startup before the first row. Either way the first frame after the hotkey is an empty card waiting on a pipe (`Flint.qml:116-121`). The stock menu paints its rows synchronously from memory (`Menu.qml:795-817`). |
| QML + on-demand helper per capability | Use narrowly | Justified where QML's JS lacks a facility. Concretely: IANA time-zone math (QML's engine has no `Intl.DateTimeFormat` zone support and `QTimeZone` is C++-only). Spawn a helper only after a cheap regex gate says the query is a time query. Never per keystroke. |
| Compiled worker or Qt C++ module | No | Nothing measured needs it, and a plugin cannot ship a compiled Qt module through `omarchy plugin add` (git checkout, no build step, validator refuses symlinks). |
| Standalone GTK/Qt app | No | Loses `resolveEnabledId` routing, dmenu callers, theme, app library, and the guide's explicit rule against a second Quickshell process. |

**What to keep, replace, remove from the current tree**

- Keep (port to JS): `flint/api.py:107-147` matcher as a provisional module; `flint/usage.py` frecency (half-life, cap, hashed ids, 2000-entry bound); `flint/config.py` validation semantics (typed schemas, unknown-field preservation, atomic writes, refuse to overwrite broken files); `extensions/calculator/extension.py` grammar (as a hand-written tokenizer/shunting-yard, not `eval`); `extensions/converter/extension.py` unit tables; the settings-screen generation in `extensions/settings/extension.py`; every UX rule listed in the handoff's "Behavior to preserve".
- Replace: the entire Omarchy adapter in `extensions/omarchy/extension.py` with the stock `MenuModel.js` (vendored, MIT, pinned to an upstream commit) and the stock guard/provider/route machinery from `Menu.qml`. See §3 for why the adapter is the weakest part of the prototype.
- Replace: `Flint.qml` colors, fonts, radius and spacing with Omarchy `Color.menu.*`, `Style.font.menuFamily`, `Style.cornerRadius`, `Style.gapsOut` tokens (`Commons/Color.qml:94-101`, `Commons/Style.qml:31-32,324`).
- Remove from production: `flint/host.py`, `flint/reply.py`, `bin/flint`, `shell.qml`, `examples/hello`, `docs/extensions.md` protocol. Keep `shell.qml`/`bin/flint` only if you want a screenshot harness, and then add a `qs.Commons` stub so the same QML runs in both places. Prefer developing in-shell: `~/.config/omarchy/plugins` hot-reloads on save (`PluginRegistry.qml:689-713`, `shell.qml:60-64,761-766`).

---

## 2. Omarchy integration design, with the source that makes it possible

### 2.1 Replacement and restoration are already supported. Keep `omarchy.clonedFrom`.

The handoff asked: what is the supported published mechanism that preserves calls to `omarchy.menu` and restores the original on disable/removal? It is `omarchy.clonedFrom`, and it is not clone-only:

- Routing: `PluginRegistry.resolveEnabledId()` (`PluginRegistry.qml:199-210`) returns any *enabled* installed plugin whose `omarchy.clonedFrom` equals the requested id. It does not check first-party provenance. `shell.summon/hide/toggle/callIfLoaded` all resolve through it (`shell.qml:441,481,511,568`). So `omarchy-menu toggle system`, all 18 default keybindings in `default/hypr/bindings/utilities.lua`, `omarchy-menu-select`, `omarchy-menu-input`, and `omarchy menu refresh|ping` reach the replacement unchanged.
- Enable: `setEnabled(id, true)` for a manifest with a non-widget kind and `clonedFrom` adds the source to `disabledPlugins[]` and records the intent in `cloneSourceRestores[]` (`PluginRegistry.qml:576-579`).
- Disable or remove: `setEnabled(id, false)` calls `restoreCloneSource()`, which removes the clone's entry, puts the source's bar entry back at the same position if the clone had replaced it, and clears `disabledPlugins` for the source (`PluginRegistry.qml:469-500,583`). `omarchy plugin remove` drives the same path and prints "Restored omarchy.menu" (`bin/omarchy-plugin-remove`).
- Proof on this machine: `~/.config/omarchy/shell.json` already carries `disabledPlugins: [omarchy.osd, omarchy.notifications, omarchy.lock, …]` and `cloneSourceRestores: [evindor.osd, evindor.notifications, evindor.lock]`.

The develop guide's "remove `clonedFrom` before publishing" is written for a clock that becomes an independent widget. The publish guide says nothing about `clonedFrom` or about replacing built-ins, and marketplace validation is `omarchy plugin validate`, which does not inspect the `omarchy` metadata block. Conclusion: **ship with `omarchy.clonedFrom: "omarchy.menu"`**, say in the README that the plugin is a deliberate menu replacement, and open an upstream issue proposing an explicit `omarchy.replaces` alias so the intent is documented rather than inferred. Risk is policy, not code.

### 2.2 The bar-widget quirk you must decide on

`isEnabled()` for a third-party plugin is "referenced somewhere in shell.json" (`PluginRegistry.qml:176-192`). With `kinds: ["menu","bar-widget"]`, enabling places the plugin in the **bar layout** (replacing the stock button in place if present, otherwise inserting into the manifest's default section) and does not add it to `plugins[]` (`PluginRegistry.qml:552-580`). Consequences:

- If the user later removes the button from the bar, the plugin becomes disabled, `resolveEnabledId` falls back to `omarchy.menu`, which is in `disabledPlugins`, and `summon` refuses (`shell.qml:451-454`). Result: no menu at all until the user edits shell.json.
- On this machine the stock button is not in the bar, so enabling would insert a new button in the center section by default.

Options: (a) keep both kinds for stock parity and in-place button replacement, document the constraint, and file an upstream fix (`isEnabled` should treat a plugin listed in `cloneSourceRestores` as enabled); (b) ship `menu` only, which records the plugin in `plugins[]` and is robust, but users who had the stock button lose it because disabling `omarchy.menu` unloads its widget too (`shell.qml:673-676`). I recommend (a) plus the upstream issue; the owner should confirm. Either way, the manifest should set `barWidget.defaultSection: "left"` to match where the stock button lives (`shell.qml:47`).

### 2.3 Lifecycle contract the menu must honor

From `shell.qml` and `Menu.qml`, the host will:

- Instantiate the `entryPoints.menu` component through a `Loader` (async) when `keepLoaded` is true or when first summoned (`shell.qml:623-626`), inject `omarchyPath`, `shell`, `manifest`, `barWidgetRegistry`, `pluginRegistry`, and `service` if the properties exist (`shell.qml:629-637`).
- Call `open(payloadJson)` on summon, possibly several queued payloads (`shell.qml:541-556`); call `close()` on hide; read `opened` to decide toggle (`shell.qml:504-507`); call arbitrary methods through `omarchy-shell shell call <id> <method> <arg>` and stringify the return (`shell.qml:567-579`). The stock menu exposes `refresh()` and `ping()`.
- Destroy and recreate the instance on any file change under `~/.config/omarchy/plugins` and on `rescanPlugins` (`shell.qml:739-759`). Anything you spawn must tolerate that; a resident child process would need explicit cleanup you cannot guarantee from QML.

Payload parity to restore (stock behavior, `Menu.qml:21-32,819-838,853-869`):

- `initialMenu` as well as `menu` (Flint reads only `menu`, `Flint.qml:106`).
- `fontFamily` override.
- Leaf routes execute immediately on summon. Super+Ctrl+R is bound to `omarchy-menu toggle reminder-set`, and screen recording uses `screenrecord-stop`; both are broken by Flint's "show the command and wait for Enter" choice. This is the highest-priority parity bug.
- dmenu `width` and `maxHeight` honored in `Style.space()` units; Flint normalizes to its card (`Flint.qml:143-157`). A picker with three options should not open a 640×540 card.
- A second dmenu request while one is active: stock leaves the first caller hanging; Flint cancels it (`Flint.qml:104`). Flint's behavior is better; keep it and say so in the README.
- Keys: Right activates (`Menu.qml:1106`), PageUp/PageDown move by 6 (`1100-1105`), Delete offers app uninstall through `appLibrary.remove` (`1081-1083,764-771`), Escape clears the filter before closing (`1084-1087`). Flint's "Escape closes immediately" is a deliberate user decision; keep it, but add PageUp/Down, Right, and Delete.

### 2.4 Shared services to use instead of reimplementing

- Applications: `shell.appLibrary` (`services/AppLibrary.qml`) gives `sortedEntries(query)`, `isHiddenEntry`, `iconSource(icon)` with a fallback index for icons installed after the shell started (`:57-73`), `launch(desktopId, name)` with launch-feedback OSD (`:77-86`), `remove()`, and `appsChanged`. Flint launches with `uwsm-app -- gtk-launch` (`extensions/applications/extension.py:16`) and looks icons up with `Quickshell.iconPath` (`ui/ResultRow.qml:38`), losing the fallback index and the feedback OSD, and decoding at 32 logical px so HiDPI icons blur (`Menu.qml:1259-1262` explains the fix).
- Clipboard: read `~/.local/state/omarchy/clipboard-history.json` as Flint does (`extensions/clipboard/extension.py:15`); the format normalizer to copy is `plugins/clipboard/ClipboardHistory.js:1-31`. There is no public cross-plugin object for the overlay's in-memory history; the file is the contract. Image re-copy through `omarchy-clipboard-paste-file --copy-only` needs an end-to-end check.
- Emoji: `plugins/emojis/emojis.json` (1,870 entries, `{e, k}`) and `EmojiSearch.js`.
- Theme: bind to `Color.menu.background/text/border/scrim/selectedBackground/selectedText/selectedBorder` and `Style.font.menuFamily`; `omarchy-shell shell applyTheme` updates the singletons live (`shell.qml:879-888`). Fonts, radius, and gaps come from `Style`. Keep the palette's identity in layout, the preview pane, typography scale, and an accent that defaults to the theme accent. Hard-coded `#222126`-style colors across `Flint.qml`, `ResultRow.qml`, and `Keycap.qml` will look wrong under any light theme.
- Layer namespace: Hyprland's default rule disables animation for `^(omarchy-menu|…)$` (`default/hypr/apps/omarchy-shell.lua:10`). Flint uses `WlrLayershell.namespace: "flint"` (`Flint.qml:321`) and therefore gets the default layer animation, which reads as slower opening and is inconsistent with the rest of the shell. Use `omarchy-menu` while acting as the menu replacement (the stock one is disabled), or ship a documented layer rule.

### 2.5 Community providers: use the `service` kind and `shell.serviceFor()`

Do not invent a plugin kind. Omarchy loads every enabled plugin of kind `service` into a hidden host item, injects `shell`/`manifest`/`pluginRegistry`, destroys it on disable/removal, and exposes `shell.serviceFor(pluginId)` (`shell.qml:263-354`). That is a first-party function whose documented purpose is sharing a live object between a plugin's parts (`shell.qml:634-637`). Design:

```text
community plugin  manifest.json: kinds ["service"], entryPoints.service = "Service.qml",
                  plus a top-level marker block, e.g. "x-<palette>": {"apiVersion": 1}
                  Service.qml: QtObject { readonly property var provider: ({ id, name, icon,
                  prefix, settings: [...], query: function(ctx, emit), activate: function(row) }) }

palette (menu)    on open and on pluginRegistry.pluginsChanged:
                  for id in pluginRegistry.installedPlugins where manifest["x-<palette>"]
                    and pluginRegistry.isEnabled(id): inst = shell.serviceFor(id)
                    register inst.provider if inst && inst.provider.apiVersion === 1
```

Properties of this contract, all derived from host behavior:

- Load order does not matter: services load when the registry changes; the palette enumerates lazily.
- Absent palette: the service idles. Disable/remove: the shell destroys the instance; the palette drops it on the next `pluginsChanged`. Duplicate ids are impossible (registry keys). Version mismatch: the palette lists the plugin in Settings with "needs palette API 2" instead of loading it.
- Custom top-level manifest keys pass both `validateManifest` (`PluginRegistry.qml:96-144`) and `omarchy plugin validate`; unknown `entryPoints` keys also pass, so a `Provider.qml` entry point loaded by the palette itself is a viable alternative if you later want the palette to own instantiation. Start with `serviceFor`; it is less code and Omarchy owns the lifecycle.
- Caveat to state in the docs: injection of `pluginRegistry` and `shell.serviceFor` are source-level contracts of Omarchy 4.0.x, not in the web guide. Feature-detect (`typeof shell.serviceFor === "function"`) and declare a minimum Omarchy version in the README.

Bundled and community providers should implement the identical interface; bundled ones are simply instantiated from the plugin's own directory. That removes the "two extension systems" problem the handoff worried about.

Minimal provider interface (v1): `id`, `name`, `icon`, optional `prefix`, optional `scopes`, `settings` schema, `query(ctx, emit) -> rows | undefined` (return rows synchronously when cheap; otherwise return nothing and call `emit(ctx.generation, rows)` later; the host discards stale generations), `activate(row, ctx) -> effect`. Effects stay declarative (`exec` argv, `copy`, `url`, `navigate`, `setting`, `compound`, `confirm`) so the host owns closing the layer before launching. Views: generic list plus the existing preview kinds (text, swatch, image). Arbitrary QML views can wait for v2.

### 2.6 Settings ownership

One authoritative file: `~/.config/omarchy/<name>.json` (JSON with comments tolerated, like `omarchy-menu.jsonc` next to it). Read with a `FileView { watchChanges: true }`, write with `atomicWrites: true` (`shell.qml:130-139` does exactly this for shell.json). Structure `{ version, palette: {density, accent, showPreview}, providers: { "<providerId>": {enabled, ...schema keys} } }`. Keep the prototype's rules: validate against schema, ignore invalid values, preserve unknown fields, never overwrite a file that fails to parse. `shell.json` stays Omarchy's domain (installed/enabled). Provider-level `enabled` defaults true for bundled providers and false for community ones, exactly as now. Do not store per-extension trees in `shell.json`: it is not deep-merged (`shell.qml:72-88`) and `updateEntryInline` is designed for flat widget settings.

### 2.7 Trust statement to keep

Everything runs in the user's shell process with the user's permissions; the marketplace validates listings, not security (publish guide). Present provenance (bundled vs community, plugin id, repo) in Settings, default community providers off, and drop the `permissions` array from manifests unless it gates a real host behavior. In the prototype it only gates `validate_action` (`flint/host.py:152-169`), which the same code could bypass by spawning a process directly.

---

## 3. Code findings, prioritized

Severity reflects user impact in the intended production setting (shared shell), not only the review harness. "Demonstrated" means visible from the code without runtime measurement; "hypothesis" needs a repro.

### High

1. **Guard evaluation is on the query path and can stall results for seconds.** `extensions/omarchy/extension.py:50-62,130-131` builds a bash script for the `when`/`checked` expressions of every candidate's ancestor chain and awaits it inside `query()` with an 8 s timeout whenever the 30 s cache has expired. Unlike the stock batch (`MenuModel.js:383-478`), it has no `pacman` prelude, so each `omarchy-pkg-present` forks `pacman -Q`; the stock comment says the un-batched menu "spends over a second on them". A query like `install` after 30 s of idle blocks the Omarchy rows for that long. The coalescing window (`flint/host.py:132-143`) hides it partially by emitting other providers first, then the Omarchy rows pop in. Stock evaluates all guards once per load and per open, never per query, and opens on the previous answers (`Menu.qml:952-974,807`). Demonstrated. Fix by porting the stock approach.

2. **Leaf routes no longer run on summon.** Covered in §2.3. Breaks `omarchy-menu toggle reminder-set` (Super+Ctrl+R) and any `summon <alias>` for an action. Demonstrated.

3. **Activation can fail on an unrelated model refresh.** `flint/host.py:60` clears `self.actions` at the start of every query. `Flint.qml:310-313` triggers `refresh()` whenever `DesktopEntries.applications.valuesChanged` fires, and the stock menu documents that this happens when applications start (`Menu.qml:613`). Sequence: user presses Enter, UI sends the token, a launch elsewhere fires `valuesChanged`, the host starts a new query and clears actions, then processes the activate: "Result expired; search again". Hypothesis with a clear mechanism; reproduce by launching an app from another terminal while pressing Enter. A native design avoids this by keeping action closures on the row objects.

4. **Resident interpreter and empty-first-frame are inherent to the transport.** `Flint.qml:281-286,116-121`; see §1. Demonstrated by design.

5. **Theme and layer-rule mismatch.** §2.4. Demonstrated.

### Medium

6. **Per-keystroke deep copies of large rows.** `ListModel { dynamicRoles: true }` (`Flint.qml:279`) is the slow ListModel mode, and each row's whole `entry` object is copied into the model on insert/`setProperty` (`Flint.qml:60-63`). Clipboard rows carry up to 12,000 characters of `preview` each (`extensions/clipboard/extension.py:37`), so a 100-entry clipboard scope moves about 1 MB through JSON, the pipe, and the model per keystroke. `applyRows` also calls `resultModel.get()` in a nested loop (`Flint.qml:51-59`), and each `get` allocates a JS wrapper. Fix: fixed roles, previews fetched for the selected row only, cap rows at what the viewport plus cache buffer can show.

7. **Provider spawns on every non-empty query after 30 s.** `extensions/omarchy/extension.py:111-115` loads the `fonts` and `power-profiles` providers for any query (the `or entry["provider"] in {...}` branch), running four subprocesses sequentially (`:75-77`) before the Omarchy rows return. Stock caches non-volatile providers for the session and re-runs volatile ones only on submenu entry (`Menu.qml:264-268,407-414`). Demonstrated.

8. **Guard and `checked` freshness.** With the 30 s cache, a ✓ marker (default browser, toggles) can be wrong for up to 30 s after the user changes it through the same menu. Stock re-evaluates on every open. Demonstrated.

9. **Full app resync on every open and on every `valuesChanged`.** `Flint.qml:91-99,120,312` serializes the complete application list over the pipe each time. Bounded, but it is work on the hot open path that the native version gets for free from `appLibrary`.

10. **Every launch waits 70 ms.** `Flint.qml:301-309`. The stock menu sets `opened = false` and calls `execDetached` synchronously (`Menu.qml:780-787`). Measure before keeping; the delay was a workaround for keyboard-grab timing that may not exist once the layer closes in the same event loop tick.

11. **Row title captured after the round-trip.** `Flint.qml:253` uses `current.title` when the `navigate` reply arrives; if the selection moved in between, the breadcrumb shows the wrong title. Minor race, disappears with in-process activation.

12. **Custom provider commands are executed from JSONC.** `extensions/omarchy/extension.py:85-90` runs `shlex.split(provider)` for any provider name other than `apps`, `fonts`, `power-profiles`. The stock QML menu ignores unknown providers (`Menu.qml:338-339`); the JSONC header describes the command form from the older bash menu. The file is user-owned, so this is a divergence rather than a vulnerability, but decide explicitly whether to support it; if yes, sanitize failure paths and document it.

13. **`bash -c` versus stock `bash -lc`.** Guards and actions run without a login shell (`extensions/omarchy/extension.py:58`, `flint/host.py:211`); stock uses `-lc` for providers, guards, and actions (`Menu.qml:346,972`, `Commons/Util.qml:53-55`), and its `execArgv` helper shows the safe argv form for input-derived commands (`Util.qml:62-64`). PATH additions made only in login profiles will differ. Low impact under uwsm, but a parity item.

14. **`copy` effect waits on `wl-copy` under a process group kill.** `flint/host.py:200-201` runs `wl-copy` through `run()` with a 2 s timeout; `run()` kills the whole session on timeout (`flint/api.py:49-58`). `wl-copy` forks a child that serves the selection. Manual testing showed copy works, so the child evidently does not hold the pipe; but if it ever did, the timeout would kill the clipboard owner and silently lose the copy. Hypothesis; in the native version use the same detached invocation the clipboard plugin uses.

### Low

15. `extensions/omarchy/extension.py:145` computes `list(items).index(id)` per candidate, O(n²) for broad queries (320 items). Precompute order once, as stock does (`MenuModel.js:89`).
16. `flint/host.py:61` rereads and parses the config on every query. Cheap, but check mtime instead, or use a watched `FileView` natively.
17. `extensions/converter/extension.py:32` calls `zoneinfo.available_timezones()` per non-city query; it walks the tz directory each time. Cache it.
18. `Flint.qml:218` spawns a Python interpreter to write two files for each dmenu reply. Stock uses one `bash -c printf` (`Menu.qml:130-134`); natively, write with `FileView` or the same bash form.
19. `Flint.qml:203,293-297`: if the host dies while `activateWhenReady` is set, the flag survives; the next successful query would activate the first row unexpectedly. Clear it in `onExited`.
20. `ui/ResultRow.qml:39`: `sourceSize: Qt.size(32,32)` ignores `Screen.devicePixelRatio`.
21. `extensions/ai/extension.py:8,15`: `omarchy-launch-terminal codex -- <prompt>` and `claude-desktop` are unverified command lines; the README already says so. Detect installed targets through `DesktopEntries`/`appLibrary` at query time and hide options that cannot work, rather than offering them and failing on activation.
22. Tests: the backend suite is solid for parsing, config, ranking, and frecency, but nothing exercises guard timing, provider freshness, the activation race, or in-shell lifecycle. Port the behavioral cases (`tests/test_flint.py:115-141,163-183`) to a QML test runner (`qmltestrunner` ships with `qt6-declarative`) as part of the migration.

### Maintainability

`Flint.qml` mixes five responsibilities (window/focus, navigation stack, model reconciliation, dmenu protocol, transport). For the native version split into `Palette.qml` (window, keys, layout), `PaletteModel.js` (rows, ranking, generations), `Navigation.js` (scope stack), `Dmenu.js` (payload parsing, reply), `Providers.qml` (registry, bundled instantiation, community discovery), and `Settings.qml` (schema, file). Keep `MenuModel.js` vendored verbatim under `omarchy/` with the upstream commit hash in a header comment so diffs against Omarchy updates are mechanical.

---

## 4. Performance plan and budgets

Baseline first: measure the stock menu, then the prototype enabled in-shell, then a 200-line native spike (stock `MenuModel.js` rows + `appLibrary` rows + a JS calculator behind Flint's layout). Those three numbers settle the runtime question in an afternoon.

**Instrumentation that exists on this machine**

- Latency: add `console.time`-style stamps in the plugin (`open()` entry, first `rows` assignment, and a zero-interval `Timer` armed after the assignment, which fires once the event loop has turned and approximates "committed to render"). Quickshell 0.3.1 does not expose the window's `frameSwapped` signal in its qmltypes, so confirm a small sample externally with a 120 fps capture (`wf-recorder` or `wl-screenrec`) against the key-press timestamp. Log p50/p95/p99 over 100 opens driven by `omarchy-shell shell toggle …` from a script. Keystroke-to-rows: drive `call <id> setQuery` at 10 chars/s and stamp model updates.
- Rendering: run the shell once with `QSG_RENDER_TIMING=1` to get per-frame render/sync times while typing; `QSG_VISUALIZE=changes` to spot whole-list repaints.
- Memory: `awk '/^Pss|^Private_Dirty/' /proc/$(pidof omarchy-shell)/smaps_rollup` before and after enabling the plugin, at 60 s idle, after 50 opens, after 2 h. Report Pss and Private_Dirty deltas, not RSS.
- Wakeups and CPU: `perf stat -e task-clock,context-switches -p <pid> -- sleep 60` hidden, with and without the plugin; `powertop --time=60 --csv=…` for wakeups/s per process.
- GPU: `intel_gpu_top`/`amdgpu_top`/`nvtop` at idle with the palette hidden; it should be indistinguishable from stock because nothing is mapped.
- Battery: `upower -i $(upower -e | grep BAT)` energy-rate sampled every 30 s for 20 min, three runs each, same brightness and app set, stock vs palette. Report means and spread; anything under the run-to-run spread is "no measurable difference", not "zero".

**Acceptance budgets (warm, this machine)**

| Metric | Budget | Rationale |
| --- | --- | --- |
| Hotkey to first painted frame with rows | p95 ≤ stock + 10 %, absolute ≤ 40 ms | Stock paints from memory; the replacement must too. |
| Keystroke to updated rows (apps + menu + calc, 2–5 chars) | p95 ≤ 16 ms, p99 ≤ 33 ms | One frame at 60 Hz for p95. |
| Emoji scope (1,870 entries) keystroke to rows | p95 ≤ 8 ms | Linear scan in JS; if it misses, move to `WorkerScript` (installed at `/usr/lib/qt6/qml/QtQml/WorkerScript`). |
| Frame time while typing 10 chars/s | no frame > 16 ms, zero dropped in a 10 s run | Delegates updated in place, fixed roles. |
| Incremental Pss hidden, after 2 h | ≤ 15 MB over stock shell | Same process; only data and component cache. |
| Incremental wakeups hidden | 0 timers, < 0.5/s over stock | No polling, no watchers beyond FileViews already used by stock. |
| Long session | 500 opens, 5,000 keystrokes: Pss growth < 5 MB | Catches model/wrapper leaks. |
| Slow provider (bash guard, community provider) | never delays first rows; late rows merge without moving the selection | Generation-guarded async merge. |
| Plugin reload/disable/remove | palette usable again within 500 ms, no orphan processes (`pgrep -af python`) | Hot reload is routine in Omarchy. |

Historical numbers in `verification.md` (0.08–4 ms in-process, 420 MiB RSS standalone) do not bear on these budgets and should be retired from the README once the native build exists.

---

## 5. Staged migration and validation

Each stage ends with a gate; do not start the next without it.

1. **Native clone with parity (1 week).** `omarchy plugin clone omarchy.menu`, move it into this repo as `<id>/`, rename, keep `clonedFrom`. Replace presentation with Flint's layout under Omarchy tokens. Keep `MenuModel.js`, guards, providers, routes, dmenu untouched. Gate: all 18 default bindings and `omarchy-menu-select/input` behave identically; disable/enable/remove restore the stock menu; hot reload works; budgets for open latency and hidden Pss met.
2. **Provider registry and bundled providers (1–2 weeks).** Introduce the provider interface; wrap the stock menu items and `appLibrary` as the first two providers; add calculator, converter (units in JS; time zones behind a gated helper), colors, emoji, clipboard, AI/web, settings. Port the behavioral tests. Gate: the UX list in the handoff passes; keystroke budgets met; settings file round-trips.
3. **One community provider end to end (3 days).** A separate repo, kind `service`, installed with `omarchy plugin add … --enable`, discovered through `shell.serviceFor`. Exercise enable, disable, reload while a query is in flight, removal, and a deliberately slow provider. Gate: no stale rows, no leaked instances, clear Settings messaging when absent or mismatched. Only after this gate, write `docs/providers.md` and call the API v1.
4. **AI handoff verification (2 days).** Confirm desktop entries and deep links for the installed Claude and ChatGPT apps, the `omarchy-launch-terminal` argument form, and Google URL encoding. Hide modes whose targets are absent. Do not promise populated chats where a deep link does not exist; copying the prompt plus a notification is the honest baseline.
5. **Fuzzy matching and ranking calibration (after 1–4).** Replace the provisional matcher behind a single `match()` module; keep frecency as a separate additive bonus capped below the "answer" tier; introduce host-owned tiers (`answer`, `item`, `fallback`) so a provider's numeric score only orders within its tier. Calibrate with a recorded set of real queries against installed apps and menu labels.
6. **Publish.** Permanent id, minimum Omarchy version, README section on replacement and restore, upstream issue for `omarchy.replaces` and the `isEnabled` quirk, marketplace submission.

---

## 6. Decisions that need the owner

1. **Name and permanent id** (see §7). Everything downstream is named after it: plugin id, config file, layer namespace, service marker key.
2. **Manifest kinds:** `menu` + `bar-widget` with the enable/disable quirk documented, or `menu` only. My recommendation is both kinds plus the upstream issue.
3. **Escape semantics:** keep "Escape closes immediately" (your choice) or stock's "clear filter, then close". Recommend keeping yours and adding Shift+Escape or Ctrl+U for clear.
4. **Custom JSONC providers:** support command-style providers (prototype behavior) or match the stock QML menu (ignore them).
5. **Time-zone helper:** accept a gated on-demand helper (GNU `date` or a tiny Python call) for IANA conversions, or drop DST-exact time conversion from v1.
6. **Config location:** `~/.config/omarchy/<name>.json` as recommended, or a separate XDG directory.

---

## 7. Names

Criteria: short, sharp or quick in meaning, easy to say and type, no binary or Arch package collision (checked `command -v` and `pacman -Ssq` on this machine; AUR not checked), and not cheesy. "Flint" is fine as a metaphor but it is also a common English word attached to many projects, and you said you do not like it.

| Name | Why it fits | Notes |
| --- | --- | --- |
| **Glint** | A quick flash of light off a sharp edge. One letter from Flint, so the prototype's history stays legible. Five letters, unclaimed here. | My first pick. Reads well as a verb in prose ("glint open", "glint search"). Id: `<you>.glint`. |
| **Hone** | To sharpen, and to home in on a target. Four letters, quiet, not cute. | Second pick. Slightly less obvious as a product name; very good as a command. |
| **Flick** | The gesture: a quick, precise flick of the wrist. Keeps the F. | Playful without being cheesy. |
| **Whet** | Sharpening again ("whet the blade"). Four letters, uncommon. | Harder to say aloud; strong on a keyboard. |
| **Fletch** | Fletching makes an arrow fly straight and fast. Uncommon, memorable. | Slightly obscure; good if you like a story behind the name. |
| **Kestrel** | Hovers, then strikes. Precise and fast. | Seven letters; best as a brand, less as a command. |
| **Omarrow** | Omarchy + arrow: points you where you want to go. | The one Oma- pun that does not feel forced; still a pun, so lower on the list. |

Avoid: Dart, Dash, Bolt, Strike (all collide with repo packages), Spark (crowded), Ember (already your accent color and a framework), Trigger (an Omarchy menu section).

If I had to choose today: **Glint** for the plugin and brand, `glint` for the config file and layer namespace, `x-glint` for the manifest marker, and `evindor.glint` or `io.github.evindor.glint` as the id.
