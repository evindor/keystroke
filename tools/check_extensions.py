#!/usr/bin/env python3
"""Check every extension folder the way a reviewer would, before a pull request.

For each folder under extensions/ (or each folder given on the command line):
the folder name is a valid id that no bundled provider uses, extension.json is
complete and points at files inside the folder, nothing is a symlink, no file
is named manifest.json (that would make it look like an Omarchy plugin), the
QML never imports from outside the folder, README.md exists, a declared setup
script is executable, qmllint passes on the extension's QML, and its
tests/tst_*.qml pass under qmltestrunner. Qt tools are required unless
--qt auto is given (then they are used when present and reported when not).
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
RESERVED = {"palette", "dmenu", "matching", "voice"}
QT_BIN = Path("/usr/lib/qt6/bin")


def bundled_ids():
    ids = set(RESERVED)
    for qml in (ROOT / "providers").glob("*.qml"):
        m = re.search(r'^\s*id:\s*"([a-z0-9-]+)"', qml.read_text(), re.M)
        if m:
            ids.add(m.group(1))
    return ids


def inside(rel):
    return rel and not rel.startswith("/") and ".." not in rel.split("/") and "" not in rel.split("/")


def tool(name):
    candidate = QT_BIN / name
    if candidate.exists():
        return str(candidate)
    return shutil.which(name)


def check(folder, qt_mode, reserved):
    problems = []
    fail = problems.append
    folder = folder.resolve()
    name = folder.name
    if not ID_RE.match(name):
        fail("folder name must be lowercase letters, digits and dashes")
    if name in reserved:
        fail(f"id {name} belongs to a bundled provider")
    manifest = folder / "extension.json"
    if not manifest.is_file():
        fail("extension.json is missing")
        return problems
    try:
        m = json.loads(manifest.read_text())
    except ValueError as e:
        fail(f"extension.json is not valid JSON: {e}")
        return problems
    if not isinstance(m, dict):
        fail("extension.json must be an object")
        return problems
    for field in ("name", "version", "author", "description"):
        if not isinstance(m.get(field), str) or not m[field].strip():
            fail(f"extension.json needs a non-empty {field}")
    if m.get("apiVersion") != 1:
        fail("extension.json must declare apiVersion 1")
    if "icon" in m and not isinstance(m["icon"], str):
        fail("icon must be a string (a glyph from Omarchy's icon font)")
    if "color" in m and not re.match(r"^#[0-9a-fA-F]{6}$", str(m["color"])):
        fail("color must be a #rrggbb value")
    if "homepage" in m and not str(m["homepage"]).startswith("https://"):
        fail("homepage must be an https URL")
    entry = m.get("entry", "Service.qml")
    if not isinstance(entry, str) or not inside(entry) or not entry.endswith(".qml"):
        fail("entry must be a .qml file inside the folder")
    elif not (folder / entry).is_file():
        fail(f"entry {entry} does not exist")
    setup = m.get("setup")
    if setup is not None:
        run = setup.get("run") if isinstance(setup, dict) else None
        if not isinstance(run, str) or not inside(run):
            fail("setup.run must be a script inside the folder")
        elif not (folder / run).is_file():
            fail(f"setup script {run} does not exist")
        elif not os.access(folder / run, os.X_OK):
            fail(f"setup script {run} is not executable")
        if isinstance(setup, dict) and not isinstance(setup.get("summary", ""), str):
            fail("setup.summary must be a string")
    commands = m.get("commands")
    if commands is not None:
        if not isinstance(commands, list):
            fail("commands must be an array")
        else:
            for i, c in enumerate(commands):
                if not isinstance(c, dict) or not isinstance(c.get("prefix"), str) or not c["prefix"].strip() or " " in c["prefix"].strip():
                    fail(f"commands[{i}] needs a one-word prefix")
                elif not isinstance(c.get("title"), str) or not c["title"].strip():
                    fail(f"commands[{i}] needs a title")
                elif any(not isinstance(a, dict) or not isinstance(a.get("name"), str) or not a["name"].strip() for a in c.get("args", [])):
                    fail(f"commands[{i}]: every argument needs a name")
    for key in m:
        if key not in {"name", "version", "author", "description", "apiVersion", "icon", "color", "homepage", "entry", "license", "setup", "commands"}:
            fail(f"unknown field {key} in extension.json")
    if not (folder / "README.md").is_file():
        fail("README.md is missing")
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_symlink():
            fail(f"symlink not allowed: {rel}")
        if path.name == "manifest.json":
            fail(f"{rel}: an extension is not an Omarchy plugin; name the file extension.json")
        if path.is_file() and path.stat().st_size > 5 * 1024 * 1024:
            fail(f"{rel} is larger than 5 MB; fetch large assets in a setup script")
        if path.suffix in {".qml", ".js"} and path.is_file():
            for line in path.read_text(errors="replace").splitlines():
                m = re.match(r'^\s*(?:import|\.import)\s+"([^"]+)"', line)
                if not m:
                    continue
                target = (path.parent / m.group(1)).resolve()
                if target != folder and folder not in target.parents:
                    fail(f"{rel} imports from outside the folder: {line.strip()}")
    qml_files = [p for p in folder.rglob("*.qml") if "tests" not in p.relative_to(folder).parts]
    qmllint = tool("qmllint")
    runner = tool("qmltestrunner")
    if qt_mode == "required" and not (qmllint and runner):
        fail("qmllint and qmltestrunner are required (pass --qt auto to skip when absent)")
    if qmllint and qml_files:
        with tempfile.TemporaryDirectory() as shim:
            shell = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")) / "shell"
            if shell.is_dir():
                (Path(shim) / "qs").symlink_to(shell)
            for qml in qml_files:
                r = subprocess.run([qmllint, "-I", "/usr/lib/qt6/qml", "-I", shim, str(qml)], capture_output=True, text=True)
                # Quickshell's metadata warnings are known noise; errors are not.
                if r.returncode != 0 and re.search(r"(?m)^.*(error|Error):", r.stdout + r.stderr):
                    fail(f"qmllint {qml.relative_to(folder)}: {(r.stdout + r.stderr).strip()[:400]}")
    tests = folder / "tests"
    if runner and tests.is_dir() and list(tests.glob("tst_*.qml")):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        r = subprocess.run([runner, "-silent", "-input", str(tests)], cwd=tests, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            fail(f"tests failed:\n{(r.stdout + r.stderr).strip()[-1500:]}")
    elif not tests.is_dir():
        print(f"  note: {name} has no tests/ folder")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folders", nargs="*", help="extension folders (default: every folder under extensions/)")
    ap.add_argument("--qt", choices=["required", "auto"], default="required", help="whether qmllint/qmltestrunner must be present")
    args = ap.parse_args()
    folders = [Path(f) for f in args.folders] or sorted(p for p in (ROOT / "extensions").iterdir() if p.is_dir() and not p.name.startswith("."))
    if not folders:
        print("no extensions to check")
        return 0
    reserved = bundled_ids()
    failed = 0
    for folder in folders:
        problems = check(folder, args.qt, reserved)
        if problems:
            failed += 1
            print(f"FAIL {folder.name}")
            for p in problems:
                print("  - " + p.replace("\n", "\n    "))
        else:
            print(f"ok   {folder.name}")
    if not (tool("qmllint") and tool("qmltestrunner")):
        print("note: Qt tools not found; QML lint and tests were skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
