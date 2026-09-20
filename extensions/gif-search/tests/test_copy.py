import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import io

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("gif_copy", Path(__file__).resolve().parents[1] / "bin/copy.py")
copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)


class Response(io.BytesIO):
    headers = {}


class CopyTests(unittest.TestCase):
    def test_url_boundary(self):
        for url in ["file:///tmp/a", "http://giphy.com/a", "https://giphy.com.evil.org/a",
                    "https://x@giphy.com/a", "https://giphy.com:999/a"]:
            with self.assertRaises(ValueError):
                copy.checked_url(url)
        self.assertEqual(copy.checked_url("https://media2.giphy.com/a.gif"), "https://media2.giphy.com/a.gif")

    def test_link_never_downloads(self):
        with patch.object(copy.urllib.request, "build_opener") as opener:
            self.assertEqual(copy.payload("link", "https://media.giphy.com/a.gif"),
                             ("text/plain;charset=utf-8", b"https://media.giphy.com/a.gif"))
            opener.assert_not_called()

    def test_binary_and_failures(self):
        with patch.object(copy.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = Response(b"GIF89a\x00\xff")
            self.assertEqual(copy.payload("gif", "https://giphy.com/a.gif"), ("image/gif", b"GIF89a\x00\xff"))
            for data in [b"<html>error</html>", b"GIF89a" + b"x" * copy.MAX_BYTES]:
                opener.return_value.open.return_value = Response(data)
                with self.assertRaises(ValueError):
                    copy.payload("gif", "https://giphy.com/a.gif")

    def test_clipboard_bytes_and_error(self):
        with patch.object(sys, "argv", ["copy.py", "gif", "https://giphy.com/a.gif"]), \
                patch.object(copy, "payload", return_value=("image/gif", b"GIF89a\x00\xff")), \
                patch.object(copy.subprocess, "run") as run:
            self.assertEqual(copy.main(), 0)
            self.assertEqual(run.call_args.args[0], ["wl-copy", "--type", "image/gif"])
            self.assertEqual(run.call_args.kwargs["input"], b"GIF89a\x00\xff")
            run.side_effect = subprocess.CalledProcessError(1, "wl-copy")
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(copy.main(), 1)
                self.assertIn("Copy failed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
