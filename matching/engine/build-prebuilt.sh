#!/usr/bin/env bash
# Build the static engine binary that ships in matching/bin, with a manifest
# naming the machine architecture and the source fingerprint it was built from.
# helpers/matching-start.py uses the binary only while both still match, so an
# engine change without a rebuild falls back to a local cargo build, and
# tests/matching_engine_check.py fails until this script is run again.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET="${CARGO_BUILD_TARGET:-x86_64-unknown-linux-gnu}"
OUT="$ROOT/matching/bin"
mkdir -p "$OUT"
# +crt-static: no glibc version dependency; every crate is pure Rust.
RUSTFLAGS="-C target-feature=+crt-static" cargo build --release --locked --quiet \
  --manifest-path "$ROOT/matching/engine/Cargo.toml" --target "$TARGET" \
  --target-dir "${CARGO_TARGET_DIR:-$ROOT/matching/engine/target}"
install -m 755 "${CARGO_TARGET_DIR:-$ROOT/matching/engine/target}/$TARGET/release/keystroke-matching" "$OUT/keystroke-matching"
python3 - "$OUT/keystroke-matching" "$TARGET" "$(python3 "$ROOT/helpers/matching-start.py" --engine-fingerprint)" <<'PY'
import hashlib, json, platform, sys
binary, target, source = sys.argv[1:4]
json.dump({"machine": platform.machine(), "target": target, "source": source,
           "sha256": hashlib.sha256(open(binary, "rb").read()).hexdigest(),
           "rustc": __import__("subprocess").run(["rustc", "--version"], capture_output=True, text=True).stdout.strip()},
          open(binary + ".json", "w"), indent=1, sort_keys=True)
print(open(binary + ".json").read())
PY
