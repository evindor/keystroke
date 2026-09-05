import asyncio
import datetime as dt
import importlib.util
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from flint.api import read_jsonc, run, score
from flint.config import Config
from flint.host import Host, ROOT
from flint.reply import reply
from flint.usage import Usage


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "extensions" / name / "extension.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MathTests(unittest.TestCase):
    def test_arithmetic(self):
        calc = module("calculator").calculate
        for query, value in [("2+3*4", 14), ("(2+3)*4", 20), ("sqrt(144)+15% of 80", 24),
                             ("2^8", 256), ("sin(pi/2)", 1), ("100*5%", 5), ("17%5", 2)]:
            self.assertAlmostEqual(calc(query), value)

    def test_untrusted_math_never_executes(self):
        calc = module("calculator").calculate
        for query in ["__import__('os').system('true')", "(1).__class__", "[0]*10000000", "9**9**9", "1/0", "sqrt(-1)", "1e999"]:
            with self.assertRaises((ValueError, SyntaxError, OverflowError, ZeroDivisionError)):
                calc(query)

    def test_units_and_dimensions(self):
        convert = module("converter").convert
        self.assertAlmostEqual(convert("2m in feet")[0], 6.561679790026246)
        self.assertEqual(convert("32 F to C")[0], 0)
        self.assertEqual(convert("1 GiB in MiB")[0], 1024)
        with self.assertRaises(ValueError):
            convert("1 kg in m")
        with self.assertRaises(ValueError):
            convert("-1 K to C")

    def test_timezones_and_date_rollover(self):
        convert = module("converter").convert_time
        result, _ = convert("10 am in london on 2026-09-06", "Europe/Tallinn")
        self.assertEqual((result.hour, result.minute), (12, 0))
        result, _ = convert("11 pm in new york to tokyo on 2026-09-06", "Europe/Tallinn")
        self.assertEqual((result.day, result.hour), (7, 12))

    def test_dst_gap_and_fold_are_not_guessed(self):
        convert = module("converter").convert_time
        for q in ["1:30 am in london on 2026-03-29", "1:30 am in london on 2026-10-25"]:
            with self.assertRaisesRegex(ValueError, "daylight-saving"):
                convert(q, "Europe/Tallinn")


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "config.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_jsonc_strings_comments_and_trailing_commas(self):
        self.path.write_text('{/* c */"url":"https://example.com/a//b", "text":"a,} \\\"b", // hi\n"values":[1,2,],}')
        data = read_jsonc(self.path)
        self.assertEqual(data["url"], "https://example.com/a//b")
        self.assertEqual(data["values"], [1, 2])

    def test_atomic_settings_preserve_unknown_fields(self):
        self.path.write_text(json.dumps({"version": 1, "future": {"x": 1}, "extensions": {}}))
        c = Config(self.path)
        m = {"id": "test.one", "settings": [{"key": "mode", "type": "enum", "options": ["a", "b"], "default": "a"}]}
        c.set(m, "mode", "b")
        self.assertEqual(Config(self.path).settings(m)["mode"], "b")
        self.assertEqual(json.loads(self.path.read_text())["future"], {"x": 1})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_broken_config_is_not_overwritten(self):
        c = Config(self.path)
        self.path.write_text("{ broken")
        with self.assertRaises(ValueError):
            c.set({"id": "test.one"}, "enabled", True)
        self.assertEqual(self.path.read_text(), "{ broken")

    def test_bad_setting_types_fall_back(self):
        self.path.write_text(json.dumps({"version": 1, "extensions": {"test.one": {"n": 2.5}}}))
        m = {"id": "test.one", "settings": [{"key": "n", "type": "number", "integer": True, "default": 10}]}
        self.assertEqual(Config(self.path).settings(m)["n"], 10)

    def test_picker_reply_and_cancel(self):
        done = Path(self.temp.name) / "done"
        reply(str(self.path), str(done), "duplicate\tstable key")
        self.assertTrue(done.exists())
        self.assertEqual(self.path.read_text(), "duplicate\tstable key\n")
        done.unlink()
        reply(str(self.path), str(done), None)
        self.assertTrue(done.exists())
        self.assertEqual(self.path.read_text(), "")


class HostTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = Config(Path(self.temp.name) / "config.json")
        self.host = Host(self.config, usage_path=Path(self.temp.name) / "usage.json")

    async def test_number_and_partial_expression_stay_in_calculator(self):
        for text, title, disabled in [("22", "22", False), ("22+", "22+ …", True), ("22+1", "23", False)]:
            result = await self.host.query(text, "flint.calculator")
            self.assertEqual(result["rows"][0]["title"], title)
            self.assertEqual(result["rows"][0].get("disabled", False), disabled)
        result = await self.host.query("22+")
        self.assertEqual(result["rows"][0]["extensionId"], "flint.calculator")
        self.assertEqual(await self.host.activate(result["rows"][0]["token"]), {})

    async def test_search_prioritizes_apps_and_learns_selected_app(self):
        self.host.apps = [dict(id="chromium", name="Chromium"), dict(id="google-chrome", name="Google Chrome")]
        result = await self.host.query("chrom")
        self.assertEqual([r["extensionId"] for r in result["rows"][:2]], ["flint.applications"] * 2)
        chrome = next(r for r in result["rows"] if r["title"] == "Google Chrome")
        self.assertFalse(self.host.usage.path.exists())  # Searching isn't usage.
        effect = await self.host.activate(chrome["token"])
        self.assertEqual(effect["launch"][0][-1], "google-chrome.desktop")
        result = await self.host.query("chrom")
        self.assertEqual(result["rows"][0]["title"], "Google Chrome")
        restarted = Host(self.config, usage_path=self.host.usage.path)
        restarted.apps = self.host.apps
        result = await restarted.query("chrom")
        self.assertEqual(result["rows"][0]["title"], "Google Chrome")
        stored = self.host.usage.path.read_text()
        self.assertNotIn("Chrome", stored)
        self.assertNotIn("chrom", stored)

    async def test_fast_providers_are_coalesced(self):
        updates = []
        result = await self.host.query("", "flint.settings", emit=updates.append)
        self.assertFalse(result["pending"])
        self.assertEqual(updates, [])

    async def test_density_schema_defaults_to_compact(self):
        settings = next(e.manifest for e in self.host.extensions if e.id == "flint.settings")
        self.assertEqual(self.config.settings(settings)["density"], "compact")
        self.config.set(settings, "density", "comfortable")
        self.assertEqual((await self.host.query(""))["appearance"]["density"], "comfortable")

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def test_all_bundled_extensions_load(self):
        self.assertEqual(self.host.errors, [])
        self.assertEqual(len(self.host.extensions), 9)
        result = await self.host.query("")
        self.assertEqual(len(result["rows"]), 8)

    async def test_actions_are_opaque_and_expire(self):
        result = await self.host.query("", "flint.calculator")
        result = await self.host.query("", "flint.settings")
        token = result["rows"][0]["token"]
        self.assertNotIn("action", result["rows"][0])
        await self.host.query("", "flint.emoji")
        with self.assertRaises(ValueError):
            await self.host.activate(token)

    async def test_query_never_launches_an_action(self):
        with patch("flint.host.run", side_effect=AssertionError("query must not run actions")):
            result = await self.host.query("", "flint.settings/flint.ai")
            self.assertEqual(len(result["rows"]), 3)

    async def test_disable_and_reenable_persist(self):
        m = next(e.manifest for e in self.host.extensions if e.id == "flint.emoji")
        self.config.set(m, "enabled", False)
        result = await self.host.query("")
        self.assertNotIn("Emoji Picker", [r["title"] for r in result["rows"]])
        self.config.set(m, "enabled", True)
        self.assertIn("Emoji Picker", [r["title"] for r in (await self.host.query(""))["rows"]])

    async def test_external_extension_disabled_until_enabled(self):
        path = Path(self.temp.name) / "extensions/hello"
        shutil.copytree(ROOT / "examples/hello", path)
        host = Host(self.config)
        ext = next(e for e in host.extensions if e.id == "example.hello")
        self.assertFalse(self.config.enabled(ext.manifest))
        self.config.set(ext.manifest, "enabled", True)
        result = await host.query("hello Flint", "example.hello")
        self.assertEqual(result["rows"][0]["title"], "Hello, Flint!")
        self.assertEqual(result["errors"], [])

    async def test_external_timeout_does_not_block_other_results(self):
        path = Path(self.temp.name) / "extensions/slow"
        path.mkdir(parents=True)
        manifest = dict(apiVersion=1, id="test.slow", name="Slow", command=["python", "-c", "import time; time.sleep(10)"],
                        timeoutMs=50, minQueryLength=0, permissions=[])
        (path / "manifest.json").write_text(json.dumps(manifest))
        self.config.set(manifest, "enabled", True)
        host = Host(self.config)
        emissions = []
        result = await host.query("", emit=lambda r: emissions.append(r))
        self.assertEqual(len(result["rows"]), 8)
        self.assertTrue(any("Slow" in e for e in result["errors"]))
        self.assertTrue(any(e["rows"] and e["pending"] for e in emissions))

    async def test_timeout_output_bound_and_cancellation(self):
        with self.assertRaises(asyncio.TimeoutError):
            await run(["python", "-c", "import time;time.sleep(10)"], timeout=.03)
        with self.assertRaises(ValueError):
            await run(["python", "-c", "print('x'*10000)"], limit=100)
        task = asyncio.create_task(run(["python", "-c", "import time;time.sleep(10)"]))
        await asyncio.sleep(.02)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_permissions_and_literal_prompt_arguments(self):
        with self.assertRaises(ValueError):
            Host.validate_action({"type": "exec", "argv": ["echo", "test"]}, {"permissions": []})
        with self.assertRaises(ValueError):
            Host.validate_action({"type": "url", "url": "javascript:alert(1)"}, {"permissions": ["open-url"]})
        payload = "--help $(touch /tmp/flint-should-not-exist) `id` \"quoted\""
        action = module("ai").ai_action("claude", "cli", payload)
        self.assertEqual(action["argv"][-2:], ["--", payload])


