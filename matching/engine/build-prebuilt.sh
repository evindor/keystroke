#!/usr/bin/env bash
# Build the static engine binary that ships in matching/bin, inside a
# digest-pinned container, so anyone can rebuild it byte for byte from the
# checked-in source and lockfile:
#
#   matching/engine/build-prebuilt.sh            rebuild and refresh matching/bin
#   matching/engine/build-prebuilt.sh --check    rebuild and compare, fail on any difference
#   ... --output DIR                             also keep the fresh build and its manifest in DIR
#
# The manifest next to the binary (keystroke-matching.json) names the target,
# the source fingerprint it was built from, the image and the digest.
# helpers/matching-start.py uses the binary only while machine and source still
# match, so an engine change without a rebuild falls back to a local cargo build,
# and tests/matching_engine_check.py fails until this script is run again.
# .github/workflows/engine.yml runs `--check` on every push and attests the
# committed digest on main and release tags. docs/engine-provenance.md explains
# how to verify both.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Every input that decides the bytes is pinned here: the image by digest (which
# fixes rustc, cargo and rust-lld), the crates by Cargo.lock (--locked), the
# target. The link uses the toolchain's own rust-lld and the crt objects that
# ship with the musl target, never the image's gcc or binutils.
IMAGE="docker.io/library/rust:1.98.1-alpine3.22@sha256:b42001307cfa41fcf31bd1530dfc7d712104b61c8e2150b2f02e75415f3d501a"
TARGET="x86_64-unknown-linux-musl"
OUT="$ROOT/matching/bin"

check=false
keep=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) check=true ;;
    --output) keep="$(mkdir -p "$2" && cd "$2" && pwd)"; shift ;;
    *) echo "usage: $0 [--check] [--output DIR]" >&2; exit 2 ;;
  esac
  shift
done

runtime="${CONTAINER_RUNTIME:-}"
if [[ -z $runtime ]]; then
  for candidate in docker podman; do
    if command -v "$candidate" >/dev/null 2>&1; then runtime=$candidate; break; fi
  done
fi
[[ -n $runtime ]] || { echo "build-prebuilt: docker or podman is required (set CONTAINER_RUNTIME to choose)" >&2; exit 1; }

stage="$(mktemp -d "${TMPDIR:-/tmp}/keystroke-engine.XXXXXX")"
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/out"

# The build runs as the invoking user so the output is owned by them. Cargo's
# home and target live in the container's own /tmp: a fresh registry checkout
# every time, and its path is remapped so no build path reaches the binary.
"$runtime" run --rm --user "$(id -u):$(id -g)" \
  -e HOME=/tmp/home -e CARGO_HOME=/tmp/cargo -e CARGO_INCREMENTAL=0 -e SOURCE_DATE_EPOCH=1 \
  -e RUSTFLAGS="-C target-feature=+crt-static -C linker=rust-lld -C link-self-contained=yes --remap-path-prefix=/tmp/cargo/registry/src=/cargo/registry/src" \
  -e TARGET="$TARGET" \
  -v "$ROOT/matching/engine:/src/engine:ro" -v "$stage/out:/out" \
  "$IMAGE" sh -euc '
    cargo build --release --locked --quiet --manifest-path /src/engine/Cargo.toml --target "$TARGET" --target-dir /tmp/target
    cp /tmp/target/"$TARGET"/release/keystroke-matching /out/keystroke-matching
    rustc --version > /out/rustc
  '
chmod 755 "$stage/out/keystroke-matching"

python3 - "$stage/out/keystroke-matching" "$TARGET" "$IMAGE" "$(python3 "$ROOT/helpers/matching-start.py" --engine-fingerprint)" <<'PY'
import hashlib, json, pathlib, sys
binary, target, image, source = sys.argv[1:5]
path = pathlib.Path(binary)
json.dump({"machine": target.split("-")[0], "target": target, "source": source, "image": image,
           "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
           "rustc": path.with_name("rustc").read_text().strip()},
          open(binary + ".json", "w"), indent=1, sort_keys=True)
PY
rm -f "$stage/out/rustc"

if [[ -n $keep ]]; then
  cp "$stage/out/keystroke-matching" "$stage/out/keystroke-matching.json" "$keep/"
fi

if $check; then
  status=0
  cmp -s "$stage/out/keystroke-matching" "$OUT/keystroke-matching" || { echo "build-prebuilt: matching/bin/keystroke-matching differs from the container build" >&2; status=1; }
  cmp -s "$stage/out/keystroke-matching.json" "$OUT/keystroke-matching.json" || { echo "build-prebuilt: matching/bin/keystroke-matching.json differs from the container build" >&2; diff "$OUT/keystroke-matching.json" "$stage/out/keystroke-matching.json" >&2 || true; status=1; }
  [[ $status -eq 0 ]] && echo "build-prebuilt: matching/bin/keystroke-matching reproduced byte for byte"
  sha256sum "$stage/out/keystroke-matching"
  exit $status
fi

mkdir -p "$OUT"
install -m 755 "$stage/out/keystroke-matching" "$OUT/keystroke-matching"
cp "$stage/out/keystroke-matching.json" "$OUT/keystroke-matching.json"
cat "$OUT/keystroke-matching.json"
