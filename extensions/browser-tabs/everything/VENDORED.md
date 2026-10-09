# Vendored: Everything backend

These files come from [Everything](https://github.com/brianblakely/omarchy-everything)
by Brian Blakely, MIT (see `LICENSE` in this folder), at commit
`32572dfa8f3e1aa2a8f8bd396100f3592077d611`:

- `__init__.py`, `atspi_runtime.py`, `commands.py`, `model.py`, `processes.py`,
  `server.py`: unchanged.
- `discovery.py`: imports and starts only the Hyprland and AT-SPI providers.
- `providers/__init__.py`: exports only those two.
- `providers/atspi.py`, `providers/base.py`, `providers/hyprland.py`: unchanged.

`bin/tabs-helper.py` is Everything's `helper/everything_helper.py` with its
help text renamed. To update, copy the same files from a newer Everything
commit and reapply the two small changes above.
