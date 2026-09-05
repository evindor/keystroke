# Experimental review-build extension API

This documents the Python-host prototype. The Omarchy-native provider contract is pending review; do not treat this as a stable public API.

Bundled extensions are directories in `extensions/`, each with `manifest.json` and `extension.py`. They implement `async query(ctx) -> list[Result]`. The context includes the query, scope, manifest-generated settings, native app metadata, a per-extension cache and the installed Omarchy path.

External providers live under `~/.config/flint/extensions/<name>/`. Discovery never executes their code. They are disabled until enabled explicitly in Flint Settings. The [hello example](../examples/hello/) is a minimal provider:

```sh
mkdir -p ~/.config/flint/extensions
cp -r examples/hello ~/.config/flint/extensions/hello
./bin/flint stop
./bin/flint settings
```

Enable Hello Extension, then search `hello world`.

An external manifest includes a namespaced ID, `apiVersion: 1`, an argv `command`, optional prefix and minimum query length, settings, and declared permissions. `./` arguments resolve against the extension directory. No shell interpolation is used to launch a provider. The provider receives one JSON object on stdin, responds with one JSON object on stdout, and exits:

```json
{"apiVersion":1,"type":"query","query":"hello world","scope":"","settings":{"greeting":"Hello"}}
```

```json
{"rows":[{"id":"hello","title":"Hello, world!","subtitle":"Copy greeting","icon":"✳","score":100,"action":{"type":"copy","text":"Hello, world!"}}]}
```

Rows may supply `preview`, `previewLabel`, `previewDetail`, `previewImage`, `swatch`, `iconName`, `accessory`, `tint`, `section` and `verb`. Returned IDs should remain stable for a logical result; the UI uses them to update existing delegates without blinking. Set `disabled: true` with a `noop` action for incomplete input. Set `remember: true` only on a stable app/command result to opt into local frecency; never use query text or clipboard contents as its ID. The host supplies an opaque, generation-bound activation token to the UI; action payloads remain in the host.

Effects: `exec` with literal argv, `copy`, HTTP(S) `url`, `navigate`, and `compound`. A `shell` effect exists for trusted scripts; never interpolate query text into it. `setting` and `edit` are reserved for bundled settings integration. A `confirm` string on the top-level action requests confirmation before activation.

Settings support `boolean`, `enum`, `number`, and `string`. Types, enum values, numeric ranges and optional `integer` constraints are validated. The current string editor is intentionally small; full forms and custom extension views remain future work.

Queries are cancelled when superseded. External processes default to an 800 ms deadline, capped at 3 seconds, with 1 MiB stdout limits. Failures are reported without removing other extensions' results. Hidden palettes do not poll or launch queries.

Declared permissions are host-side effect validation only. External executables and bundled code still have the user's full account permissions; they can bypass this API. There is no filesystem, process or network sandbox. Prefixes and timeouts are performance controls, not security boundaries.
