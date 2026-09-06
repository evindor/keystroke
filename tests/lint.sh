#!/usr/bin/env bash
# qmllint with the `qs` module (Omarchy's shell Commons/Ui) made importable.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHIM="$(mktemp -d)"
trap 'rm -rf "$SHIM"' EXIT
ln -s "${OMARCHY_PATH:-/usr/share/omarchy}/shell" "$SHIM/qs"
status=0
while IFS= read -r file; do
  if ! /usr/lib/qt6/bin/qmllint -I /usr/lib/qt6/qml -I "$SHIM" "$file"; then status=1; fi
done < <(rg --files "$ROOT" -g '*.qml' -g '!**/tests/**' | sort)
exit $status
