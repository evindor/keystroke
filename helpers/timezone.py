#!/usr/bin/env python3
"""On-demand IANA time-zone conversion for Keystroke's converter.

Invoked once per distinct time query (never per keystroke), with the query
and the user's zone; a third argument (an ISO instant) fixes "now" for tests.
Prints one JSON object: {"result": "HH:MM ZZZ", "detail": "..."} plus
"live": true when the answer moves with the clock, or {"error": "..."} plus
"hint": true when the message is worth showing to the user.
DST gaps and folds are rejected instead of guessed.

Grammar (case-insensitive, whitespace-tolerant):
  <time> [in|from|at] <zone> [to|in <zone>] [on <date>]     10am pt, 10:30 in london to tokyo
  <time> to <zone>                                          local 10am shown in that zone
  [what time is it | time | now] in <zone>                  now in that zone
  <zone> time                                               same
  <date> [at] <time> ...  /  ... <date>                     tomorrow 9am est, 10am pt on monday
A <time> is 10am, 10:30pm, 10.30, 1530, 15:00, noon or midnight. A bare hour
(10 in london) needs "in", "from" or "at". A <zone> is an abbreviation (pt,
est, cet, ist, aest...), a name (pacific, eastern, london, new york), an
IANA zone (Europe/Tallinn), an offset (utc+2, gmt-5, +05:30) or here/local/
my time. A <date> is 2026-09-06, today, tomorrow, yesterday, a weekday,
"6 sep", "sep 6" or "sep 6 2027".
"""
import datetime as dt
import json
import re
import sys
from zoneinfo import ZoneInfo, available_timezones

