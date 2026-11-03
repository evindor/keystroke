#!/usr/bin/env python3
"""Extract a Raycast store zip, dropping the single top folder Vicinae strips."""

import os
import sys
import zipfile


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: unzip.py <zip> <dest>")
    src, dest = sys.argv[1], sys.argv[2]
    os.makedirs(dest, exist_ok=True)
    dest_abs = os.path.abspath(dest)
    with zipfile.ZipFile(src) as archive:
        names = [info.filename.replace("\\", "/") for info in archive.infolist()]
        tops = set()
        for name in names:
            if not name or name.endswith("/"):
                head = name.rstrip("/").split("/", 1)[0]
            else:
                head = name.split("/", 1)[0]
            if head:
                tops.add(head)
        strip = len(tops) == 1
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if not name or name.startswith("/") or name.startswith("../") or "/../" in "/" + name:
                raise SystemExit("unsafe zip path: " + name)
            rel = name.split("/", 1)[1] if strip and "/" in name else name
            if strip and "/" not in name:
                continue
            if not rel or rel.endswith("/"):
                if rel:
                    os.makedirs(os.path.join(dest, rel), exist_ok=True)
                continue
            out = os.path.abspath(os.path.join(dest, rel))
            if os.path.commonpath([dest_abs, out]) != dest_abs:
                raise SystemExit("unsafe zip path: " + name)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with archive.open(info) as inp, open(out, "wb") as outf:
                outf.write(inp.read())


if __name__ == "__main__":
    main()
