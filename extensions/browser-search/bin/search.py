#!/usr/bin/env python3
"""Read only the default browser's saved web pages; emit bounded JSON results."""
import argparse
import configparser
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
from urllib.parse import urlsplit


# Exact desktop IDs: never silently search a different browser's private data.
BROWSERS = {
    "chromium.desktop": ("Chromium", "chromium"),
    "chromium-browser.desktop": ("Chromium", "chromium"),
    "google-chrome.desktop": ("Google Chrome", "google-chrome"),
    "google-chrome-beta.desktop": ("Google Chrome Beta", "google-chrome-beta"),
    "google-chrome-unstable.desktop": ("Google Chrome Dev", "google-chrome-unstable"),
    "brave-browser.desktop": ("Brave", "BraveSoftware/Brave-Browser"),
    "vivaldi-stable.desktop": ("Vivaldi", "vivaldi"),
    "vivaldi.desktop": ("Vivaldi", "vivaldi"),
    "microsoft-edge.desktop": ("Microsoft Edge", "microsoft-edge"),
    "firefox.desktop": ("Firefox", None),
    "firefox-esr.desktop": ("Firefox ESR", None),
}
FLATPAKS = {
    "org.chromium.Chromium.desktop": ("Chromium", "chromium"),
    "com.google.Chrome.desktop": ("Google Chrome", "google-chrome"),
    "com.brave.Browser.desktop": ("Brave", "BraveSoftware/Brave-Browser"),
    "com.microsoft.Edge.desktop": ("Microsoft Edge", "microsoft-edge"),
    "com.vivaldi.Vivaldi.desktop": ("Vivaldi", "vivaldi"),
    "org.mozilla.firefox.desktop": ("Firefox", None),
}


def default_browser():
    # xdg-mime reads mimeapps.list directly; xdg-settings probes the desktop
    # environment first and costs several hundred milliseconds for the same answer.
    for command in (["xdg-mime", "query", "default", "x-scheme-handler/https"],
                    ["xdg-settings", "get", "default-web-browser"]):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=1)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return ""


def profiles(desktop, home, config):
    """Return family, display name and existing profiles for one browser."""
    spec = BROWSERS.get(desktop) or FLATPAKS.get(desktop)
    if not spec:
        raise ValueError("Default browser is not supported" if desktop else "Could not detect the default browser")
    name, directory = spec
    flatpak = desktop in FLATPAKS
    base = home / ".var/app" / desktop.removesuffix(".desktop") if flatpak else home
    config = base / "config" if flatpak else config
    if directory:
        # Chrome honors these overrides before XDG_CONFIG_HOME.
        if not flatpak:
            config = Path(os.environ.get("CHROME_CONFIG_HOME") or str(config))
        data = config / directory
        if not flatpak and os.environ.get("CHROME_USER_DATA_DIR"):
            data = Path(os.environ["CHROME_USER_DATA_DIR"])
        found = []
        if data.is_dir():
            found = [p for p in data.iterdir() if p.is_dir() and
                     (p.name == "Default" or p.name.startswith("Profile "))]
        return "chromium", name, sorted(found)[:32]
    data = base / ".mozilla/firefox"
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(data / "profiles.ini")
    found = []
    for section in ini.sections():
        if not section.startswith("Profile") or not ini.has_option(section, "Path"):
            continue
        path = Path(ini.get(section, "Path"))
        if ini.get(section, "IsRelative", fallback="1") == "1":
            path = data / path
        if path.is_dir() and path not in found:
            found.append(path)
    return "firefox", name, found[:32]


def web_url(url):
    if not isinstance(url, str) or len(url) > 16384 or any(ord(c) < 32 for c in url):
        return False
    try:
        parsed = urlsplit(url)
        return parsed.scheme.lower() in ("http", "https") and bool(parsed.netloc)
    except ValueError:
        return False


def matches(title, url, terms):
    # SQLite calls this for every row: the substring test first, the costlier
    # URL parse only for the few rows that survive it.
    text = (str(title or "") + " " + str(url or "")).casefold()
    return all(term in text for term in terms) and web_url(url)


