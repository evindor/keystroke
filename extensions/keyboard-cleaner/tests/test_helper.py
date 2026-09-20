#!/usr/bin/env python3
"""Unit tests for the pure parts of bin/keyboard-cleaner.

    python3 tests/test_helper.py

Device selection, the Lua call the names are quoted into, the held-key probe
output and the idle-parking bookkeeping. Nothing here talks to Hyprland;
README.md describes the live checks.
"""
import importlib.machinery
import importlib.util
from pathlib import Path
import unittest

HELPER = Path(__file__).resolve().parents[1] / "bin" / "keyboard-cleaner"
loader = importlib.machinery.SourceFileLoader("keyboard_cleaner", str(HELPER))
spec = importlib.util.spec_from_loader("keyboard_cleaner", loader)
helper = importlib.util.module_from_spec(spec)
loader.exec_module(helper)

DEVICES = {
    "mice": [{"name": "ven_2c2f:00-2c2f:0034-mouse"}, {"name": "ven_2c2f:00-2c2f:0034-touchpad"}],
    "keyboards": [{"name": "at-translated-set-2-keyboard"}, {"name": "power-button"}, {"name": "sleep-button"},
                  {"name": "hl-virtual-keyboard-fcitx5"}, {"name": "video-bus"}, {"name": ""}, {"address": "0x1"}],
}

APPLE = {
    "keyboards": [{"name": "apple-spi-keyboard"}, {"name": "apple-smc-power/lid-events"}],
    "mice": [{"name": "apple-spi-trackpad"}],
    "switches": [{"name": "Apple SMC power/lid events"}],
}


class SelectionTests(unittest.TestCase):
    def test_keyboards_and_pointers(self):
        self.assertEqual(helper.select_devices(DEVICES, keep_pointer=False),
                         ["at-translated-set-2-keyboard", "power-button", "sleep-button", "video-bus",
                          "ven_2c2f:00-2c2f:0034-mouse", "ven_2c2f:00-2c2f:0034-touchpad"])

    def test_keep_pointer(self):
        self.assertEqual(helper.select_devices(DEVICES, keep_pointer=True),
                         ["at-translated-set-2-keyboard", "power-button", "sleep-button", "video-bus"])

    def test_virtual_keyboards_are_skipped(self):
        names = helper.select_devices(DEVICES, keep_pointer=False)
        self.assertNotIn("hl-virtual-keyboard-fcitx5", names)
        self.assertFalse(helper.usable("hl-virtual-keyboard-fcitx5"))
        self.assertFalse(helper.usable("hl-virtual-pointer-1"))

    def test_unnamed_entries_are_skipped(self):
        names = helper.select_devices(DEVICES, keep_pointer=False)
        self.assertNotIn("", names)
        self.assertFalse(helper.usable(None))

    def test_power_lid_node_is_inside_the_block(self):
        # Hyprland lists the Apple SMC power/lid node as a keyboard, and
        # XF86PowerOff opens Omarchy's power menu (Screensaver, Lock, Log out,
        # Reboot, Shut down). Leaving it outside the block let a cloth wiping
        # the keyboard end the session at any block length, so it is blocked
        # like any other keyboard now — the same device still reaches logind,
        # which handles a lid close on its own.
        self.assertEqual(helper.select_devices(APPLE, keep_pointer=False),
                         ["apple-spi-keyboard", "apple-smc-power/lid-events", "apple-spi-trackpad"])
        self.assertEqual(helper.select_devices(APPLE, keep_pointer=True),
                         ["apple-spi-keyboard", "apple-smc-power/lid-events"])
        self.assertTrue(helper.usable("apple-smc-power/lid-events"))

    def test_power_button_names_are_inside_the_block(self):
        for blocked in ("power-button", "sleep-button", "Power Button", "lid-switch"):
            self.assertTrue(helper.usable(blocked), blocked)
        self.assertTrue(helper.usable("apple-spi-keyboard"))

    def test_names_with_control_characters_are_refused(self):
        self.assertFalse(helper.usable("bad\nname"))
        self.assertFalse(helper.usable("bad\x7f"))
        self.assertFalse(helper.usable(None))
        self.assertTrue(helper.usable('Keyboard "Deluxe" 2'))

    def test_empty_listing(self):
        self.assertEqual(helper.select_devices({}, keep_pointer=False), [])


