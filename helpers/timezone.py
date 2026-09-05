#!/usr/bin/env python3
"""On-demand IANA time-zone conversion for Keystroke's converter.

Invoked once per distinct time query (never per keystroke). Prints one JSON
object: {"result": "HH:MM ZZZ", "detail": "..."} or {"error": "..."}.
DST gaps and folds are rejected instead of guessed.
"""
import datetime as dt
import json
import re
import sys
from zoneinfo import ZoneInfo, available_timezones

CITIES = {"london": "Europe/London", "tallinn": "Europe/Tallinn", "new york": "America/New_York",
          "san francisco": "America/Los_Angeles", "los angeles": "America/Los_Angeles",
          "tokyo": "Asia/Tokyo", "berlin": "Europe/Berlin", "paris": "Europe/Paris",
          "sydney": "Australia/Sydney", "singapore": "Asia/Singapore", "utc": "UTC"}
PATTERN = re.compile(r"\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+(?:in|from)\s+(.+?)(?:\s+to\s+(.+?))?(?:\s+on\s+(\d{4}-\d{2}-\d{2}))?\s*", re.I)


def timezone(name):
    name = name.strip().casefold()
    if name in CITIES:
        return ZoneInfo(CITIES[name])
    matches = [z for z in available_timezones()
               if z.casefold() == name or z.rsplit("/", 1)[-1].replace("_", " ").casefold() == name]
    if len(matches) != 1:
        raise ValueError("Use a full IANA timezone for ambiguous cities")
    return ZoneInfo(matches[0])


def convert_time(text, local_zone, now=None):
    m = PATTERN.fullmatch(text)
    if not m:
        raise ValueError("Not a time conversion")
    hour, minute = int(m[1]), int(m[2] or 0)
    if m[3]:
        if not 1 <= hour <= 12:
            raise ValueError("Invalid 12-hour time")
        hour = hour % 12 + (12 if m[3].lower() == "pm" else 0)
    if hour > 23 or minute > 59:
        raise ValueError("Invalid time")
    source = timezone(m[4])
    target = timezone(m[5]) if m[5] else ZoneInfo(local_zone)
    now = now or dt.datetime.now(dt.timezone.utc)
    date = dt.date.fromisoformat(m[6]) if m[6] else now.astimezone(source).date()
    naive = dt.datetime.combine(date, dt.time(hour, minute))
    instant = naive.replace(tzinfo=source)
    if instant.astimezone(dt.timezone.utc).astimezone(source).replace(tzinfo=None) != naive:
        raise ValueError("That time does not exist during the daylight-saving change")
    if instant.utcoffset() != instant.replace(fold=1).utcoffset():
        raise ValueError("That time occurs twice during the daylight-saving change")
    return instant.astimezone(target), instant


def main(argv):
    try:
        value, source = convert_time(argv[1], argv[2])
        print(json.dumps({"result": value.strftime("%H:%M %Z"),
                          "detail": source.strftime("%a, %d %b · %H:%M %Z") + " → " + value.strftime("%a, %d %b · %H:%M %Z")}))
    except Exception as e:  # noqa: BLE001 - every failure is reported as data
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main(sys.argv)
