import QtQuick
import QtTest
import "../core/SettingsTree.js" as SettingsTree
import "../providers"

// A setting the user has to fetch from somewhere (an API key) and a setting
// that must not be read over a shoulder (the same one).
TestCase {
    name: "SettingsSecret"
    SettingsProvider { id: provider }

    property var keySchema: ({
        key: "apiKey", type: "string", label: "GIPHY API key", "default": "", secret: true,
        description: "A free key from the GIPHY developer dashboard",
        setup: { notice: "GIPHY API key is not set", detail: "GIF Search needs your own free key from GIPHY",
                 hint: "↵ opens developers.giphy.com", verb: "Get a key", icon: "󰌆",
                 url: "https://developers.giphy.com/dashboard/" }
    })

    function screen(value) { return { path: ["providers", "gif-search"], schema: keySchema, value: value } }

    function test_unset_key_is_notable_and_actionable() {
        var rows = provider.valueRows({ query: "" }, screen(""))
        compare(rows.length, 1)
        compare(rows[0].title, "GIPHY API key is not set")
        compare(rows[0].tier, "answer")          // the answer tier is the notable type size
        verify(!rows[0].disabled)
        compare(rows[0].verb, "Get a key")
        compare(rows[0].hint, "↵ opens developers.giphy.com")
        compare(rows[0].action.type, "url")
        compare(rows[0].action.url, "https://developers.giphy.com/dashboard/")
    }

    function test_typing_a_key_offers_to_save_it_masked() {
        var rows = provider.valueRows({ query: "abcdef0123456789" }, screen(""))
        compare(rows.length, 2)
        compare(rows[0].tier, "answer")                       // the notice stays while typing
        compare(rows[1].verb, "Save")
        verify(rows[1].title.indexOf("abcd••••••••") !== -1)  // never the whole key
        verify(rows[1].title.indexOf("abcdef0123456789") === -1)
        compare(rows[1].action.value, "abcdef0123456789")     // but the full key is what is saved
    }

    function test_a_set_key_is_never_shown_in_full() {
        var rows = provider.valueRows({ query: "" }, screen("abcdef0123456789"))
        compare(rows.length, 1)
        compare(rows[0].title, "abcd••••••••")
        verify(rows[0].disabled)
    }

    function test_a_plain_setting_is_unchanged() {
        var plain = { key: "prefix", type: "string", label: "Prefix", "default": "gif" }
        var rows = provider.valueRows({ query: "" }, { path: ["providers", "x"], schema: plain, value: "" })
        compare(rows[0].title, "Not set")
        verify(rows[0].disabled)
        compare(provider.valueRows({ query: "" }, { path: ["providers", "x"], schema: plain, value: "gg" })[0].title, "gg")
    }

    function test_the_settings_list_flags_it_rather_than_dashing_it() {
        var nodes = [], screens = ({})
        SettingsTree.schemaNodes(nodes, screens, ["providers", "gif-search"],
                                 [keySchema, { key: "prefix", type: "string", label: "Prefix" }],
                                 { apiKey: "", prefix: "" }, "settings/gif-search", ["GIF Search"], "gif")
        compare(nodes[0].accessory, "Not set")   // a key the user must fetch
        compare(nodes[1].accessory, "—")         // an ordinary empty value
        var set = [], setScreens = ({})
        SettingsTree.schemaNodes(set, setScreens, ["providers", "gif-search"], [keySchema],
                                 { apiKey: "abcdef0123456789" }, "settings/gif-search", ["GIF Search"], "gif")
        compare(set[0].accessory, "abcd••••••••")
    }
}
