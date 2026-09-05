# Architecture review

## Evidence from this machine

Inspected on 2026-09-06:

- Omarchy **4.0.2-1**, Quickshell **0.3.1-1**, Qt **6.11.2**.
- `/usr/share/omarchy/bin/omarchy-menu` is an IPC wrapper around `omarchy.menu`.
- The menu is a `menu` + `bar-widget` plugin with `keepLoaded: true`.
- `/usr/share/omarchy/shell/plugins/menu/Menu.qml` contains the visual surface, navigation, providers and dmenu compatibility. `MenuModel.js` handles parsing, merging and search.
- The definition is `/usr/share/omarchy/default/omarchy/omarchy-menu.jsonc`; user overrides are in `~/.config/omarchy/extensions/omarchy-menu.jsonc`.
- `shell.appLibrary` shares the native `DesktopEntries` index. Clipboard and emojis already have useful Omarchy services/data.
- `PluginRegistry.qml` resolves calls to a built-in ID to an enabled plugin whose `omarchy.clonedFrom` matches it.

The [Omarchy plugin development guide](https://plugins.omarchy.org/develop.html) recommends cloning a built-in with the same runtime contract, developing in user-owned files, and sharing the existing shell process. Its generic publishing example removes clone metadata. For a deliberate menu replacement, we need to confirm the supported published replacement mechanism before dropping `clonedFrom`; blindly removing it would lose existing menu routing.

## Recommendation following the user's feedback

Develop **one Omarchy-native menu plugin**, starting from the stock menu clone. Preserve the host lifecycle and dmenu contract, then replace the presentation and add a capability registry. No separate desktop application or fork of the whole Omarchy distribution is needed.

Ship maintained capabilities in this repository. Accept PRs for those modules. Allow independently distributed Omarchy plugins to register additional capabilities with Flint. This reuses installation, update, enabling/disabling, hot reload and removal that Omarchy already supplies.

The stock plugin kinds do **not** currently include a Flint search-provider kind. "A plugin for a plugin" is feasible, but not automatically implemented by Omarchy. We must define a small contract, for example:

```text
Omarchy plugin (service)
  └─ register Flint provider metadata + query/activate/settings interface
       └─ Flint menu ranks results and renders list/detail/form views
```

The precise discovery mechanism is still a proposal: service registration via the injected shell/registry, or namespaced Flint metadata discovered from installed plugin manifests. It must handle load order, disabled plugins, reload, unregistration, ID collisions and an absent Flint host. Do not publish a new unsupported `kind` and assume Omarchy knows how to mount it.

## Why Python is in the review build

The original idea was to keep arbitrary-language extensions outside the QML UI thread, use Python's standard-library arithmetic parser and IANA time-zone support, and cancel slow processes with bounded outputs. That produced a useful working prototype, but also introduced another process, serialization, settings store and extension registry.

QML executes JavaScript inside Qt's runtime. It does not need Node or Python for ordinary menu logic. For the Omarchy-native direction, the extra Python host is unnecessary for the core menu and search plumbing. Port ordinary capabilities to QML/JS; use event-driven `Process` calls only where the capability actually needs an external tool. Keep expensive I/O asynchronous and avoid running a subprocess per keystroke.

## Trust model

Bundled means maintained and reviewed; it cannot mean guaranteed safe. Third-party Omarchy plugins run unsandboxed with the user's permissions, in the desktop shell's process. Marketplace installation is not a sandbox or a safety certification. A malicious or badly behaved QML plugin can access files, invoke commands, or freeze the shell.

Flint should make provenance and required capabilities visible, default optional community providers off, and document this trust boundary. A future isolated worker protocol could be offered for expensive/untrusted work, but that is a separate design decision. The current Python prototype's subprocess limits provide timeout/error containment, **not security isolation**.

## Review-build layout

```text
Flint.qml / ui/          QML presentation, navigation, IPC transport
manifest.json           Omarchy menu replacement manifest
BarWidget.qml           Omarchy bar entry point
shell.qml / bin/flint    Separate review harness only
flint/                  Python transport, registry, ranking, config, effects
extensions/*/           Nine bundled extension manifests and implementations
examples/hello/         Experimental external JSON-provider example
tests/                  Backend and live review-UI checks
```

This is a behavior reference, not a commitment to maintaining two extension ecosystems.
