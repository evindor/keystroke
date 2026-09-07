#!/usr/bin/env bash
# Sets this machine up for Keystroke's voice path, and can be run again any
# time to update one piece:
#
#   1. voxtype 1.1 with the live transcript mirror, built from Keystroke's
#      fork (github.com/evindor/voxtype, proposed upstream) at the exact
#      commit FORK_COMMIT below, with whisper on Vulkan, installed under
#      ~/.local/share/keystroke/voxtype and made the daemon through a systemd
#      drop-in. The packaged voxtype stays where it is; removing the drop-in
#      restores it.
#   2. voxtype's config switched to streaming (`[whisper] streaming = true`
#      and a `[streaming]` section tuned for short commands).
#
# Nothing here needs root. Rust (rustup) and a cmake are found on the PATH or
# under ~/.local/share/keystroke/toolchain/env.sh, which is where a root-free
# toolchain (rustup, cmake tarball, Vulkan headers) lives on the machine this
# was developed on.
set -euo pipefail

KS="$HOME/.local/share/keystroke"
SRC="${KEYSTROKE_VOXTYPE_SRC:-$HOME/Documents/ChatGPT/voxtype}"
FORK_URL="https://github.com/evindor/voxtype.git"
# The one commit this script builds: the source is fetched and checked out
# detached at exactly this revision (where feature/live-transcript-file
# pointed when it was reviewed), so what gets compiled is what was reviewed,
# whatever the branch points at later. helpers/voxtype-full-request.patch is
# written against it; bump the two together.
FORK_COMMIT="60082b10e61af51b63b97ce86254686aadb8af88"
HELPERS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
DROPIN="$UNIT_DIR/voxtype.service.d/keystroke.conf"
VOXTYPE="$KS/voxtype/voxtype"

say() { printf '\033[1m» %s\033[0m\n' "$*"; }
note() { printf '  %s\n' "$*"; }

status() {
  echo "Keystroke voice status"
  if [[ -x $VOXTYPE ]]; then note "voxtype: $("$VOXTYPE" --version 2>/dev/null) at $VOXTYPE"; else note "voxtype: Keystroke build not installed (packaged: $(command -v voxtype || echo none))"; fi
  if [[ -f $DROPIN ]]; then note "voxtype.service: drop-in present ($(systemctl --user is-active voxtype 2>/dev/null))"; else note "voxtype.service: stock ExecStart ($(systemctl --user is-active voxtype 2>/dev/null))"; fi
  local cfg="$HOME/.config/voxtype/config.toml"
  if [[ -f $cfg ]]; then
    note "streaming: $(awk '/^\[whisper\]/{w=1;next} /^\[/{w=0} w && /^streaming *=/{print "whisper." $0}' "$cfg" | tr -d ' ' | head -1) $(awk '/^\[streaming\]/{s=1;next} /^\[/{s=0} s && /=/{printf "%s ", $0}' "$cfg" | tr -d ' ')"
  fi
  if [[ -x $VOXTYPE ]]; then note "accel: $("$VOXTYPE" info accel 2>/dev/null | sed -n 's/^ *Backend: *//p' | head -1)"; fi
  ls "$XDG_RUNTIME_DIR/voxtype/" 2>/dev/null | tr '\n' ' ' | sed 's/^/  runtime: /'; echo
}

# Fetches the fork into $SRC without checking anything out; the build step
# below checks out FORK_COMMIT detached, so nothing is built from a moving
# branch. An existing checkout (KEYSTROKE_VOXTYPE_SRC) is used as is and gets
# the same detached checkout; local edits that conflict with it stop the build.
pinned_source() {
  if [[ ! $FORK_COMMIT =~ ^[0-9a-f]{40}$ ]]; then
    note "FORK_COMMIT is not a full 40-character commit SHA; refusing to fetch source"
    exit 1
  fi
  if [[ ! -d $SRC/.git ]]; then
    note "fetching $FORK_URL into $SRC (built at $FORK_COMMIT)"
    git clone -q --no-checkout "$FORK_URL" "$SRC"
  fi
  if ! git -C "$SRC" cat-file -e "$FORK_COMMIT^{commit}" 2>/dev/null; then
    note "$SRC does not contain the pinned commit $FORK_COMMIT; fetch it there or remove the folder"
    exit 1
  fi
}

