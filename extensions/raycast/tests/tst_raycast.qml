import QtQuick
import QtTest
import "../core/Raycast.js" as Raycast

TestCase {
    name: "Raycast"

    function test_paths() {
        compare(Raycast.extensionsDir("/home/fredde", ""), "/home/fredde/.local/share/keystroke/raycast/extensions")
        compare(Raycast.dataDir("/home/fredde", "/tmp/data"), "/tmp/data/keystroke/raycast")
        compare(Raycast.safeName("dad-jokes"), "dad-jokes")
        compare(Raycast.safeName("../etc"), "")
        compare(Raycast.safeName("store.raycast.dad-jokes"), "store.raycast.dad-jokes")
    }

    function installed() {
        return [{
            id: "store.raycast.dad-jokes", name: "dad-jokes", title: "Dad Jokes", dir: "/ext/dad",
            commands: [{ name: "index", title: "Random Dad Joke", mode: "view", description: "A joke" }]
        }]
    }

    function test_root_lists_installed_commands_only_when_there_is_a_query() {
        var quiet = Raycast.rows({ ready: true, runtime: true, nodeOk: true, installed: installed(), query: "" })
        compare(quiet.length, 0)
        var rows = Raycast.rows({ ready: true, runtime: true, nodeOk: true, installed: installed(), query: "dad" })
        compare(rows.length, 1)
        compare(rows[0].title, "Random Dad Joke")
        compare(rows[0].action.type, "raycast-run")
        compare(rows[0].action.dir, "/ext/dad")
        compare(rows[0].score, undefined)
    }

    function test_store_install_asks_before_downloading() {
        var rows = Raycast.rows({
            ready: true, runtime: true, nodeOk: true, inCommand: true, commandRest: "dad",
            installed: [],
            store: [{ name: "dad-jokes", title: "Dad Jokes", description: "Jokes", handle: "someone", compat: "full" }]
        })
        var store = rows.filter(function(row) { return row.id === "store/dad-jokes" })[0]
        compare(store.action.type, "raycast-install")
        compare(store.action.handle, "someone")
        compare(store.confirmText, "Install")
        verify(store.confirm.indexOf("Dad Jokes") >= 0)
        compare(store.accessory, "Works")
    }

    function test_installed_store_row_opens_the_command_without_a_confirm() {
        var rows = Raycast.rows({
            ready: true, runtime: true, nodeOk: true, scope: "raycast", query: "",
            installed: installed(),
            store: [{ name: "dad-jokes", title: "Dad Jokes", description: "Jokes", handle: "someone", installed: true }]
        })
        var store = rows.filter(function(row) { return row.id === "store/dad-jokes" })[0]
        compare(store.action.type, "raycast-run")
        compare(store.confirm, undefined)
        var removal = rows.filter(function(row) { return row.id.indexOf("remove/") === 0 })[0]
        compare(removal.action.type, "raycast-remove")
        compare(removal.confirmText, "Uninstall")
    }

    function test_raycast_extension_is_the_store_list() {
        compare(Raycast.storeSearchText("extension"), "")
        compare(Raycast.storeSearchText("extensions"), "")
        compare(Raycast.storeSearchText("extension dad jokes"), "dad jokes")
        var rows = Raycast.rows({
            inCommand: true, commandRest: "extension", installed: installed(),
            store: [
                { name: "dad-jokes", title: "Dad Jokes", description: "Jokes", handle: "someone" },
                { name: "gif-search", title: "GIF Search", description: "GIFs", handle: "someone" }
            ]
        })
        compare(rows.length, 2)
        compare(rows[0].title, "Dad Jokes")
        compare(rows[0].section, "Raycast Extensions")
        compare(rows[1].title, "GIF Search")
    }

    function test_flatten_keeps_section_headers() {
        var flat = Raycast.flatten({
            kind: "list",
            sections: [{ title: "Top", items: [{ id: "a", title: "Alpha", accessories: ["1"] }] }]
        })
        compare(flat.length, 2)
        compare(flat[0].kind, "header")
        compare(flat[1].id, "a")
        compare(Raycast.iconText({ text: "🔥" }), "🔥")
        compare(Raycast.iconSource({ url: "http://evil.test/x" }), "")
        compare(Raycast.iconSource({ url: "https://example.com/a.png" }), "https://example.com/a.png")
    }
}