class LuaTests(unittest.TestCase):
    def test_plain_name(self):
        self.assertEqual(helper.lua_call("at-translated-set-2-keyboard", False),
                         'hl.device({ name = "at-translated-set-2-keyboard", enabled = false })')

    def test_quotes_and_backslashes_stay_data(self):
        self.assertEqual(helper.lua_call('Key "board" \\ 1', True),
                         'hl.device({ name = "Key \\"board\\" \\\\ 1", enabled = true })')


class ProbeOutputTests(unittest.TestCase):
    def test_reads_the_keycodes_the_lua_side_wrote(self):
        self.assertEqual(helper.keys_from_probe_output("191,29"), [191, 29])

    def test_empty_output_means_nothing_is_held(self):
        self.assertEqual(helper.keys_from_probe_output(""), [])
        self.assertEqual(helper.keys_from_probe_output("   "), [])

    def test_junk_and_out_of_range_values_are_ignored(self):
        self.assertEqual(helper.keys_from_probe_output("ok:191,,abc,0,999,9"), [191, 9])

    def test_duplicates_collapse(self):
        self.assertEqual(helper.keys_from_probe_output("30,30,31"), [30, 31])


class WaitForReleaseTests(unittest.TestCase):
    def test_returns_true_when_nothing_is_held(self):
        self.assertTrue(helper.wait_for_release(read=lambda: [], timeout=0.01, sleep=lambda _s: None))

    def test_returns_false_when_a_key_stays_down(self):
        self.assertFalse(helper.wait_for_release(read=lambda: [30], timeout=0.01, sleep=lambda _s: None))

    def test_waits_until_the_key_comes_up(self):
        seen = {"calls": 0}

        def read():
            seen["calls"] += 1
            return [30] if seen["calls"] == 1 else []

        self.assertTrue(helper.wait_for_release(read=read, timeout=1.0, sleep=lambda _s: None))
        self.assertEqual(seen["calls"], 2)


class IdleParkingTests(unittest.TestCase):
    def test_status_json_drives_the_parked_decision(self):
        self.assertTrue(helper.idle_parked_from_status('{"stayAwake":true,"idle":false}'))
        self.assertFalse(helper.idle_parked_from_status('{"stayAwake":false}'))
        self.assertFalse(helper.idle_parked_from_status("not json"))

    def test_marker_owner(self):
        self.assertEqual(helper.marker_owner("4242"), 4242)
        self.assertEqual(helper.marker_owner(""), 0)
        self.assertEqual(helper.marker_owner(None), 0)
        self.assertEqual(helper.marker_owner("nonsense"), 0)

    def test_marker_pid_must_still_be_a_helper(self):
        # A pid can be reused by an unrelated process after a crash; only a
        # running keyboard-cleaner at that pid keeps the marker alive.
        self.assertTrue(helper.is_helper_pid(4242, cmdline_of=lambda p: b"python3\0/x/bin/keyboard-cleaner\0--seconds\x0030\0"))
        self.assertFalse(helper.is_helper_pid(4242, cmdline_of=lambda p: b"/usr/bin/firefox\0"))
        self.assertFalse(helper.is_helper_pid(4242, cmdline_of=lambda p: (_ for _ in ()).throw(FileNotFoundError())))
        self.assertFalse(helper.is_helper_pid(0))

    def test_marker_paths_are_outside_the_plugin(self):
        self.assertIn("keyboard-cleaner", str(helper.PARK_MARKER))
        self.assertTrue(str(helper.PARK_MARKER).endswith("idle-parked"))


if __name__ == "__main__":
    unittest.main()
