#!/usr/bin/env bash
# Keystroke owns this process. Do not attach to the desktop application's server.
set -euo pipefail
expected=0.153.2
actual="$(codex --version 2>/dev/null || true)"
if [[ "$actual" != "codex-cli $expected" ]]; then
  echo "Keystroke requires codex-cli $expected; found ${actual:-no Codex CLI}." >&2
  exit 65
fi
mkdir -p "$HOME/.local/state/keystroke/questions"
exec codex app-server --stdio --enable fast_mode --disable hooks --disable apps --disable plugins