# Abbreviations and common names. Ambiguous abbreviations take their most
# common reading (ist = India, cst = US Central, bst = British); the detail
# line always names the zone that was used so a wrong guess is visible.
ALIASES = {
    "utc": "UTC", "gmt": "UTC", "z": "UTC", "zulu": "UTC",
    "pt": "America/Los_Angeles", "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles", "pacific": "America/Los_Angeles",
    "mt": "America/Denver", "mst": "America/Denver", "mdt": "America/Denver", "mountain": "America/Denver",
    "ct": "America/Chicago", "cst": "America/Chicago", "cdt": "America/Chicago", "central": "America/Chicago",
    "et": "America/New_York", "est": "America/New_York", "edt": "America/New_York", "eastern": "America/New_York",
    "ast": "America/Halifax", "adt": "America/Halifax", "atlantic": "America/Halifax",
    "akst": "America/Anchorage", "akdt": "America/Anchorage", "alaska": "America/Anchorage",
    "hst": "Pacific/Honolulu", "hawaii": "Pacific/Honolulu",
    "bst": "Europe/London", "uk": "Europe/London", "england": "Europe/London", "britain": "Europe/London",
    "wet": "Europe/Lisbon", "west": "Europe/Lisbon",
    "cet": "Europe/Berlin", "cest": "Europe/Berlin", "met": "Europe/Berlin", "mest": "Europe/Berlin",
    "eet": "Europe/Helsinki", "eest": "Europe/Helsinki",
    "msk": "Europe/Moscow", "trt": "Europe/Istanbul",
    "ist": "Asia/Kolkata", "pkt": "Asia/Karachi", "ict": "Asia/Bangkok", "wib": "Asia/Jakarta",
    "sgt": "Asia/Singapore", "hkt": "Asia/Hong_Kong", "jst": "Asia/Tokyo", "kst": "Asia/Seoul",
    "gst": "Asia/Dubai", "idt": "Asia/Jerusalem",
    "aest": "Australia/Sydney", "aedt": "Australia/Sydney", "aet": "Australia/Sydney",
    "acst": "Australia/Adelaide", "acdt": "Australia/Adelaide", "awst": "Australia/Perth",
    "nzst": "Pacific/Auckland", "nzdt": "Pacific/Auckland", "nzt": "Pacific/Auckland",
    "sast": "Africa/Johannesburg", "wat": "Africa/Lagos", "eat": "Africa/Nairobi",
    "brt": "America/Sao_Paulo", "art": "America/Argentina/Buenos_Aires",
    # Cities and countries that are not IANA zone names, or that map to one.
    "san francisco": "America/Los_Angeles", "sf": "America/Los_Angeles", "la": "America/Los_Angeles",
    "seattle": "America/Los_Angeles", "portland": "America/Los_Angeles", "san diego": "America/Los_Angeles",
    "bay area": "America/Los_Angeles", "silicon valley": "America/Los_Angeles", "las vegas": "America/Los_Angeles",
    "nyc": "America/New_York", "ny": "America/New_York", "boston": "America/New_York", "miami": "America/New_York",
    "washington": "America/New_York", "dc": "America/New_York", "atlanta": "America/New_York",
    "philadelphia": "America/New_York", "montreal": "America/Toronto", "ottawa": "America/Toronto",
    "austin": "America/Chicago", "dallas": "America/Chicago", "houston": "America/Chicago",
    "minneapolis": "America/Chicago", "salt lake city": "America/Denver", "calgary": "America/Edmonton",
    "ireland": "Europe/Dublin", "portugal": "Europe/Lisbon", "spain": "Europe/Madrid", "barcelona": "Europe/Madrid",
    "france": "Europe/Paris", "germany": "Europe/Berlin", "munich": "Europe/Berlin", "frankfurt": "Europe/Berlin",
    "hamburg": "Europe/Berlin", "cologne": "Europe/Berlin", "italy": "Europe/Rome", "milan": "Europe/Rome",
    "netherlands": "Europe/Amsterdam", "holland": "Europe/Amsterdam", "belgium": "Europe/Brussels",
    "switzerland": "Europe/Zurich", "geneva": "Europe/Zurich", "austria": "Europe/Vienna",
    "sweden": "Europe/Stockholm", "norway": "Europe/Oslo", "denmark": "Europe/Copenhagen",
    "finland": "Europe/Helsinki", "estonia": "Europe/Tallinn", "latvia": "Europe/Riga", "lithuania": "Europe/Vilnius",
    "poland": "Europe/Warsaw", "krakow": "Europe/Warsaw", "czechia": "Europe/Prague", "czech": "Europe/Prague",
    "hungary": "Europe/Budapest", "romania": "Europe/Bucharest", "greece": "Europe/Athens",
    "ukraine": "Europe/Kyiv", "kiev": "Europe/Kyiv", "turkey": "Europe/Istanbul",
    "st petersburg": "Europe/Moscow", "saint petersburg": "Europe/Moscow",
    "israel": "Asia/Jerusalem", "tel aviv": "Asia/Jerusalem", "uae": "Asia/Dubai", "saudi": "Asia/Riyadh",
    "india": "Asia/Kolkata", "mumbai": "Asia/Kolkata", "delhi": "Asia/Kolkata", "new delhi": "Asia/Kolkata",
    "bangalore": "Asia/Kolkata", "bengaluru": "Asia/Kolkata", "hyderabad": "Asia/Kolkata", "chennai": "Asia/Kolkata",
    "pune": "Asia/Kolkata", "pakistan": "Asia/Karachi", "thailand": "Asia/Bangkok", "vietnam": "Asia/Ho_Chi_Minh",
    "hanoi": "Asia/Ho_Chi_Minh", "saigon": "Asia/Ho_Chi_Minh", "philippines": "Asia/Manila",
    "china": "Asia/Shanghai", "beijing": "Asia/Shanghai", "shenzhen": "Asia/Shanghai", "hangzhou": "Asia/Shanghai",
    "japan": "Asia/Tokyo", "osaka": "Asia/Tokyo", "korea": "Asia/Seoul", "south korea": "Asia/Seoul",
    "taiwan": "Asia/Taipei", "egypt": "Africa/Cairo", "south africa": "Africa/Johannesburg",
    "cape town": "Africa/Johannesburg", "kenya": "Africa/Nairobi", "nigeria": "Africa/Lagos",
    "argentina": "America/Argentina/Buenos_Aires", "colombia": "America/Bogota", "peru": "America/Lima",
    "chile": "America/Santiago", "rio": "America/Sao_Paulo", "rio de janeiro": "America/Sao_Paulo",
    "auckland": "Pacific/Auckland", "new zealand": "Pacific/Auckland", "wellington": "Pacific/Auckland",
}
AMBIGUOUS = {
    "usa": "et, ct, mt or pt", "us": "et, ct, mt or pt", "america": "et, ct, mt or pt", "united states": "et, ct, mt or pt",
    "canada": "toronto or vancouver", "australia": "sydney, adelaide or perth", "brazil": "sao paulo",
    "russia": "moscow", "mexico": "mexico city", "indonesia": "jakarta", "europe": "cet or eet",
}
LOCAL = {"here", "local", "local time", "me", "mine", "my time", "my zone", "my timezone", "my time zone"}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
WEEKDAY_RE = (r"(?:monday|mon|tuesday|tues|tue|wednesday|weds|wed|thursday|thurs|thur|thu|friday|fri"
              r"|saturday|sat|sunday|sun)")
MONTH_RE = (r"(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug"
            r"|september|sept|sep|october|oct|november|nov|december|dec)")
