#!/usr/bin/env python3
"""Checks helpers/timezone.py, the one on-demand helper Keystroke keeps.

Every case runs with the clock fixed at 2026-09-09 12:00 UTC (a Wednesday)
so relative dates and "now" answers are deterministic.
"""
import json
import subprocess
import sys
from pathlib import Path

HELPER = Path(__file__).resolve().parent.parent / "helpers/timezone.py"
NOW = "2026-09-09T12:00:00+00:00"
CASES = [
    # (query, local zone, {key: substring expected in that field})
    ("10 am in london on 2026-09-06", "Europe/Tallinn", {"result": "12:00 EEST"}),
    ("11 pm in new york to tokyo on 2026-09-06", "Europe/Tallinn", {"result": "12:00 JST"}),
    ("1:30 am in london on 2026-03-29", "Europe/Tallinn", {"error": "does not exist"}),
    ("1:30 am in london on 2026-10-25", "Europe/Tallinn", {"error": "occurs twice"}),
    ("13 pm in london", "Europe/Tallinn", {"error": "Invalid 12-hour"}),
    ("chrome", "Europe/Tallinn", {"error": "Not a time conversion"}),
    ("10 chrome", "Europe/Tallinn", {"error": "Not a time conversion"}),
    # Abbreviations, bare form, note naming the zone that was used
    ("10am pt", "Europe/Tallinn", {"result": "20:00 EEST", "detail": "pt = America/Los_Angeles"}),
    ("10:30pm est", "Europe/Tallinn", {"result": "05:30 EEST", "detail": "Thu, 10 Sep"}),
    ("10am pst to cet", "Europe/Tallinn", {"result": "19:00 CEST"}),
    ("10am ist", "Europe/Tallinn", {"result": "07:30 EEST", "detail": "Asia/Kolkata"}),
    ("9am aest", "UTC", {"result": "23:00 UTC", "detail": "Tue, 08 Sep"}),
    ("10 a.m. pt", "Europe/Tallinn", {"result": "20:00 EEST"}),
    ("10am pt in my time", "Europe/Tallinn", {"result": "20:00 EEST"}),
    ("10am from pt to here", "Europe/Tallinn", {"result": "20:00 EEST"}),
    # Separators, 24-hour forms, words
    ("10.30 in london", "Europe/Tallinn", {"result": "12:30 EEST"}),
    ("10 in london", "Europe/Tallinn", {"result": "12:00 EEST"}),
    ("1530 utc", "Europe/Tallinn", {"result": "18:30 EEST"}),
    ("15:00 cet", "Europe/Tallinn", {"result": "16:00 EEST"}),
    ("noon utc", "Europe/Tallinn", {"result": "15:00 EEST"}),
    ("midnight pt to tokyo", "Europe/Tallinn", {"result": "16:00 JST"}),
    ("10am pt -> tokyo", "Europe/Tallinn", {"result": "02:00 JST", "detail": "Thu, 10 Sep"}),
    ("10am to london", "Europe/Tallinn", {"result": "08:00 BST"}),
    # Names: cities, countries, IANA, offsets
    ("10am in san francisco", "Europe/Tallinn", {"result": "20:00 EEST"}),
    ("10am amsterdam", "Europe/Tallinn", {"result": "11:00 EEST"}),
    ("10am india", "Europe/Tallinn", {"result": "07:30 EEST"}),
    ("10am in Europe/Tallinn to America/Los_Angeles", "UTC", {"result": "00:00 PDT"}),
    ("10am in new_york", "Europe/Tallinn", {"result": "17:00 EEST"}),
    ("10am utc+2", "Europe/Tallinn", {"result": "11:00 EEST"}),
    ("10 am gmt-5", "Europe/Tallinn", {"result": "18:00 EEST"}),
    ("10am +05:30", "Europe/Tallinn", {"result": "07:30 EEST"}),
    ("10am australia", "Europe/Tallinn", {"error": "sydney, adelaide or perth", "hint": True}),
    ("10am in springfield", "Europe/Tallinn", {"error": "Unknown time zone"}),
    ("10am", "Europe/Tallinn", {"error": "Which time zone"}),
    # Now
    ("now in london", "Europe/Tallinn", {"result": "13:00 BST", "live": True, "detail": "15:00 EEST here"}),
    ("what time is it in new york", "Europe/Tallinn", {"result": "08:00 EDT", "live": True}),
    ("time in tokyo", "Europe/Tallinn", {"result": "21:00 JST"}),
    ("london time", "Europe/Tallinn", {"result": "13:00 BST"}),
    ("pacific time", "Europe/Tallinn", {"result": "05:00 PDT"}),
    # Dates
    ("tomorrow 10am pt", "Europe/Tallinn", {"detail": "Thu, 10 Sep"}),
    ("monday 9am est", "Europe/Tallinn", {"detail": "Mon, 14 Sep"}),
    ("wednesday 9am est", "Europe/Tallinn", {"detail": "Wed, 09 Sep"}),
    ("next wednesday 9am est", "Europe/Tallinn", {"detail": "Wed, 16 Sep"}),
    ("10am pt on friday", "Europe/Tallinn", {"detail": "Fri, 11 Sep"}),
    ("10am pt on 6 sep", "Europe/Tallinn", {"detail": "Sun, 06 Sep"}),
    ("10am pt sep 6 2027", "Europe/Tallinn", {"detail": "Mon, 06 Sep"}),
    ("10am pt on 2026-09-06", "Europe/Tallinn", {"detail": "Sun, 06 Sep"}),
    ("10pm pt on tuesday to tokyo", "Europe/Tallinn", {"detail": "Tue, 15 Sep · 22:00 PDT → Wed, 16 Sep"}),
    # Offset-based deduplication: Asia/Istanbul and Europe/Istanbul share the same offset
    ("now in istanbul", "Europe/Tallinn", {"result": "15:00 +03", "live": True}),
    ("now in Asia/Istanbul", "Europe/Tallinn", {"result": "15:00 +03", "live": True}),
    ("now in Europe/Istanbul", "Europe/Tallinn", {"result": "15:00 +03", "live": True}),
    ("15:00 istanbul to utc", "Europe/Tallinn", {"result": "12:00 UTC"}),
]
failed = 0
for query, zone, expected in CASES:
    out = json.loads(subprocess.check_output([sys.executable, str(HELPER), query, zone, NOW], text=True, timeout=5))
    ok = all(key in out and (expected[key] is True and out[key] is True or
                             isinstance(expected[key], str) and expected[key] in str(out[key]))
             for key in expected)
    print(("PASS " if ok else "FAIL ") + query + " -> " + json.dumps(out, ensure_ascii=False))
    failed += 0 if ok else 1
print(f"{len(CASES) - failed}/{len(CASES)} passed")
sys.exit(1 if failed else 0)
