"""Synthetic browser profiles only; never consult the user's browser data."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("browser_search", Path(__file__).resolve().parents[1] / "bin/search.py")
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / ".config"
        self.profile = self.config / "chromium/Default"
        self.profile.mkdir(parents=True)
        self.env = patch.dict(os.environ, {"CHROME_CONFIG_HOME": "", "CHROME_USER_DATA_DIR": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def history(self, profile=None):
        db = sqlite3.connect((profile or self.profile) / "History")
        db.execute("CREATE TABLE urls (title TEXT, url TEXT, last_visit_time INTEGER, hidden INTEGER)")
        db.executemany("INSERT INTO urls VALUES (?,?,?,?)", [
            ("Keystroke docs", "https://example.org/docs", 100, 0),
            ("Keystroke old", "https://example.org/old", 10, 0),
            ("Keystroke hidden", "https://example.org/hidden", 200, 1),
            ("Keystroke script", "javascript:alert(1)", 300, 0),
            ("Straße reference", "https://example.org/unicode", 20, 0),
            ("100%_literal", "https://example.org/literal", 30, 0),
        ])
        db.commit()
        return db

    def bookmarks(self, profile=None):
        (profile or self.profile).joinpath("Bookmarks").write_text(json.dumps({"roots": {"bookmark_bar": {
            "type": "folder", "children": [{"type": "folder", "children": [
                {"type": "url", "name": "Keystroke bookmark", "url": "https://example.org/docs", "date_added": "50"},
                {"type": "url", "name": "Keystroke saved", "url": "https://example.org/saved", "date_added": "60"},
                {"type": "url", "name": "Keystroke script", "url": "javascript:alert(1)"}
            ]}]}}}))

    def search(self, query="keystroke", **kwargs):
        return browser.search(query, home=self.home, config=self.config, desktop=kwargs.pop("desktop", "chromium.desktop"), **kwargs)

    def test_merge_and_source_toggles(self):
        self.history().close()
        self.bookmarks()
        result = self.search()
        self.assertEqual(result["browser"], "Chromium")
        self.assertEqual(len(result["results"]), 3)
        shared = next(r for r in result["results"] if r["url"].endswith("/docs"))
        self.assertTrue(shared["bookmark"] and shared["history"])
        with patch.object(browser, "database_rows", side_effect=AssertionError("History accessed")):
            self.assertEqual(len(self.search(history=False)["results"]), 2)
        with patch.object(browser, "bookmark_rows", side_effect=AssertionError("Bookmarks accessed")):
            self.assertEqual(len(self.search(bookmarks=False)["results"]), 2)
        with patch.object(browser, "profiles", side_effect=AssertionError("Detection ran")):
            self.assertEqual(self.search(history=False, bookmarks=False)["results"], [])
            self.assertEqual(self.search("x")["results"], [])

    def test_literal_unicode_and_injection(self):
        self.history().close()
        self.assertEqual(len(self.search("STRASSE", bookmarks=False)["results"]), 1)
        self.assertEqual(len(self.search("%_", bookmarks=False)["results"]), 1)
        self.assertEqual(self.search("' OR 1=1 --")["results"], [])
        self.assertEqual(len(self.search("docs example.org")["results"]), 1)

    def test_live_wal_and_no_database_changes(self):
        db = self.history()
        self.addCleanup(db.close)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("INSERT INTO urls VALUES ('Live page','https://example.org/live',999,0)")
        db.commit()
        files = {p: p.read_bytes() for p in [self.profile / "History", self.profile / "History-wal"]}
        self.assertEqual(len(self.search("live", bookmarks=False)["results"]), 1)
        self.assertEqual(files, {p: p.read_bytes() for p in files})

    def test_profiles_deduplicate_and_ignore_guest(self):
        self.history().close()
        other = self.profile.parent / "Profile 1"
        other.mkdir()
        self.bookmarks(other)
        guest = self.profile.parent / "Guest Profile"
        guest.mkdir()
        self.history(guest).close()
        result = self.search()
        self.assertEqual(len(result["results"]), 3)
        self.assertFalse(any(r["profile"] == "Guest Profile" for r in result["results"]))

    def test_missing_corrupt_and_locked_sources(self):
        self.assertIn("No enabled", self.search()["error"])
        self.bookmarks()
        (self.profile / "History").write_text("invalid database")
        result = self.search()
        self.assertEqual(len(result["results"]), 2)
        self.assertIn("history", result["error"])
        (self.profile / "History").unlink()
        db = self.history()
        self.addCleanup(db.close)
        db.execute("BEGIN EXCLUSIVE")
        self.assertIn("history", self.search()["error"])

    def test_default_browser_and_fallback(self):
        with patch.object(browser.subprocess, "run", return_value=type("Result", (), {"returncode": 0, "stdout": "chromium.desktop\n"})()) as run:
            self.assertEqual(browser.default_browser(), "chromium.desktop")
            self.assertEqual(run.call_count, 1)
        with patch.object(browser.subprocess, "run", side_effect=[FileNotFoundError(), type("Result", (), {"returncode": 0, "stdout": "firefox.desktop\n"})()]):
            self.assertEqual(browser.default_browser(), "firefox.desktop")
        self.assertIn("not supported", self.search(desktop="unknown.desktop")["error"])
        self.assertIn("detect", self.search(desktop="")["error"])

    def test_flatpak_and_other_browser_isolation(self):
        self.history().close()
        self.assertEqual(self.search(desktop="google-chrome.desktop")["results"], [])
        path = self.home / ".var/app/org.chromium.Chromium/config/chromium/Default"
        path.mkdir(parents=True)
        self.bookmarks(path)
        self.assertEqual(len(self.search(desktop="org.chromium.Chromium.desktop")["results"]), 2)

    def test_firefox(self):
        base = self.home / ".mozilla/firefox"
        profile = base / "abc.default-release"
        profile.mkdir(parents=True)
        (base / "profiles.ini").write_text("[Profile0]\nPath=abc.default-release\nIsRelative=1\n")
        db = sqlite3.connect(profile / "places.sqlite")
        db.executescript("""
            CREATE TABLE moz_places (id INTEGER, title TEXT, url TEXT, last_visit_date INTEGER, hidden INTEGER);
            CREATE TABLE moz_bookmarks (fk INTEGER, title TEXT, dateAdded INTEGER, type INTEGER);
            INSERT INTO moz_places VALUES (1,'Keystroke docs','https://example.org/docs',100,0);
            INSERT INTO moz_places VALUES (2,'Keystroke unvisited','https://example.org/saved',NULL,0);
            INSERT INTO moz_bookmarks VALUES (1,'Keystroke saved title',50,1);
            INSERT INTO moz_bookmarks VALUES (2,'Keystroke saved only',60,1);
        """)
        db.close()
        result = self.search(desktop="firefox.desktop")
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(len(self.search(desktop="firefox.desktop", bookmarks=False)["results"]), 1)
        self.assertEqual(len(self.search("saved title", desktop="firefox.desktop", history=False)["results"]), 1)


if __name__ == "__main__":
    unittest.main()