class MenuTests(unittest.IsolatedAsyncioTestCase):
    async def test_menu_override_alias_link_and_ancestor_guard(self):
        mod = module("omarchy")
        with tempfile.TemporaryDirectory() as temp:
            default, user = Path(temp)/"default", Path(temp)/"user"
            default.write_text(json.dumps({"setup": {"label": "Setup", "when": "false"},
                "setup.child": {"label": "Original", "action": "true"},
                "shortcut": {"label": "Link", "target": "setup", "aliases": ["s"]}}))
            user.write_text(json.dumps({"setup.child": {"label": "Mine", "action": "echo literal"}}))
            items = mod.load_menu([default, user])
            self.assertEqual(items["setup.child"]["label"], "Mine")
            self.assertEqual(mod.resolve(items, "s"), "setup")
            checks = await mod.guards(mod.ancestors(items, "setup.child"), {})
            self.assertFalse(checks["false"])

    async def test_cycles_are_bounded(self):
        mod = module("omarchy")
        items = {"a": {"parent": "b", "target": "b"}, "b": {"parent": "a", "target": "a"}}
        self.assertEqual(len(mod.ancestors(items, "a")), 2)
        self.assertIn(mod.resolve(items, "a"), items)


class RankingTests(unittest.TestCase):
    def test_word_matching_without_unrelated_fuzzy_results(self):
        self.assertGreater(score("chrome", "Google Chrome"), 100)
        self.assertEqual(score("chrome", "Chromium"), 0)
        self.assertEqual(score("chrome", "Flint Settings", "preferences configuration"), 0)
        self.assertGreater(score("chrom", "Google Chrome"), score("chrom", "Default browser", "Chrome"))
        self.assertGreater(score("chroe", "Google Chrome"), 0)
        self.assertEqual(score("cme", "Chrome"), 0)
        self.assertGreater(score("code", "Visual Studio Code"), 0)

    def test_frecency_halves_in_two_weeks_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            now = [1_800_000_000]
            path = Path(temp) / "usage.json"
            usage = Usage(path, clock=lambda: now[0])
            key = usage.key("test.apps", "chrome")
            usage.record(key)
            usage.record(key)
            self.assertEqual(usage.weight(key), 2)
            now[0] += Usage.HALF_LIFE
            self.assertAlmostEqual(usage.weight(key), 1)
            self.assertAlmostEqual(Usage(path, clock=lambda: now[0]).weight(key), 1)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_corrupt_usage_file_is_recoverable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "usage.json"
            path.write_text("{ broken")
            usage = Usage(path)
            self.assertEqual(usage.entries, {})
            usage.record(usage.key("test.apps", "one"))
            self.assertEqual(len(Usage(path).entries), 1)


if __name__ == "__main__":
    unittest.main()
