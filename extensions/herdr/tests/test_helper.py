"""Drive bin/herdr.py against a fake `herdr` CLI and a fake session socket."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELPER = HERE.parent / "bin" / "herdr.py"
sys.path.insert(0, str(HELPER.parent))
import herdr  # noqa: E402

SNAPSHOT = {"focused_pane_id": "pane-1", "workspaces": [{"workspace_id": "workspace-1", "label": "Project"}],
            "tabs": [], "panes": [{"pane_id": "pane-1"}], "agents": [{"pane_id": "pane-1", "agent": "claude"}]}


class FakeSession:
    def __init__(self, path):
        self.requests = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(path)
        self.server.listen()
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                req = json.loads(conn.makefile().readline())
                self.requests.append(req)
                if req["method"] == "session.snapshot":
                    result = {"type": "session_snapshot", "snapshot": SNAPSHOT}
                    conn.sendall((json.dumps({"id": req["id"], "result": result}) + "\n").encode())
                elif req["params"].get("pane_id") == "gone":
                    conn.sendall((json.dumps({"id": req["id"], "error": {"message": "pane not found"}}) + "\n").encode())
                else:
                    conn.sendall((json.dumps({"id": req["id"], "result": {"type": "ok"}}) + "\n").encode())


class HelperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.sock = str(root / "herdr.sock")
        self.session = FakeSession(self.sock)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        listing = {"sessions": [{"name": "default", "running": True, "socket_path": self.sock},
                                {"name": "old", "running": False, "socket_path": self.sock}]}
        for name, body in {
            "herdr": "#!/bin/sh\necho '%s'\n" % json.dumps(listing),
            "hyprctl": "#!/bin/sh\necho '[]'\n",
            "omarchy-launch-terminal": "#!/bin/sh\necho \"$@\" > %s\n" % (root / "launched"),
        }.items():
            (bin_dir / name).write_text(body)
            (bin_dir / name).chmod(0o755)
        self.launched = root / "launched"
        self.env = dict(os.environ, PATH=str(bin_dir) + ":" + os.environ["PATH"])

    def tearDown(self):
        self.session.server.close()
        self.tmp.cleanup()

    def run_helper(self, *args):
        return subprocess.run([sys.executable, str(HELPER), *args], capture_output=True, text=True, env=self.env, timeout=10)

    def test_list_reads_running_sessions_only(self):
        r = self.run_helper("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        value = json.loads(r.stdout)
        self.assertEqual([s["name"] for s in value["sessions"]], ["default"])
        self.assertEqual(value["sessions"][0]["snapshot"]["agents"][0]["agent"], "claude")
        self.assertEqual(value["sessions"][0]["windows"], [])

    def test_focus_sends_the_native_request_then_opens_a_terminal(self):
        r = self.run_helper("focus", "default", "pane", "pane-1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.session.requests[-1]["method"], "pane.focus")
        self.assertEqual(self.session.requests[-1]["params"], {"pane_id": "pane-1"})
        for _ in range(50):
            if self.launched.exists():
                break
            threading.Event().wait(0.05)
        self.assertEqual(self.launched.read_text().split(), ["herdr", "session", "attach", "default"])

    def test_focus_refuses_bad_targets(self):
        self.assertEqual(self.run_helper("focus", "default", "shell", "x").returncode, 2)
        self.assertEqual(self.run_helper("focus", "default", "pane", "a\nb").returncode, 2)
        self.assertEqual(self.run_helper("focus", "nope", "pane", "pane-1").returncode, 1)
        self.assertEqual(self.run_helper("focus", "default", "pane", "gone").returncode, 1)

    def test_client_session_and_hosts(self):
        self.assertEqual(herdr.client_session(["herdr"]), "default")
        self.assertEqual(herdr.client_session(["/usr/bin/herdr", "--session", "work"]), "work")
        self.assertEqual(herdr.client_session(["herdr", "session", "attach", "work"]), "work")
        self.assertEqual(herdr.client_session(["herdr", "--session=work"]), "work")
        self.assertIsNone(herdr.client_session(["herdr", "--remote", "workbox"]))
        self.assertIsNone(herdr.client_session(["herdr", "--remote=workbox", "--session", "work"]))
        self.assertIsNone(herdr.client_session(["herdr", "--no-session"]))
        self.assertIsNone(herdr.client_session(["herdr", "server"]))
        self.assertIsNone(herdr.client_session(["herdr", "session", "list"]))
        self.assertIsNone(herdr.client_session(["herdr", "pane", "list"]))
        self.assertIsNone(herdr.client_session(["vim"]))
        table = {10: {"ppid": 1, "argv": ["kitty"]}, 11: {"ppid": 10, "argv": ["zsh"]}, 12: {"ppid": 11, "argv": ["herdr"]},
                 20: {"ppid": 1, "argv": ["foot", "--server"]}, 21: {"ppid": 20, "argv": ["herdr", "--session", "x"]}}
        clients = [{"pid": 10, "address": "0xAA", "focusHistoryID": 2},
                   {"pid": 20, "address": "0xbb"}, {"pid": 20, "address": "0xcc"}]
        self.assertEqual(herdr.hosts(table, clients), {"default": ["0xaa"]})
        self.assertEqual(herdr.address("0xzz"), "")


if __name__ == "__main__":
    unittest.main()
