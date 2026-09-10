#!/usr/bin/env python3
"""Unit tests for the pure parts of bin/keyboard-cleaner.

    python3 tests/test_helper.py

Device selection and the Lua call the names are quoted into. Nothing here
talks to Hyprland; README.md describes the live check.
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


class SelectionTests(unittest.TestCase):
    def test_keyboards_and_pointers(self):
        self.assertEqual(helper.select_devices(DEVICES, keep_pointer=False),
                         ["at-translated-set-2-keyboard", "video-bus", "ven_2c2f:00-2c2f:0034-mouse", "ven_2c2f:00-2c2f:0034-touchpad"])

    def test_keep_pointer(self):
        self.assertEqual(helper.select_devices(DEVICES, keep_pointer=True), ["at-translated-set-2-keyboard", "video-bus"])

    def test_escape_hatches_and_virtual_devices_are_skipped(self):
        names = helper.select_devices(DEVICES, keep_pointer=False)
        for skipped in ("power-button", "sleep-button", "hl-virtual-keyboard-fcitx5"):
            self.assertNotIn(skipped, names)

    def test_names_with_control_characters_are_refused(self):
        self.assertFalse(helper.usable("bad\nname"))
        self.assertFalse(helper.usable("bad\x7f"))
        self.assertFalse(helper.usable(None))
        self.assertTrue(helper.usable('Keyboard "Deluxe" 2'))

    def test_explicit_names_may_be_escape_hatches(self):
        self.assertTrue(helper.safe_name("sleep-button"))
        self.assertFalse(helper.usable("sleep-button"))

    def test_empty_listing(self):
        self.assertEqual(helper.select_devices({}, keep_pointer=False), [])

    def test_switches_are_skipped_whatever_their_name(self):
        # Hyprland lists one physical device in two spellings — Apple SMC's
        # power and lid events appear as `apple-smc-power/lid-events` under
        # keyboards and `Apple SMC power/lid events` under switches — so a
        # block must leave it alone however it is spelled.
        apple = {
            "keyboards": [{"name": "apple-spi-keyboard"}, {"name": "apple-smc-power/lid-events"}],
            "mice": [{"name": "apple-spi-trackpad"}],
            "switches": [{"name": "Apple SMC power/lid events"}],
        }
        self.assertEqual(helper.select_devices(apple, keep_pointer=False),
                         ["apple-spi-keyboard", "apple-spi-trackpad"])
        self.assertEqual(helper.select_devices(apple, keep_pointer=True), ["apple-spi-keyboard"])

    def test_power_and_lid_names_are_skipped_by_fragment(self):
        for skipped in ("apple-smc-power/lid-events", "Power Button", "sleep-button", "lid-switch"):
            self.assertFalse(helper.usable(skipped), skipped)
        self.assertTrue(helper.usable("apple-spi-keyboard"))


class LuaTests(unittest.TestCase):
    def test_plain_name(self):
        self.assertEqual(helper.lua_call("at-translated-set-2-keyboard", False),
                         'hl.device({ name = "at-translated-set-2-keyboard", enabled = false })')

    def test_quotes_and_backslashes_stay_data(self):
        self.assertEqual(helper.lua_call('Key "board" \\ 1', True),
                         'hl.device({ name = "Key \\"board\\" \\\\ 1", enabled = true })')


if __name__ == "__main__":
    unittest.main()
