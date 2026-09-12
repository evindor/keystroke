#!/usr/bin/env python3
"""Query GIPHY for GIFs.

The API key arrives in the environment, never in argv: /proc/<pid>/cmdline is
world readable, /proc/<pid>/environ is owner only. No message printed here ever
carries the key or the request URL.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://api.giphy.com/v1/gifs/"
RATINGS = ("g", "pg", "pg-13", "r")
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 15


class Failure(Exception):
    """A message fit to show in the palette."""


def request_url(endpoint, args, key):
    params = {"api_key": key, "limit": args.limit, "offset": args.offset, "rating": args.rating}
    if endpoint == "search":
        params["q"] = args.query
        params["lang"] = "en"
    base = os.environ.get("GIPHY_API_BASE") or DEFAULT_BASE
    return base.rstrip("/") + "/" + endpoint + "?" + urllib.parse.urlencode(params)


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            data = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise Failure("GIPHY rejected the API key. Check it in GIF Search settings.") from None
        if error.code == 429:
            raise Failure("GIPHY rate limit reached. Beta keys allow about 100 searches an hour.") from None
        raise Failure("GIPHY returned HTTP %d." % error.code) from None
    except (urllib.error.URLError, OSError, ValueError):
        raise Failure("Could not reach GIPHY. Check your connection and retry.") from None
    if len(data) > MAX_BYTES:
        raise Failure("GIPHY returned an unexpectedly large response.") from None
    try:
        json.loads(data)
    except (UnicodeDecodeError, ValueError):
        raise Failure("GIPHY returned an unreadable response.") from None
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("endpoint", choices=("search", "trending"))
    parser.add_argument("--query", default="")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--rating", default="g", choices=RATINGS)
    args = parser.parse_args()
    try:
        key = os.environ.get("GIPHY_API_KEY", "").strip()
        if not key:
            raise Failure("No GIPHY API key set. Add one in GIF Search settings.")
        # Catches a mis-paste (a whole dashboard URL, say) with a clear message.
        # Transport is safe either way: the key goes through urlencode.
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", key):
            raise Failure("That does not look like a GIPHY API key.")
        if args.endpoint == "search" and not args.query.strip():
            raise Failure("Nothing to search for.")
        args.limit = max(1, min(args.limit, 50))
        args.offset = max(0, min(args.offset, 4999))
        sys.stdout.buffer.write(fetch(request_url(args.endpoint, args, key)))
        return 0
    except Failure as error:
        print(str(error))
        return 1
    except Exception:
        # Never let a traceback carry the request URL, and so the key, to stdout.
        print("GIF search failed unexpectedly.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