# The whole-request revision on top of the pinned commit. Applied once; a
# checkout that already carries it is left alone.
apply_revision_patch() {
  local revision_patch="$HELPERS/voxtype-full-request.patch"
  if git -C "$SRC" apply --reverse --check "$revision_patch" 2>/dev/null; then
    note "whole-request revision patch already applied"
  elif git -C "$SRC" apply --check "$revision_patch"; then
    git -C "$SRC" apply "$revision_patch"
  else
    note "Whole-request patch does not match this voxtype checkout; resolve it before building."
    return 1
  fi
}

if [[ ${1:-} == --status ]]; then status; exit 0; fi

mkdir -p "$KS/voxtype" "$UNIT_DIR/voxtype.service.d"

# ------------------------------------------------------------- 1. voxtype
say "voxtype (Keystroke build)"
[[ -f $KS/toolchain/env.sh ]] && source "$KS/toolchain/env.sh"
if ! command -v cargo >/dev/null; then
  note "cargo not found: install rustup (https://rustup.rs) or pacman -S rustup && rustup default stable"
elif ! command -v cmake >/dev/null; then
  note "cmake not found: pacman -S cmake (whisper.cpp builds with it), or drop a cmake under $KS/toolchain"
else
  pinned_source
  note "building in $SRC at $FORK_COMMIT (whisper.cpp + Vulkan; several minutes the first time)"
  # One fail-closed chain: the exact commit (spelled out, same as FORK_COMMIT)
  # is checked out detached, then patched, then built; any failure stops here.
  git -C "$SRC" checkout -q --detach 60082b10e61af51b63b97ce86254686aadb8af88 && apply_revision_patch && (cd "$SRC" && cargo build --release --features gpu-vulkan --bin voxtype --bin voxtype-audio-bridge) || { note "voxtype build at the pinned commit failed; nothing installed"; exit 1; }
  install -m 755 "$SRC/target/release/voxtype" "$KS/voxtype/voxtype.new"
  install -m 755 "$SRC/target/release/voxtype-audio-bridge" "$KS/voxtype/voxtype-audio-bridge"
  mv -f "$KS/voxtype/voxtype.new" "$VOXTYPE"
  note "installed $("$VOXTYPE" --version)"
fi

if [[ -x $VOXTYPE ]]; then
  cat > "$DROPIN" <<EOF
# Written by Keystroke (bin/keystroke voice-setup): run Keystroke's voxtype
# build instead of the packaged one. Delete this file and run
# systemctl --user daemon-reload && systemctl --user restart voxtype to go back.
[Service]
ExecStart=
ExecStart=$VOXTYPE daemon
EOF
  # Streaming is what makes the live transcript exist; the interval and the
  # minimum audio are tuned for one-line commands on a GPU. The daemon reads
  # these keys but `voxtype config set` does not list them yet, so the TOML
  # is edited in place: `streaming = true` inside [whisper], and a
  # [streaming] section appended once (an existing one is left alone).
  python3 - "$HOME/.config/voxtype/config.toml" <<'PY'
import re, sys, os
path = sys.argv[1]
text = open(path).read() if os.path.exists(path) else 'engine = "whisper"\n'
lines = text.split("\n")
out, section, done = [], "", False
for line in lines:
    m = re.match(r"^\s*\[([^\]]+)\]", line)
    if m:
        if section == "whisper" and not done:
            out.append("streaming = true")
            done = True
        section = m.group(1).strip()
        out.append(line)
        continue
    if section == "whisper" and re.match(r"^\s*streaming\s*=", line):
        out.append("streaming = true")
        done = True
        continue
    out.append(line)
if not done:
    if section == "whisper":
        out.append("streaming = true")
    else:
        out += ["", "[whisper]", "streaming = true"]
text = "\n".join(out)
if not re.search(r"^\s*\[streaming\]", text, re.M):
    text = text.rstrip("\n") + """

# Begin with a full second of context; revise every 0.8 s. Keystroke file
# sessions use whole-request snapshots through the recording duration cap.
# Ordinary live typing keeps a 12 s rolling window and four revisable words.
[streaming]
interval_secs = 0.8
min_audio_secs = 1.0
partial_min_words = 1
max_buffer_secs = 12
revision_mode = true
"""
tmp = path + ".keystroke.tmp"
open(tmp, "w").write(text)
os.replace(tmp, path)
PY
  systemctl --user daemon-reload
  systemctl --user restart voxtype
  note "voxtype.service now runs $VOXTYPE with whisper streaming on"
fi


note "Vulkan speech setup complete; no local language model is installed."
