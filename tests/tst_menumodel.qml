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
    function test_multi_selection_values_and_order() {
        var options = ["x\tOne\tid1", "Two", "x\tOne\tid2"]
        compare(MenuModel.dmenuValue(options[0]), "One\tid1")
        compare(MenuModel.dmenuSelections(options, ["Two", "unknown", "One\tid1", "Two"]), ["One\tid1", "Two"])
        compare(MenuModel.dmenuSelections(options, ["Two", "One\tid1"], true), ["Two", "One\tid1"])
        compare(MenuModel.toggleDmenuSelection(["Two"], "Two"), [])
        compare(MenuModel.toggleDmenuSelection([], "Two"), ["Two"])
    }
    function test_translation_fallback_and_search_only_english() {
        var original = MenuModel.parseMenuJsonc(JSON.stringify({"setup.language": {label: "Language", description: "Choose language"}}))
        var translated = MenuModel.applyTranslations(original, {"setup.language": {label: "Sprache"}})
        compare(original[0].label, "Language")
        compare(translated[0].label, "Sprache")
        compare(translated[0].description, "Choose language")
        compare(translated[0].searchTerms, ["Language"])
        compare(translated[0].aliases, [])
        compare(MenuModel.applyTranslations(original, {})[0].label, "Language")
    }
}
