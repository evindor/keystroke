import datetime as dt
import re
from zoneinfo import ZoneInfo, available_timezones
from flint.api import row, copy, navigate, score

# factor to SI, dimension, aliases. Currency is deliberately not silently guessed.
UNITS = [
    (1, "length", "m meter meters metre metres"), (.01, "length", "cm centimeter centimeters"),
    (.001, "length", "mm millimeter millimeters"), (1000, "length", "km kilometer kilometers"),
    (.3048, "length", "ft foot feet"), (.0254, "length", "in inch inches"),
    (.9144, "length", "yd yard yards"), (1609.344, "length", "mi mile miles"),
    (1, "mass", "kg kilogram kilograms"), (.001, "mass", "g gram grams"),
    (.45359237, "mass", "lb lbs pound pounds"), (.028349523125, "mass", "oz ounce ounces"),
    (1, "time", "s sec second seconds"), (60, "time", "min minute minutes"),
    (3600, "time", "h hr hour hours"), (86400, "time", "d day days"),
    (1, "volume", "l liter liters litre litres"), (.001, "volume", "ml milliliter milliliters"),
    (3.785411784, "volume", "gal gallon gallons"),
    (1, "data", "b byte bytes"), (1000, "data", "kb"), (1e6, "data", "mb"), (1e9, "data", "gb"),
    (1024, "data", "kib"), (1048576, "data", "mib"), (1073741824, "data", "gib"),
    (1, "speed", "m/s"), (1/3.6, "speed", "km/h kph"), (.44704, "speed", "mph")]
LOOKUP = {a: (factor, dimension) for factor, dimension, aliases in UNITS for a in aliases.split()}
CITIES = {"london": "Europe/London", "tallinn": "Europe/Tallinn", "new york": "America/New_York",
          "san francisco": "America/Los_Angeles", "los angeles": "America/Los_Angeles",
          "tokyo": "Asia/Tokyo", "berlin": "Europe/Berlin", "paris": "Europe/Paris",
          "sydney": "Australia/Sydney", "singapore": "Asia/Singapore", "utc": "UTC"}


def timezone(name):
    name = name.strip().casefold()
    if name in CITIES:
        return ZoneInfo(CITIES[name])
    matches = [z for z in available_timezones() if z.casefold() == name or z.rsplit("/", 1)[-1].replace("_", " ").casefold() == name]
    if len(matches) != 1:
        raise ValueError("Use a full IANA timezone for ambiguous cities")
    return ZoneInfo(matches[0])


def convert(text):
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*([\w/°]+)\s+(?:in|to)\s+([\w/°]+)\s*", text, re.I)
    if not m:
        raise ValueError("Not a unit conversion")
    value, source, target = float(m[1]), m[2].casefold().lstrip("°"), m[3].casefold().lstrip("°")
    temperatures = {"c": "c", "celsius": "c", "f": "f", "fahrenheit": "f", "k": "k", "kelvin": "k"}
    if source in temperatures and target in temperatures:
        source, target = temperatures[source], temperatures[target]
        celsius = (value-32)*5/9 if source == "f" else value-273.15 if source == "k" else value
        if celsius < -273.15:
            raise ValueError("Below absolute zero")
        return (celsius*9/5+32 if target == "f" else celsius+273.15 if target == "k" else celsius), "°" + target.upper()
    sf, sd = LOOKUP[source]
    tf, td = LOOKUP[target]
    if sd != td:
        raise ValueError("Incompatible dimensions")
    return value * sf / tf, target


def convert_time(text, local_zone, now=None):
    # "10 am in London" means 10:00 London time -> configured local timezone.
    m = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+(?:in|from)\s+(.+?)(?:\s+to\s+(.+?))?(?:\s+on\s+(\d{4}-\d{2}-\d{2}))?\s*", text, re.I)
    if not m:
        raise ValueError("Not a time conversion")
    hour, minute = int(m[1]), int(m[2] or 0)
    if m[3]:
        if not 1 <= hour <= 12:
            raise ValueError("Invalid 12-hour time")
        hour = hour % 12 + (12 if m[3].lower() == "pm" else 0)
    source, target = timezone(m[4]), timezone(m[5]) if m[5] else ZoneInfo(local_zone)
    now = now or dt.datetime.now(dt.timezone.utc)
    date = dt.date.fromisoformat(m[6]) if m[6] else now.astimezone(source).date()
    naive = dt.datetime.combine(date, dt.time(hour, minute))
    instant = naive.replace(tzinfo=source)
    if instant.astimezone(dt.timezone.utc).astimezone(source).replace(tzinfo=None) != naive:
        raise ValueError("That time does not exist during the daylight-saving change")
    if instant.utcoffset() != instant.replace(fold=1).utcoffset():
        raise ValueError("That time occurs twice during the daylight-saving change")
    return instant.astimezone(target), instant


async def query(ctx):
    if ctx.scope and ctx.scope != "flint.converter":
        return []
    if not ctx.query:
        return [row("converter", "Convert Anything", "Units, temperatures & time zones", "󰯍", action=navigate("flint.converter"), score=23, order=4)] if not ctx.scope else []
    s = score(ctx.query, "Convert Anything", "converter units timezone temperature")
    if s and not ctx.scope:
        return [row("converter", "Convert Anything", "Units, temperatures & time zones", "󰯍", action=navigate("flint.converter"), score=s)]
    try:
        value, unit = convert(ctx.query)
        result = f"{value:.10g} {unit}"
        detail = "US liquid gallons · decimal KB/MB/GB" if unit in {"gal", "gallons", "gallon", "kb", "mb", "gb"} else "Unit conversion"
    except (KeyError, ValueError, OverflowError):
        try:
            value, source = convert_time(ctx.query, ctx.settings["timezone"])
            result = value.strftime("%H:%M %Z")
            detail = source.strftime("%a, %d %b · %H:%M %Z") + " → " + value.strftime("%a, %d %b · %H:%M %Z")
        except (KeyError, ValueError, OverflowError) as e:
            if "daylight-saving" in str(e):
                return [row("dst", "Ambiguous local time", str(e), "◷", score=180, action=navigate("flint.converter"))]
            return []
    return [row("conversion", result, detail, "󰯍", score=195, action=copy(result), verb="Copy result",
                preview=result, previewLabel="CONVERSION", previewDetail=ctx.query + "\n" + detail)]
