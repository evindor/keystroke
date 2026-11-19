import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

improve = runpy.run_path(str(Path(__file__).resolve().parents[1] / "bin/improve.py"))["improve"]


class ImproveTest(unittest.TestCase):
    def test_omarchy_codex_uses_current_account_and_stdin(self):
        config = {"provider": "omarchy", "omarchyPath": "/test/omarchy", "text": "fix me"}
        env = {"CODEX_HOME": "/stale", "OMARCHY_AGENT_CODEX_HOME": "/stale", "PATH": "/bin"}
        with patch.dict(os.environ, env, clear=True):
            with patch("subprocess.check_output", side_effect=["codex\n", "/selected\n"]) as lookup:
                with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "Fix me.\n", "")) as run:
                    self.assertEqual(improve(config), {"text": "Fix me."})
        self.assertEqual([call.args[0] for call in lookup.call_args_list],
                         [["omarchy-default-agent"], ["omarchy-agent-account-home", "codex"]])
        args, kwargs = run.call_args
        self.assertIn("read-only", args[0])
        self.assertNotIn("fix me", args[0])
        self.assertTrue(kwargs["input"].endswith("\nfix me"))
        self.assertEqual(kwargs["env"]["CODEX_HOME"], "/selected")
        self.assertEqual(kwargs["env"]["PATH"], "/test/omarchy/bin:/bin")

    def test_unsupported_or_unset_omarchy_default(self):
        config = {"provider": "omarchy", "text": "fix me"}
        for default, message in [("", "Choose a default agent"), ("pi\n", "does not support")]:
            with self.subTest(default=default):
                with patch("subprocess.check_output", return_value=default) as lookup:
                    self.assertIn(message, improve(config)["error"])
                    lookup.assert_called_once()

    def test_providers_and_key_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "key"
            key_file.write_text("file-key\n", encoding="utf-8")
            for provider, domain, path, key in [
                ("openai", "api.openai.com", "", "env-key"),
                ("grok", "api.x.ai", str(key_file), "file-key"),
            ]:
                with self.subTest(provider=provider), patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
                    response = io.StringIO('{"choices":[{"message":{"content":"Bonjour !"}}]}')
                    with patch("urllib.request.OpenerDirector.open", return_value=response) as send:
                        result = improve({"provider": provider, "model": "custom-model",
                                          "text": "bonjour\nça va ?", "keyFile": path})
                    request = send.call_args.args[0]
                    self.assertEqual(result, {"text": "Bonjour !"})
                    self.assertEqual(request.full_url, f"https://{domain}/v1/chat/completions")
                    self.assertEqual(request.get_header("Authorization"), f"Bearer {key}")
                    payload = json.loads(request.data)
                    self.assertEqual(payload["model"], "custom-model")
                    system, user = payload["messages"]
                    self.assertEqual(system["role"], "system")
                    self.assertIn("Improve this text", system["content"])
                    self.assertEqual(user, {"role": "user", "content": "bonjour\nça va ?"})

    def test_missing_key_skips_network(self):
        with patch.dict(os.environ, {}, clear=True), patch("urllib.request.OpenerDirector.open") as send:
            result = improve({"provider": "grok", "model": "my-model", "text": "Hello"})
        send.assert_not_called()
        self.assertIn("XAI_API_KEY", result["error"])

    def test_http_error_does_not_expose_response(self):
        failure = HTTPError("https://api.x.ai", 401, "secret", {}, None)
        with patch.dict(os.environ, {"XAI_API_KEY": "test-key"}):
            with patch("urllib.request.OpenerDirector.open", side_effect=failure):
                result = improve({"provider": "grok", "model": "my-model", "text": "Hello"})
        self.assertEqual(result, {"error": "Grok returned HTTP 401. Check your API key."})


if __name__ == "__main__":
    unittest.main()