DATE_RE = (r"(?P<iso>\d{4}-\d{2}-\d{2})|(?P<rel>today|tonight|tomorrow|tmrw|tmr|yesterday)"
           r"|(?P<nxt>next\s+|this\s+)?(?P<wd>" + WEEKDAY_RE + r")"
           r"|(?P<d1>\d{1,2})(?:st|nd|rd|th)?\s+(?P<mo1>" + MONTH_RE + r")(?:,?\s+(?P<y1>\d{4}))?"
           r"|(?P<mo2>" + MONTH_RE + r")\s+(?P<d2>\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(?P<y2>\d{4}))?")
DATE_SUFFIX = re.compile(r"^(?P<rest>.+?)(?:\s+on)?\s+(?:" + DATE_RE + r")$")
DATE_PREFIX = re.compile(r"^(?:on\s+)?(?:" + DATE_RE + r")(?:\s+at)?\s+(?P<rest>.+)$")
DATE_INSIDE = re.compile(r"^(?P<rest>.+?)\s+on\s+(?:" + DATE_RE + r")(?P<tail>\s+(?:to|in|for|as|vs)\s+.+)$")
TIME_RE = (r"(?:(?P<h24>[01]\d|2[0-3])(?P<m24>[0-5]\d)(?!\d)"
           r"|(?P<h>\d{1,2})(?:[:.](?P<m>[0-5]\d))?\s*(?P<ap>(?:a\.?m\.?|p\.?m\.?)(?![a-z]))?"
           r"|(?P<word>noon|midday|midnight))")
TIME_QUERY = re.compile(r"^" + TIME_RE + r"\s*(?:(?P<sep>in|from|at|@)\s+)?(?P<rest>.*)$")
NOW_QUERY = re.compile(r"^(?:(?:what(?:'s|\s+is)?\s+(?:the\s+)?)?(?:current\s+|local\s+)?time(?:\s+is\s+it)?"
                       r"(?:\s+(?:right\s+)?now)?|now|(?:the\s+)?date)\s+(?:in|at|for|of)\s+(?P<zone>.+)$")
ZONE_TIME = re.compile(r"^(?P<zone>.+?)\s+(?:time|now)$")
SPLIT_RE = re.compile(r"\s+(?:to|in|for|as|vs)\s+")
OFFSET_RE = re.compile(r"^(?:utc|gmt|z)?\s*(?P<sign>[+-])\s*(?P<h>\d{1,2})(?::?(?P<m>[0-5]\d))?$")


def normalize(text):
    text = " ".join(str(text).casefold().split())
    text = re.sub(r"\s*(?:->|→|=>|>)\s*", " to ", text)
    return text.strip(" ?.!")


class Hint(ValueError):
    """An error the palette should show as a row."""


class Zone:
    """An IANA or fixed-offset zone plus how the user spelled it."""
    def __init__(self, typed, tz, key):
        self.typed, self.tz, self.key = typed, tz, key

    def note(self):
        parts = re.split(r"[/_]", self.key.casefold())
        spelled_out = all(word in parts for word in re.split(r"[/_ ]", self.typed))
        return "" if self.key == "here" or spelled_out else self.typed + " = " + self.key