def database_rows(path, family, source, terms, deadline):
    # mode=ro sees committed WAL data as well; immutable=1 would miss live visits.
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.1)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        conn.create_function("matches", 2, lambda title, url: matches(title, url, terms))
        if family == "chromium":
            sql = "SELECT title, url, last_visit_time FROM urls WHERE hidden=0 AND matches(title,url) ORDER BY last_visit_time DESC LIMIT 60"
        elif source == "history":
            sql = "SELECT title, url, last_visit_date FROM moz_places WHERE hidden=0 AND last_visit_date>0 AND matches(title,url) ORDER BY last_visit_date DESC LIMIT 60"
        else:
            sql = "SELECT COALESCE(b.title,p.title), p.url, b.dateAdded FROM moz_bookmarks b JOIN moz_places p ON p.id=b.fk WHERE b.type=1 AND matches(COALESCE(b.title,p.title),p.url) ORDER BY b.dateAdded DESC LIMIT 60"
        return list(conn.execute(sql))
    finally:
        conn.close()


def bookmark_rows(path, terms, deadline):
    with path.open("rb") as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Bookmark file exceeds 16 MB")
    data = json.loads(raw)
    roots = data.get("roots", {})
    if not isinstance(roots, dict):
        raise ValueError("Invalid bookmark roots")
    stack = list(roots.values())
    found = []
    while stack:
        if time.monotonic() > deadline:
            raise ValueError("Search deadline exceeded")
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if node.get("type") == "url" and matches(node.get("name"), node.get("url"), terms):
            found.append((node.get("name", ""), node["url"], int(node.get("date_added") or 0)))
        children = node.get("children", [])
        if isinstance(children, list):
            stack.extend(children)
    return sorted(found, key=lambda row: row[2], reverse=True)[:60]


def search(query, history=True, bookmarks=True, *, desktop=None, home=None, config=None):
    result = {"browser": "", "results": [], "error": ""}
    if not (history or bookmarks) or len(query.strip()) < 2:
        return result
    home = Path(home) if home is not None else Path.home()
    config = Path(config) if config is not None else Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    desktop = default_browser() if desktop is None else desktop
    try:
        family, name, found = profiles(desktop, home, config)
        result["browser"] = name
    except (ValueError, OSError, configparser.Error) as exc:
        result["error"] = str(exc) if isinstance(exc, ValueError) else "Could not read browser profiles"
        return result
    if not found:
        result["error"] = "No browser profiles found in the standard location"
        return result
    deadline = time.monotonic() + 2
    terms = query[:512].casefold().split()
    merged, errors, readable = {}, set(), 0
    for profile in found:
        for source, enabled in (("bookmarks", bookmarks), ("history", history)):
            if not enabled:
                continue
            path = profile / ("places.sqlite" if family == "firefox" else "Bookmarks" if source == "bookmarks" else "History")
            if not path.is_file():
                continue
            try:
                rows = bookmark_rows(path, terms, deadline) if family == "chromium" and source == "bookmarks" else database_rows(path, family, source, terms, deadline)
                readable += 1
                for title, url, stamp in rows:
                    item = merged.setdefault(url, {"url": url, "title": str(title or url)[:2048], "profile": profile.name,
                                                   "bookmark": False, "history": False, "stamp": 0})
                    item["bookmark" if source == "bookmarks" else "history"] = True
                    item["stamp"] = max(item["stamp"], stamp or 0)
            except (OSError, ValueError, sqlite3.Error, TypeError):
                errors.add(source)
    result["results"] = sorted(merged.values(), key=lambda item: (not item["bookmark"], -item["stamp"], item["url"]))[:30]
    if errors:
        result["error"] = "Could not read some " + " and ".join(sorted(errors)) + "; reopen the palette to retry"
    elif not readable:
        result["error"] = "No enabled browser data found in the detected profiles"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", choices=("0", "1"), default="1")
    parser.add_argument("--bookmarks", choices=("0", "1"), default="1")
    parser.add_argument("query")
    args = parser.parse_args()
    print(json.dumps(search(args.query, args.history == "1", args.bookmarks == "1"), ensure_ascii=True))


if __name__ == "__main__":
    main()
