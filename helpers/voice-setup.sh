#!/usr/bin/env bash
# Sets this machine up for Keystroke's voice path, and can be run again any
# time to update one piece:
#
#   1. voxtype 1.1 with the live transcript mirror, built from Keystroke's
#      fork (github.com/evindor/voxtype, branch feature/live-transcript-file,
#      proposed upstream) with whisper on Vulkan, installed under
#      ~/.local/share/keystroke/voxtype and made the daemon through a systemd
#      drop-in. The packaged voxtype stays where it is; removing the drop-in
#      restores it.
#   2. voxtype's config switched to streaming (`[whisper] streaming = true`
#      and a `[streaming]` section tuned for short commands).
#   3. llama-server (llama.cpp, Vulkan build) with Gemma 4 E2B Q4_0 as the
#      keystroke-llm user service on 127.0.0.1:18781.
#
# Nothing here needs root. Rust (rustup) and a cmake are found on the PATH or
# under ~/.local/share/keystroke/toolchain/env.sh, which is where a root-free
# toolchain (rustup, cmake tarball, Vulkan headers) lives on the machine this
# was developed on.
set -euo pipefail

KS="$HOME/.local/share/keystroke"
SRC="${KEYSTROKE_VOXTYPE_SRC:-$HOME/Documents/ChatGPT/voxtype}"
FORK_URL="https://github.com/evindor/voxtype.git"
FORK_BRANCH="feature/live-transcript-file"
LLAMA_TAG="${KEYSTROKE_LLAMA_TAG:-b10821}"
LLAMA_URL="https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/llama-$LLAMA_TAG-bin-ubuntu-vulkan-x64.tar.gz"
MODEL_REPO="https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/main"
MODEL="gemma-4-E2B-it-Q4_0.gguf"
MMPROJ="mmproj-gemma-4-E2B-it-Q8_0.gguf"
UNIT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/keystroke-llm.service"
UNIT_DIR="$HOME/.config/systemd/user"
DROPIN="$UNIT_DIR/voxtype.service.d/keystroke.conf"
VOXTYPE="$KS/voxtype/voxtype"
ENDPOINT="http://127.0.0.1:18781"

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
  if [[ -x $KS/llama/current/llama-server ]]; then note "llama-server: $KS/llama/current ($(readlink "$KS/llama/current" 2>/dev/null))"; else note "llama-server: not installed"; fi
  for f in "$MODEL" "$MMPROJ"; do if [[ -f $KS/models/$f ]]; then note "model: $f ($(du -h "$KS/models/$f" | cut -f1))"; else note "model: $f missing"; fi; done
  note "keystroke-llm.service: $(systemctl --user is-active keystroke-llm 2>/dev/null || true) · health: $(curl -s -m 2 "$ENDPOINT/health" 2>/dev/null || echo unreachable)"
  ls "$XDG_RUNTIME_DIR/voxtype/" 2>/dev/null | tr '\n' ' ' | sed 's/^/  runtime: /'; echo
}

if [[ ${1:-} == --status ]]; then status; exit 0; fi

mkdir -p "$KS/voxtype" "$KS/llama" "$KS/models" "$UNIT_DIR/voxtype.service.d"

# ------------------------------------------------------------- 1. voxtype
say "voxtype (Keystroke build)"
[[ -f $KS/toolchain/env.sh ]] && source "$KS/toolchain/env.sh"
if ! command -v cargo >/dev/null; then
  note "cargo not found: install rustup (https://rustup.rs) or pacman -S rustup && rustup default stable"
elif ! command -v cmake >/dev/null; then
  note "cmake not found: pacman -S cmake (whisper.cpp builds with it), or drop a cmake under $KS/toolchain"
else
  if [[ ! -d $SRC/.git ]]; then
    note "cloning $FORK_URL ($FORK_BRANCH) into $SRC"
    git clone -q --branch "$FORK_BRANCH" "$FORK_URL" "$SRC"
  fi
  note "building in $SRC (whisper.cpp + Vulkan; several minutes the first time)"
  (cd "$SRC" && cargo build --release --features gpu-vulkan --bin voxtype --bin voxtype-audio-bridge)
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

# Sliding-window streaming, tuned by Keystroke for short spoken commands on a
# GPU (voxtype setup gpu --enable): a re-transcription every half second, the
# first one after half a second of audio, every stable word committed, and a
# 12 s window so a tick never grows past the interval (a saturated 29 s
# window makes the stop drain for a minute).
[streaming]
interval_secs = 0.5
min_audio_secs = 0.5
partial_min_words = 1
max_buffer_secs = 12
"""
tmp = path + ".keystroke.tmp"
open(tmp, "w").write(text)
os.replace(tmp, path)
PY
  systemctl --user daemon-reload
  systemctl --user restart voxtype
  note "voxtype.service now runs $VOXTYPE with whisper streaming on"
fi

# --------------------------------------------------------- 2. llama-server
say "llama-server ($LLAMA_TAG, Vulkan)"
if [[ ! -x $KS/llama/$LLAMA_TAG/llama-server ]]; then
  note "downloading $LLAMA_URL"
  tmp="$(mktemp -d "$KS/llama/.dl.XXXXXX")"
  curl -fL --progress-bar -o "$tmp/llama.tgz" "$LLAMA_URL"
  tar -xzf "$tmp/llama.tgz" -C "$tmp"
  inner="$(find "$tmp" -maxdepth 2 -name llama-server -printf '%h\n' | head -1)"
  rm -rf "$KS/llama/$LLAMA_TAG"
  mv "$inner" "$KS/llama/$LLAMA_TAG"
  rm -rf "$tmp"
fi
ln -sfn "$LLAMA_TAG" "$KS/llama/current"
note "$("$KS/llama/current/llama-server" --version 2>&1 | head -1)"

say "Gemma 4 E2B (Q4_0 weights + Q8_0 projector, ~3.3 GB)"
for f in "$MODEL" "$MMPROJ"; do
  if [[ ! -f $KS/models/$f ]]; then
    note "downloading $f"
    curl -fL --progress-bar -C - -o "$KS/models/$f.part" "$MODEL_REPO/$f"
    mv -f "$KS/models/$f.part" "$KS/models/$f"
  fi
done

install -m 644 "$UNIT_SRC" "$UNIT_DIR/keystroke-llm.service"
systemctl --user daemon-reload
systemctl --user enable --now keystroke-llm >/dev/null
for _ in $(seq 1 120); do curl -s -m 1 "$ENDPOINT/health" 2>/dev/null | grep -q '"ok"' && break; sleep 1; done
note "keystroke-llm.service: $(systemctl --user is-active keystroke-llm) · $(curl -s -m 2 "$ENDPOINT/health" 2>/dev/null || echo 'not answering yet')"

echo
status
echo
echo "Keystroke picks the build under $KS/voxtype up on its next open (Settings › Voice shows the version and the assistant)."
echo "If the palette was already loaded, run: omarchy-restart-shell"
