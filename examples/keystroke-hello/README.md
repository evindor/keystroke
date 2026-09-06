# Keystroke Hello

The smallest possible community provider for [Keystroke](../../README.md): one `manifest.json` with the `x-keystroke` marker and one `Service.qml` exposing a `provider`. For a complete, published extension with settings, a scoped screen, a service that outlives the palette and unit tests, start from [keystroke-timer](https://github.com/evindor/keystroke-timer) instead.

Try it locally (Omarchy refuses symlinks inside plugin folders, so copy):

```sh
cp -r examples/keystroke-hello ~/.config/omarchy/plugins/example.keystroke-hello
omarchy-shell shell rescanPlugins && omarchy plugin enable example.keystroke-hello
```

Then turn it on under Extensions → Hello → Enabled (community providers installed by hand start off) and type `hello world`. Remove it with `omarchy plugin remove example.keystroke-hello`. See [docs/providers.md](../../docs/providers.md) for the contract and [AGENTS.md](../../AGENTS.md) for the guide.
