# Keystroke Hello

The smallest possible community provider for [Keystroke](../../README.md). Install it like any Omarchy plugin:

```sh
omarchy plugin add https://example.invalid/keystroke-hello.git --enable   # from a git repo
# or, for local testing:
cp -r examples/keystroke-hello ~/.config/omarchy/plugins/example.keystroke-hello
omarchy-shell shell rescanPlugins && omarchy plugin enable example.keystroke-hello
```

Then turn it on once in Keystroke → Settings → Hello (community providers start disabled) and type `hello world`. See [docs/providers.md](../../docs/providers.md) for the contract.
