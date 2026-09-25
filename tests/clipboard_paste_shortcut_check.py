#!/usr/bin/env python3
"""Check paste shortcut selection without sending keys to the desktop."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="keystroke-paste-") as temp:
    work = Path(temp)
    commands = work / "commands"
    commands.mkdir()
    (commands / "hyprctl").write_text('#!/bin/sh\nprintf "%s" "$TEST_WINDOW"\n')
    (commands / "wtype").write_text('#!/bin/sh\nprintf "%s\\n" "$*" > "$TEST_WTYPE"\n')
    (commands / "wl-copy").write_text('#!/bin/sh\ncat > "$TEST_COPY"\n')
    for command in commands.iterdir():
        command.chmod(0o755)
    applications = work / "applications"
    applications.mkdir()
    (applications / "example-terminal.desktop").write_text(
        "[Desktop Entry]\nStartupWMClass=example-terminal\nCategories=System;TerminalEmulator;\n"
    )
    source = work / "image.png"
    source.write_bytes(b"image bytes")
    env = dict(os.environ, PATH=str(commands) + ":" + os.environ["PATH"],
               XDG_DATA_HOME=str(work), XDG_DATA_DIRS=str(work),
               TEST_WTYPE=str(work / "keys"), TEST_COPY=str(work / "copied"))

    def check(window, expected, args=()):
        env["TEST_WINDOW"] = json.dumps(window)
        subprocess.run([str(root / "bin/keystroke-paste"), *args], env=env, check=True)
        assert (work / "keys").read_text().strip() == expected

    check({"class": "ordinary-app", "tags": []}, "-M ctrl -k v -m ctrl")
    check({"class": "tagged-app", "tags": ["terminal*"]}, "-M ctrl -M shift -k v -m shift -m ctrl")
    check({"class": "example-terminal", "tags": []}, "-M ctrl -M shift -k v -m shift -m ctrl")
    check({"class": "ordinary-app", "tags": []}, "-M shift -k Insert -m shift", ["--shift-insert"])
    check({"class": "example-terminal", "tags": []}, "-M ctrl -M shift -k v -m shift -m ctrl",
          ["--file", "image/png", str(source)])
    assert (work / "copied").read_bytes() == b"image bytes"
    print("PASS: paste shortcut selection, override, and image copy")