def resolve(name, local_zone):
    name = name.strip()
    if not name:
        raise ValueError("Which time zone?")
    if name in LOCAL:
        return Zone(name, ZoneInfo(local_zone), "here")
    if name in AMBIGUOUS:
        raise Hint(name.title() + " spans several time zones; try " + AMBIGUOUS[name])
    m = OFFSET_RE.fullmatch(name)
    if m:
        delta = dt.timedelta(hours=int(m["h"]), minutes=int(m["m"] or 0))
        if delta > dt.timedelta(hours=18):
            raise ValueError("Offset out of range")
        key = "UTC" + m["sign"] + "%02d:%02d" % (delta.seconds // 3600, delta.seconds // 60 % 60)
        return Zone(name, dt.timezone(-delta if m["sign"] == "-" else delta, key), key)
    if name in ALIASES:
        return Zone(name, ZoneInfo(ALIASES[name]), ALIASES[name])
    wanted = name.replace(" ", "_")
    zones = available_timezones()
    exact = [z for z in zones if z.casefold() == wanted]
    if exact:
        return Zone(name, ZoneInfo(exact[0]), exact[0])
    matches = sorted(z for z in zones if z.rsplit("/", 1)[-1].casefold() == wanted and "/" in z)
    if len(matches) == 1:
        return Zone(name, ZoneInfo(matches[0]), matches[0])
    if matches:
        raise Hint("Which " + name + "? Try " + " or ".join(matches[:3]))
    raise ValueError("Unknown time zone: " + name)


def weekday_index(word):
    for i, day in enumerate(WEEKDAYS):
        if day.startswith(word[:3]):
            return i
    raise ValueError("Unknown weekday")


def month_index(word):
    for i, month in enumerate(MONTHS):
        if month.startswith(word[:3]):
            return i + 1
    raise ValueError("Unknown month")


def resolve_date(m, today):
    """Turns a DATE_RE match into a date, relative to the source zone's today."""
    if m["iso"]:
        return dt.date.fromisoformat(m["iso"])
    if m["rel"]:
        return today + dt.timedelta(days={"tomorrow": 1, "tmrw": 1, "tmr": 1, "yesterday": -1}.get(m["rel"], 0))
    if m["wd"]:
        ahead = (weekday_index(m["wd"]) - today.weekday()) % 7
        if ahead == 0 and (m["nxt"] or "").strip() == "next":
            ahead = 7
        return today + dt.timedelta(days=ahead)
    day, month, year = (m["d1"], m["mo1"], m["y1"]) if m["d1"] else (m["d2"], m["mo2"], m["y2"])
    return dt.date(int(year) if year else today.year, month_index(month), int(day))


def split_date(text):
    """Returns (text without the date, DATE_RE match or None)."""
    m = DATE_SUFFIX.fullmatch(text)
    if m and m["rest"].split()[-1] not in ("in", "from", "at", "to", "for", "on"):
        return m["rest"], m
    m = DATE_PREFIX.fullmatch(text)
    if m:
        return m["rest"], m
    m = DATE_INSIDE.fullmatch(text)
    if m:
        return m["rest"] + m["tail"], m
    return text, None


def parse_time(m):
    if m["word"]:
        return (0 if m["word"] == "midnight" else 12), 0
    if m["h24"]:
        return int(m["h24"]), int(m["m24"])
    hour, minute = int(m["h"]), int(m["m"] or 0)
    if m["ap"]:
        if not 1 <= hour <= 12:
            raise ValueError("Invalid 12-hour time")
        hour = hour % 12 + (12 if m["ap"].startswith("p") else 0)
    if hour > 23:
        raise ValueError("Invalid time")
    return hour, minute


def parse(text, local_zone):
    """Returns ("at", hour, minute, source Zone, target Zone, date match) or ("now", Zone)."""
    text = normalize(text)
    m = NOW_QUERY.fullmatch(text)
    if m:
        return "now", resolve(m["zone"], local_zone)
    m = ZONE_TIME.fullmatch(text)
    if m and not TIME_QUERY.fullmatch(text):
        return "now", resolve(m["zone"], local_zone)
    text, date = split_date(text)
    m = TIME_QUERY.fullmatch(text)
    if not m:
        raise ValueError("Not a time conversion")
    hour, minute = parse_time(m)
    if not (m["sep"] or m["ap"] or m["m"] or m["h24"] or m["word"]):
        raise ValueError("Not a time conversion")  # "10 chrome" is not a time
    rest = m["rest"].strip()
    if rest.startswith("to "):
        source_name, target_name = "here", rest[3:]
    else:
        parts = SPLIT_RE.split(rest, maxsplit=1)
        source_name, target_name = parts[0], (parts[1] if len(parts) > 1 else "here")
    return "at", hour, minute, resolve(source_name, local_zone), resolve(target_name, local_zone), date


def convert_time(text, local_zone, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    parsed = parse(text, local_zone)
    if parsed[0] == "now":
        zone = parsed[1]
        return {"result": now.astimezone(zone.tz).strftime("%H:%M %Z"),
                "detail": now.astimezone(zone.tz).strftime("%a, %d %b · %H:%M %Z") + " in " + zone.key
                          + " · " + now.astimezone(ZoneInfo(local_zone)).strftime("%H:%M %Z") + " here",
                "live": True}
    _, hour, minute, source, target, date_match = parsed
    today = now.astimezone(source.tz).date()
    date = resolve_date(date_match, today) if date_match else today
    naive = dt.datetime.combine(date, dt.time(hour, minute))
    instant = naive.replace(tzinfo=source.tz)
    if instant.astimezone(dt.timezone.utc).astimezone(source.tz).replace(tzinfo=None) != naive:
        raise Hint("That time does not exist during the daylight-saving change")
    if instant.utcoffset() != instant.replace(fold=1).utcoffset():
        raise Hint("That time occurs twice during the daylight-saving change")
    value = instant.astimezone(target.tz)
    notes = [n for n in (source.note(), target.note()) if n]
    detail = instant.strftime("%a, %d %b · %H:%M %Z") + " → " + value.strftime("%a, %d %b · %H:%M %Z")
    if notes:
        detail += " · " + ", ".join(notes)
    return {"result": value.strftime("%H:%M %Z"), "detail": detail}


def main(argv):
    try:
        now = dt.datetime.fromisoformat(argv[3]) if len(argv) > 3 else None
        print(json.dumps(convert_time(argv[1], argv[2], now)))
    except Hint as e:
        print(json.dumps({"error": str(e), "hint": True}))
    except Exception as e:  # noqa: BLE001 - every failure is reported as data
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main(sys.argv)
