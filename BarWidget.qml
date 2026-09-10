pragma ComponentBehavior: Bound
import QtQuick
import qs.Commons
import qs.Ui

// Adapted from Omarchy's menu bar widget. Toggling through `omarchy.menu`
// lets PluginRegistry route the call to whichever menu implementation is
// enabled, so this button keeps working if Keystroke is disabled.
//
// After the menu button come the palette's bar items: what a provider asked
// to show next to the menu (the Timer extension's countdown) through
// host.setBarItem. The running palette is found through the shell's panel
// loaders (Keystroke is keepLoaded, so the instance exists once the shell
// has loaded its plugins) and its barList is bound, so a change in the
// palette repaints the bar without any process or poll. Text items are
// hidden on a vertical bar, like Omarchy's own text widgets.
BarWidget {
  id: root
  moduleName: "evindor.keystroke"

  readonly property var keystroke: {
    var shell = root.bar ? root.bar.shell : null
    var loaders = shell && shell.panelLoaders ? shell.panelLoaders : null
    var loader = loaders ? loaders[root.moduleName] : null
    return loader && loader.item ? loader.item : null
  }
  readonly property var items: root.keystroke && root.keystroke.barList ? root.keystroke.barList : []

  implicitWidth: layout.implicitWidth
  implicitHeight: layout.implicitHeight

  function toggleMenu() {
    if (root.bar) root.bar.run("omarchy-shell shell toggle omarchy.menu '{\"menu\":\"root\"}'")
  }
  // An item's payload is what its provider wants the palette opened with
  // (a scope, a query); without one the click toggles the menu.
  function openItem(item) {
    if (!root.bar) return
    if (item && item.payload) root.bar.run("omarchy-shell shell summon omarchy.menu " + Util.shellQuote(JSON.stringify(item.payload)))
    else root.toggleMenu()
  }

  // The buttons size themselves from the bar (a WidgetButton's implicit
  // height is the bar's size); the Row adds them up and the widget takes the
  // Row's size. Nothing here reads the widget's own size back, which would
  // be a loop that collapses the widget to nothing.
  Row {
    id: layout

    WidgetButton {
      id: button
      bar: root.bar
      text: ""
      fontFamily: "omarchy"
      horizontalMargin: 7.5
      onPressed: function(pressedButton) {
        if (!root.bar) return
        if (pressedButton === Qt.RightButton) root.bar.run("xdg-terminal-exec")
        else root.toggleMenu()
      }
    }

    Repeater {
      model: root.items
      delegate: WidgetButton {
        required property var modelData
        bar: root.bar
        visible: !root.vertical && text !== ""
        text: String(modelData.text || "")
        tooltipText: String(modelData.tooltip || "")
        horizontalMargin: 5
        onPressed: function(pressedButton) { root.openItem(modelData) }
      }
    }
  }
}
