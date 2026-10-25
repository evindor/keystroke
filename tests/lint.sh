#!/usr/bin/env bash
# qmllint with the `qs` module (Omarchy's shell Commons/Ui) made importable.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHIM="$(mktemp -d)"
trap 'rm -rf "$SHIM"' EXIT
ln -s "${OMARCHY_PATH:-/usr/share/omarchy}/shell" "$SHIM/qs"
status=0
while IFS= read -r file; do
  # The optional 4.5 bridge is intentionally never compiled on older shells.
  if [[ $file == "$ROOT/i18n/OmarchyTranslations.qml" && ! -f ${OMARCHY_PATH:-/usr/share/omarchy}/shell/Commons/Translations.qml ]]; then continue; fi
  if ! /usr/lib/qt6/bin/qmllint -I /usr/lib/qt6/qml -I "$SHIM" "$file"; then status=1; fi
done < <(rg --files "$ROOT" -g '*.qml' -g '!**/tests/**' | sort)
exit $status
