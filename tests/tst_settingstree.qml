import QtQuick
import QtTest
import "../core/SettingsTree.js" as SettingsTree
import "../core/Match.js" as Match

TestCase {
    name: "SettingsTree"
    function model() {
        return {
            configPath: "/home/x/.config/omarchy/keystroke.json",
            paletteSchema: [
                { key: "density", type: "enum", label: "Layout density", "default": "compact", options: ["compact", "comfortable"], description: "Compact uses a narrower window" },
                { key: "showPreview", type: "boolean", label: "Show result previews", "default": true }
            ],
            paletteValues: { density: "compact", showPreview: true },
            entries: [
                { key: "ai", name: "AI & Web Search", description: "Continue any query in Claude, ChatGPT/Codex or Google", icon: "✳", iconFont: "", color: "#e79c85",
                  source: "bundled", pluginId: "", enabled: true,
                  schemas: [
                      { key: "provider", type: "enum", label: "Preferred assistant", "default": "chatgpt", options: ["chatgpt", "claude"], description: "Listed first among the fallbacks" },
                      { key: "mode", type: "enum", label: "Open conversations in", "default": "desktop", options: ["desktop", "cli", "browser"] },
                      { key: "autoSend", type: "boolean", label: "Send immediately in the browser", "default": false }
                  ],
                  values: { provider: "chatgpt", mode: "desktop", autoSend: false } },
                { key: "clipboard", name: "Clipboard History", description: "Uses Omarchy's existing history", icon: "", iconFont: "", color: "", source: "bundled", pluginId: "", enabled: true,
                  schemas: [{ key: "limit", type: "number", label: "Maximum entries", "default": 100, min: 1, max: 300, integer: true }], values: { limit: 100 } },
                { key: "example.hello", name: "Hello", description: "Says hello", icon: "", iconFont: "", color: "", source: "community", pluginId: "example.hello", enabled: false,
                  schemas: [], values: {} }
            ],
            problems: [{ pluginId: "broken.plugin", message: "no provider" }]
        }
    }
    function search(scope, query) {
        var t = SettingsTree.build(model())
        return Match.rank(SettingsTree.rows(t.nodes, scope, query), null)
    }
    function titles(rows) { return rows.map(function(r) { return r.title }) }

    function test_abbreviations_reach_a_deep_setting_from_the_root() {
        // The setting's config key is `provider`, so "pro"/"prv" reach it
        // through the key even though its label says "assistant".
        var abbreviations = ["prefp", "keysepro", "setaiprv", "preferred", "ai prov", "prov ai", "aiprefp", "pref"]
        for (var i = 0; i < abbreviations.length; i++) {
            var rows = search("", abbreviations[i])
            verify(rows.length > 0, abbreviations[i] + " found nothing")
            compare(rows[0].title, "Preferred assistant", abbreviations[i])
            compare(rows[0].subtitle, "Keystroke Settings › AI & Web Search")
            compare(rows[0].action.type, "navigate")
            compare(rows[0].action.scope, "settings/ai/provider")
            compare(rows[0].accessory, "chatgpt")
        }
    }
    function test_choices_are_reachable_and_selectable_from_anywhere() {
        var rows = search("", "prefcla")
        compare(rows[0].title, "Claude")
        compare(rows[0].icon, "○")
        compare(rows[0].action.type, "setting")
        compare(rows[0].action.value, "claude")
        compare(rows[0].action.path, ["providers", "ai"])
        compare(rows[0].previewDetail, "Keystroke Settings › AI & Web Search › Preferred assistant › Claude")
        rows = search("settings", "ai cla")
        compare(rows[0].title, "Claude")
        compare(rows[0].subtitle, "AI & Web Search › Preferred assistant")          // breadcrumb below the current screen
        rows = search("settings/ai", "cla")
        compare(rows[0].subtitle, "Preferred assistant")
        rows = search("", "dens comf")
        compare(rows[0].title, "Comfortable")
        compare(rows[0].action.path, ["palette"])
        rows = search("", "enable emoji")
        compare(rows.length, 0)                                                       // no such provider in the model
        rows = search("", "enable clip")
        compare(rows[0].title, "Enabled")
        compare(rows[0].subtitle, "Keystroke Settings › Clipboard History")
        compare(rows[0].action.value, false)
        rows = search("", "hello")
        compare(rows[0].title, "Hello")
        compare(rows[0].badge, "plugin")
    }
    function test_listings_show_one_screen_and_value_screens_are_registered() {
        var t = SettingsTree.build(model())
        var root = SettingsTree.rows(t.nodes, "", "")
        compare(titles(root), ["Keystroke Settings"])
        compare(root[0].score, 20)
        compare(titles(SettingsTree.rows(t.nodes, "settings", "")), ["Appearance", "Open config file", "AI & Web Search", "Clipboard History", "Hello", "broken.plugin"])
        compare(titles(SettingsTree.rows(t.nodes, "settings/ai", "")), ["Enabled", "Preferred assistant", "Open conversations in", "Send immediately in the browser"])
        var hello = SettingsTree.rows(t.nodes, "settings/example.hello", "")
        compare(hello[1].title, "Provided by example.hello")
        verify(hello[1].disabled)
        compare(SettingsTree.rows(t.nodes, "settings/example.hello", "byex").length, 0)   // "Provided by example.hello" is list-only, never a search hit
        var options = SettingsTree.rows(t.nodes, "settings/ai/provider", "").map(function(r) { return r.title + " " + r.icon })
        compare(options, ["Chatgpt ✓", "Claude ○"])
        verify(t.screens["settings/clipboard/limit"] !== undefined)
        compare(t.screens["settings/clipboard/limit"].value, 100)
        compare(t.screens["settings/ai/provider"], undefined)
        var seen = ({})
        for (var i = 0; i < t.nodes.length; i++) { verify(!seen[t.nodes[i].id], "duplicate id " + t.nodes[i].id); seen[t.nodes[i].id] = true }
    }
    function voiceModel(detected, bindings) {
        var m = model()
        m.voice = { detected: detected, version: "1.0.1", daemonState: "idle", bindings: bindings, bindingsPath: "~/.config/hypr/bindings.lua",
                    schemas: [
                        { key: "enabled", type: "boolean", label: "Voxtype voice command integration", "default": true, description: "Hold the palette hotkey to dictate" },
                        { key: "secondTap", type: "enum", label: "Second tap of the hotkey", "default": "voice", options: ["voice", "close"] },
                        { key: "keys", type: "string", label: "Hotkeys to hold", "default": "SUPER + SPACE" }
                    ],
                    values: { enabled: true, secondTap: "voice", keys: "SUPER + SPACE" } }
        return m
    }
    function test_voice_screen_lists_its_settings_and_the_bindings_row() {
        var t = SettingsTree.build(voiceModel(true, "missing"))
        compare(titles(SettingsTree.rows(t.nodes, "settings", "")).slice(0, 3), ["Appearance", "Voice", "Open config file"])
        var screen = SettingsTree.rows(t.nodes, "settings/voice", "")
        compare(titles(screen), ["Voxtype voice command integration", "Second tap of the hotkey", "Hotkeys to hold", "Hold-to-talk bindings", "Voxtype 1.0.1"])
        compare(screen[0].accessory, "On")
        compare(screen[0].action.path, ["voice"])
        compare(screen[0].action.value, false)
        compare(screen[3].accessory, "Missing")
        compare(screen[3].verb, "Install")
        compare(screen[3].action.type, "voice-bindings")
        verify(screen[3].confirm.indexOf("Add the Keystroke voice block") === 0)
        verify(screen[4].disabled)
        verify(t.screens["settings/voice/keys"] !== undefined)
        var rows = Match.rank(SettingsTree.rows(t.nodes, "", "voice"), null)
        compare(rows[0].title, "Voice")
        rows = Match.rank(SettingsTree.rows(t.nodes, "", "voxtype"), null)
        verify(["Voice", "Voxtype voice command integration"].indexOf(rows[0].title) >= 0, rows[0].title)
        rows = Match.rank(SettingsTree.rows(t.nodes, "", "hold bind"), null)
        compare(rows[0].title, "Hold-to-talk bindings")
        compare(rows[0].subtitle, "Keystroke Settings › Voice")
        rows = Match.rank(SettingsTree.rows(t.nodes, "", "second tap clo"), null)
        compare(rows[0].title, "Close")
        compare(rows[0].action.path, ["voice"])
        compare(rows[0].action.value, "close")
        t = SettingsTree.build(voiceModel(true, "outdated"))
        var bindings = SettingsTree.rows(t.nodes, "settings/voice", "")[3]
        compare(bindings.accessory, "Outdated")
        compare(bindings.verb, "Update")
        verify(bindings.confirm.indexOf("Rewrite") === 0)
    }
    function test_voice_screen_without_voxtype_offers_the_installer() {
        var t = SettingsTree.build(voiceModel(false, "missing"))
        var entry = SettingsTree.rows(t.nodes, "settings", "")[1]
        compare(entry.title, "Voice")
        compare(entry.subtitle, "Voxtype is not installed")
        var screen = SettingsTree.rows(t.nodes, "settings/voice", "")
        compare(titles(screen), ["Voxtype is not installed", "Install dictation (voxtype)"])
        verify(screen[0].disabled)
        compare(screen[1].action.type, "shell")
        compare(SettingsTree.rows(t.nodes, "", "hold bind").length, 0)
        compare(t.screens["settings/voice/keys"], undefined)
        t = SettingsTree.build(model())                                              // no voice model at all: nothing changes
        compare(titles(SettingsTree.rows(t.nodes, "settings", "")).slice(0, 2), ["Appearance", "Open config file"])
    }
    function test_unrelated_queries_find_nothing() {
        compare(search("", "chrome").length, 0)
        compare(search("", "zzzz").length, 0)
        compare(search("settings/clipboard", "prefp").length, 0)                      // scoped search stays inside its subtree
    }
}
