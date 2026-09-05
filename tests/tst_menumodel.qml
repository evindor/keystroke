import QtQuick
import QtTest
import "../omarchy/MenuModel.js" as MenuModel

TestCase {
    name: "MenuModel"
    function merged() {
        var def = MenuModel.parseMenuJsonc(JSON.stringify({
            "setup": {label: "Setup", when: "false"},
            "setup.child": {label: "Original", action: "true"},
            "shortcut": {label: "Link", target: "setup", aliases: ["s"]}}))
        var user = MenuModel.parseMenuJsonc('// comment\n{"setup.child": {"label": "Mine", "action": "echo literal",},}')
        return MenuModel.mergeMenuSources(def, user)
    }
    function test_override_alias_link_and_guard_script() {
        var m = merged()
        compare(m.items["setup.child"].label, "Mine")
        compare(m.items["setup.child"].action, "echo literal")
        compare(MenuModel.resolveRoute(m.items, m.itemOrder, "s"), "shortcut")
        compare(m.items["shortcut"].kind, "link")
        compare(m.items["setup.child"].kind, "action")
        compare(MenuModel.resolveRoute(m.items, m.itemOrder, "SETUP"), "setup")
        compare(MenuModel.resolveRoute(m.items, m.itemOrder, ""), "root")
        var script = MenuModel.guardScript(m.items)
        verify(script.indexOf("setup:w:") >= 0)
        verify(script.indexOf("omarchy-pkg-present()") >= 0)
        compare(MenuModel.pathFor(m.items, "setup.child"), "Setup › Mine")
    }
    function test_cycles_are_bounded() {
        var items = {a: {id: "a", parent: "b", kind: "menu", label: "a", aliases: []}, b: {id: "b", parent: "a", kind: "menu", label: "b", aliases: []}}
        verify(MenuModel.depthFor(items, "a") <= 32)
        verify(MenuModel.pathFor(items, "a").length > 0)
        verify(!MenuModel.isDescendantOf(items, "a", "zzz"))
    }
}
