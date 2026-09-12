#!/usr/bin/env python3
"""bin/search.py against a local GIPHY stand-in: key handling and error text."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

HELPER = str(Path(__file__).resolve().parents[1] / "bin" / "search.py")
KEY = "abcdef0123456789abcdef0123456789"
BODY = {"data": [], "meta": {"status": 200, "msg": "OK"}, "pagination": {"offset": 0, "count": 0, "total_count": 0}}


class Handler(BaseHTTPRequestHandler):
    status = 200
    junk = False
    seen = []

    def do_GET(self):
        parts = urlsplit(self.path)
        Handler.seen.append((parts.path, parse_qs(parts.query)))
        self.send_response(Handler.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"<html>captive portal</html>" if Handler.junk else json.dumps(BODY).encode())

    def log_message(self, *args):
        pass


class SearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d/v1/gifs/" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_helper(self, *args, key=KEY, base=None):
        env = dict(os.environ, GIPHY_API_BASE=base or self.base)
        env.pop("GIPHY_API_KEY", None)
        if key is not None:
            env["GIPHY_API_KEY"] = key
        return subprocess.run([sys.executable, HELPER, *args], capture_output=True, text=True, timeout=30, env=env)

    def setUp(self):
        Handler.status = 200
        Handler.junk = False
        Handler.seen = []

    def test_search_sends_query_rating_and_key(self):
        result = self.run_helper("search", "--query", "happy cat", "--offset", "24", "--rating", "pg-13")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["meta"]["status"], 200)
        path, query = Handler.seen[0]
        self.assertEqual(path, "/v1/gifs/search")
        self.assertEqual(query["q"], ["happy cat"])
        self.assertEqual(query["rating"], ["pg-13"])
        self.assertEqual(query["offset"], ["24"])
        self.assertEqual(query["api_key"], [KEY])

    def test_trending_omits_the_query(self):
        self.assertEqual(self.run_helper("trending").returncode, 0)
        path, query = Handler.seen[0]
        self.assertEqual(path, "/v1/gifs/trending")
        self.assertNotIn("q", query)

    def test_key_is_never_in_argv(self):
        # The whole point of reading it from the environment.
        result = self.run_helper("search", "--query", "x")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn(KEY, " ".join([HELPER, "search", "--query", "x"]))

    def test_missing_key_explains_itself(self):
        result = self.run_helper("search", "--query", "x", key=None)
        self.assertEqual(result.returncode, 1)
        self.assertIn("No GIPHY API key set", result.stdout)
        self.assertEqual(Handler.seen, [])

    def test_mispasted_key_is_refused_before_the_request(self):
        result = self.run_helper("search", "--query", "x", key="https://developers.giphy.com/dashboard/")
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not look like a GIPHY API key", result.stdout)
        self.assertEqual(Handler.seen, [])

    def test_rejected_key_and_rate_limit_have_their_own_messages(self):
        for status, expected in ((401, "rejected the API key"), (403, "rejected the API key"),
                                 (429, "rate limit reached"), (500, "HTTP 500")):
            Handler.status = status
            result = self.run_helper("search", "--query", "x")
            self.assertEqual(result.returncode, 1)
            self.assertIn(expected, result.stdout)
            self.assertNotIn(KEY, result.stdout + result.stderr)

    def test_unreachable_host_and_junk_body_stay_readable(self):
        result = self.run_helper("search", "--query", "x", base="http://127.0.0.1:1/v1/gifs/")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Could not reach GIPHY", result.stdout)
        self.assertNotIn(KEY, result.stdout + result.stderr)
        Handler.junk = True
        junk = self.run_helper("search", "--query", "x")
        self.assertEqual(junk.returncode, 1)
        self.assertIn("unreadable response", junk.stdout)

    def test_bad_rating_is_refused_by_the_parser(self):
        result = self.run_helper("search", "--query", "x", "--rating", "xxx")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(Handler.seen, [])


if __name__ == "__main__":
    unittest.main()
