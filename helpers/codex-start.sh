#!/usr/bin/env bash
# Keystroke owns this process. Do not attach to the desktop application's server.
set -euo pipefail
minimum=0.159.2
actual="$(codex --version 2>/dev/null || true)"
IFS=. read -r min_major min_minor min_patch <<< "$minimum"
compatible=false
# Accept stable releases only; compare components numerically (not as strings).
if [[ "$actual" =~ ^codex-cli\ ([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  major=$((10#${BASH_REMATCH[1]}))
  minor=$((10#${BASH_REMATCH[2]}))
  patch=$((10#${BASH_REMATCH[3]}))
  if (( major > min_major || (major == min_major && (minor > min_minor || (minor == min_minor && patch >= min_patch))) )); then
    compatible=true
  fi
fi
if [[ "$compatible" != true ]]; then
  echo "Keystroke requires codex-cli $minimum or newer; found ${actual:-no Codex CLI}." >&2
  exit 65
fi
mkdir -p "$HOME/.local/state/keystroke/questions"
exec codex app-server --stdio --enable fast_mode --disable hooks --disable apps --disable plugins
