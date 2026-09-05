#!/usr/bin/env python3
"""Checks helpers/timezone.py, the one on-demand helper Keystroke keeps."""
import json
import subprocess
import sys
from pathlib import Path

HELPER = Path(__file__).resolve().parent.parent / "helpers/timezone.py"
CASES = [
    ("10 am in london on 2026-09-06", "Europe/Tallinn", {"result": "12:00 EEST"}),
    ("11 pm in new york to tokyo on 2026-09-06", "Europe/Tallinn", {"result": "12:00 JST"}),
    ("1:30 am in london on 2026-03-29", "Europe/Tallinn", {"error": "does not exist"}),
    ("1:30 am in london on 2026-10-25", "Europe/Tallinn", {"error": "occurs twice"}),
    ("13 pm in london", "Europe/Tallinn", {"error": "Invalid 12-hour"}),
    ("chrome", "Europe/Tallinn", {"error": "Not a time conversion"}),
]
failed = 0
for query, zone, expected in CASES:
    out = json.loads(subprocess.check_output([sys.executable, str(HELPER), query, zone], text=True, timeout=5))
    key = next(iter(expected))
    ok = key in out and expected[key] in out[key]
    print(("PASS " if ok else "FAIL ") + query + " -> " + json.dumps(out, ensure_ascii=False))
    failed += 0 if ok else 1
sys.exit(1 if failed else 0)
