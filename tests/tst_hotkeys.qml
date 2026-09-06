import QtQuick
import QtTest
import "../core/Hotkeys.js" as Hotkeys

TestCase {
    name: "Hotkeys"
    property var settings: ({ limit: 10, keyboardOnly: true })
    // Records as omarchy-menu-keybindings' output_binding_records prints them: display, dispatcher, arg.
    property string records:
        "SUPER + K                           → Keybindings\texec\tomarchy-menu-keybindings\n" +
        "SUPER + RETURN                      → Terminal\texec\tomarchy-launch-terminal\n" +
        "SUPER SHIFT + RETURN                → Browser\texec\tomarchy-launch-browser\n" +
        "SUPER + F                           → Full screen\tlua\thl.dsp.window.fullscreen({ mode = \"fullscreen\" })\n" +
        "SUPER ALT + F                       → Full width\tlua\thl.dsp.window.fullscreen({ mode = \"maximized\" })\n" +
        "SUPER + W                           → Close window (tab in Chromium)\t\t\n" +
        "SUPER SHIFT ALT + B                 → Browser (private)\texec\tomarchy-launch-browser --private\n" +
        "SUPER SHIFT + B                     → Browser\texec\tomarchy-launch-browser\n" +
        "SUPER ALT + B                       → Browser\texec\tomarchy-launch-browser --work\n" +
        "PRINT                               → Screenshot\texec\tomarchy-capture-screenshot\n" +
        "SHIFT ALT + L                       → Copy URL from Web App\tsendshortcut\tSHIFT ALT,L,\n" +
        "SUPER + code:20                     → Mystery\texec\techo a,b\tc\n" +
        "                                    → No combo\texec\tx\n" +
        "garbage without an arrow\n\n"

    function test_parse_reads_records_and_merges_duplicate_binds() {
        var binds = Hotkeys.parse(records)
        compare(binds.map(function(b) { return b.id }), ["keybindings", "terminal", "browser", "full-screen", "full-width", "close-window-tab-in-chromium", "browser-private", "browser-2", "screenshot", "copy-url-from-web-app", "mystery"])
        compare(binds[3], { id: "full-screen", label: "Full screen", combos: ["SUPER + F"], dispatcher: "lua", arg: "hl.dsp.window.fullscreen({ mode = \"fullscreen\" })", order: 3 })
        // Browser is bound twice to the same command: one bind, two combos, the first position.
        compare(binds[2].combos, ["SUPER SHIFT + RETURN", "SUPER SHIFT + B"])
        // A different action under the same label stays its own bind with its own id.
        compare(binds[7].label, "Browser")
        compare(binds[7].id, "browser-2")
        compare(binds[7].combos, ["SUPER ALT + B"])
        // A tab inside the argument survives.
        compare(binds[10].arg, "echo a,b\tc")
        compare(binds[5].dispatcher, "")
        compare(binds[9].arg, "SHIFT ALT,L,")
        compare(Hotkeys.parse("").length, 0)
    }

    function test_keys_are_readable() {
        compare(Hotkeys.keys("SUPER + F"), "Super + F")
        compare(Hotkeys.keys("SUPER SHIFT + RETURN"), "Super + Shift + ↵")
        compare(Hotkeys.keys("SUPER SHIFT CTRL + SPACE"), "Super + Shift + Ctrl + Space")
        compare(Hotkeys.keys("CTRL ALT + DELETE"), "Ctrl + Alt + Del")
        compare(Hotkeys.keys("PRINT"), "Print")
        compare(Hotkeys.keys("SUPER + 1"), "Super + 1")
        compare(Hotkeys.keys("SUPER + F11"), "Super + F11")
        compare(Hotkeys.keys("SUPER + COMMA"), "Super + ,")
        compare(Hotkeys.keys("SUPER + LEFT"), "Super + ←")
        compare(Hotkeys.keys("XF86AudioRaiseVolume"), "Audio Raise Volume")
        compare(Hotkeys.keys("SUPER + LEFT MOUSE BUTTON"), "Super + Left click")
        compare(Hotkeys.keys("SUPER + code:20"), "Super + code:20")
        compare(Hotkeys.keys(""), "")
    }

    function test_argv_is_literal() {
        var load = Hotkeys.loadArgv("/usr/share/omarchy")
        compare(load[0], "bash")
        compare(load[3], "/usr/share/omarchy/bin/omarchy-menu-keybindings")
        verify(load[2].indexOf("output_binding_records") > 0)
        var run = Hotkeys.dispatchArgv("/usr/share/omarchy", "exec", "echo \"$(rm -rf ~)\"; hi")
        compare(run.length, 6)
        compare(run[3], "/usr/share/omarchy/bin/omarchy-menu-keybindings")
        compare(run[4], "exec")
        // The argument is passed, never interpolated into the script.
        compare(run[5], "echo \"$(rm -rf ~)\"; hi")
        verify(run[2].indexOf("rm") < 0)
        verify(run[2].indexOf("dispatch_binding \"$1\" \"$2\"") > 0)
    }

    function test_screen_lists_every_bind_in_menu_order() {
        var binds = Hotkeys.parse(records)
        var rows = Hotkeys.rows("", binds, settings, true)
        compare(rows.length, binds.length)
        compare(rows[0].title, "Keybindings")
        compare(rows[0].accessory, "Super + K")
        compare(rows[0].subtitle, "omarchy-menu-keybindings")
        compare(rows[0].section, "Hotkeys")
        compare(rows[0].action, { type: "hotkey", dispatcher: "exec", arg: "omarchy-menu-keybindings" })
        compare(rows[0].remember, true)
        compare(rows[2].accessory, "Super + Shift + ↵  ·  Super + Shift + B")
        compare(rows[3].subtitle, "Hyprland window.fullscreen({ mode = \"fullscreen\" })")
        // A bind without a dispatcher is shown for learning but cannot be run.
        compare(rows[5].disabled, true)
        compare(rows[5].remember, false)
        compare(rows[5].subtitle, "Only from the keyboard")
        compare(rows[5].action, { type: "noop" })
        compare(rows[5].accessory, "Super + W")
        compare(Hotkeys.rows("", binds, { limit: 10, keyboardOnly: false }, true).length, binds.length - 1)
        // Nothing at the root without a query: the nav row is the provider's business.
        compare(Hotkeys.rows("", binds, settings, false).length, 0)
    }

    function test_root_finds_binds_by_abbreviation_keys_and_command() {
        var binds = Hotkeys.parse(records)
        var titles = function(q, s) { return Hotkeys.rows(q, binds, s || settings, false).map(function(r) { return r.title }) }
        compare(titles("flcrn")[0], "Full screen")
        compare(titles("full screen")[0], "Full screen")
        // The keys spelled out pick the bind on exactly those keys over Full width on Super + Alt + F.
        compare(titles("super f")[0], "Full screen")
        compare(titles("super alt f")[0], "Full width")
        compare(titles("SUPER + ALT + F")[0], "Full width")
        compare(titles("omarchy-capture")[0], "Screenshot")
        compare(titles("close win")[0], "Close window (tab in Chromium)")
        compare(titles("zzzz").length, 0)
        var browsers = titles("browser")
        compare(browsers[0], "Browser")
        verify(browsers.indexOf("Browser (private)") > 0)
        compare(titles("b", { limit: 1, keyboardOnly: true }).length, 1)
    }
}
