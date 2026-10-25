import QtQuick
import QtTest
import "../core/Locale.js" as Locale
import "../i18n/Legacy.js" as Legacy

TestCase {
    name: "Locale"
    function german(key) {
        return ({"Open":"Öffnen", "Settings":"Einstellungen", "Layout":"Darstellung", "Compact":"Kompakt", "On":"Ein"})[key] || key
    }
    function test_placeholders_are_literal_and_non_recursive() {
        compare(Locale.format("%2 / %1 / %1", ["<x> %2", "$()"]), "$() / <x> %2 / <x> %2")
        compare(Locale.format("%1 and %2", ["one"]), "one and %2")
        compare(Locale.text(null, "Save %1", ["Open"]), "Save Open")
    }
    function test_settings_preserve_values_actions_and_external_names() {
        var effect = {type:"setting", path:["palette"], key:"density", value:"compact"}
        var nodes = [
            {id:"palette/density", parts:["Settings","Layout"], path:"Settings › Layout", accessory:"compact", localizeAccessory:true, action:effect},
            {id:"files/prefix", parts:["Settings","Files","Prefix"], path:"Settings › Files › Prefix", accessory:"Open", localizeAccessory:false, action:effect},
            {id:"external", parts:["Settings","Open"], path:"Settings › Open", action:{type:"navigate",scope:"settings/external",title:"Open"}}
        ]
        var screens={value:{value:"Open"}}
        var result=Locale.settings({nodes:nodes,screens:screens,literalNames:{external:"Open"}},german)
        compare(result.nodes[0].title,"Darstellung")
        compare(result.nodes[0].accessory,"Kompakt")
        compare(result.nodes[0].action,effect)
        compare(result.nodes[0].keywords.indexOf("Settings › Layout") >= 0,true)
        compare(result.nodes[1].accessory,"Open")
        compare(result.nodes[2].title,"Open")
        compare(result.nodes[2].action.title,"Open")
        compare(result.screens,screens)
        compare(nodes[0].parts[0],"Settings")
        compare(nodes[0].accessory,"compact")
    }
    function test_system_locale_names_and_invalid_paths() {
        compare(Legacy.language("de_AT.UTF-8"), "de-AT")
        compare(Legacy.language("pt_BR.UTF-8"), "pt-BR")
        compare(Legacy.language("zh_TW"), "zh-TW")
        compare(Legacy.language("C.UTF-8"), "en")
        compare(Legacy.language("POSIX"), "en")
        compare(Legacy.language("../../secret"), "en")
        compare(Legacy.language(""), "en")
    }
}
