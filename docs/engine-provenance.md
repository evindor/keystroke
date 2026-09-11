# Matching engine provenance

Keystroke ships one compiled executable, `matching/bin/keystroke-matching`, the
Smart Match engine (`matching/engine`, Rust). It is committed so that users
need neither a Rust toolchain nor a build step. This note shows how anyone can
confirm that the committed bytes come from the committed source, without
trusting the person who committed them.

## How the binary is built

`matching/engine/build-prebuilt.sh` builds it inside a container pinned by
digest, and every input that decides the bytes is fixed:

- Image: `docker.io/library/rust:1.98.1-alpine3.22@sha256:b42001307cfa41fcf31bd1530dfc7d712104b61c8e2150b2f02e75415f3d501a`.
  The digest fixes rustc, cargo and rust-lld.
- Crates: `matching/engine/Cargo.lock`, enforced with `cargo build --locked`.
  Four direct dependencies (serde, serde_json, unicode-normalization,
  unicode_categories), nothing with a build script that reaches the network.
- Target: `x86_64-unknown-linux-musl`, static-pie, `+crt-static`. The link uses
  the toolchain's own `rust-lld` and the crt objects that ship with the musl
  target (`-C link-self-contained=yes`), so the image's gcc and binutils do not
  take part.
- Paths: cargo's registry is checked out fresh in the container's `/tmp` and
  remapped with `--remap-path-prefix`; the crate source is mounted read-only at
  `/src/engine`. `CARGO_INCREMENTAL=0`, `SOURCE_DATE_EPOCH=1`.
- Release profile from `Cargo.toml`: `opt-level = 3`, `lto = true`,
  `codegen-units = 1`, `panic = "abort"`, `strip = true`.

The manifest beside the binary, `matching/bin/keystroke-matching.json`, records
the image, target, machine, rustc version, the SHA-256 of the binary and the
fingerprint of the engine source it was built from (`helpers/matching-start.py
--engine-fingerprint`: SHA-256 over `Cargo.toml`, `Cargo.lock` and `src/*.rs`).
The start script uses the binary only while machine and fingerprint match the
checkout, and `tests/matching_engine_check.py` fails when they do not.

There is deliberately no `rust-toolchain.toml`: the container pins the
toolchain for the shipped binary, and the fallback `cargo build` that
`helpers/matching-start.py` runs on other architectures must work with whatever
Rust the user has, without pulling a second toolchain.

## Reproduce it yourself

With docker or podman, from any checkout:

```sh
matching/engine/build-prebuilt.sh --check
```

This rebuilds the engine in the pinned image and exits non-zero unless the
result is byte-identical to `matching/bin/keystroke-matching` and the
regenerated manifest equals `matching/bin/keystroke-matching.json`. Add
`--output DIR` to keep the fresh build for inspection. The build takes about a
minute, most of it pulling the image.

## What CI does

`.github/workflows/engine.yml` runs that same `--check` on every push to `main`
and `dev`, every pull request and every `v*` tag, and uploads the fresh build as
a workflow artifact. On pushes to `main` and on release tags, after the
comparison passed, it records a GitHub build provenance attestation (SLSA
provenance v1, signed through Sigstore) for the committed file. Both actions in
the workflow are pinned to full commit SHAs.

The attestation binds the binary's digest to the exact source commit and the
workflow that produced the claim. To check it for a given commit:

```sh
gh attestation verify matching/bin/keystroke-matching \
  --repo evindor/keystroke \
  --signer-workflow evindor/keystroke/.github/workflows/engine.yml \
  --source-digest <full commit SHA>
```

`--source-digest` is the commit under review. Verification fails if no
attestation for this file's digest was produced by that workflow at that commit.
`gh attestation verify --help` describes offline verification from a downloaded
bundle.

## Updating the binary

After editing anything under `matching/engine`, run `bin/keystroke engine` (the
same script without `--check`) and commit the binary together with the source
and the refreshed manifest. To move to a newer Rust, change `IMAGE` in the
script to the new tag and digest (`docker buildx imagetools inspect` or the
Docker Hub tag page shows the digest), rebuild, and commit all three.
