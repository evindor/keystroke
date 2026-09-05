import QtQuick
import qs.Ui

// Adapted from Omarchy's menu bar widget. Toggling through `omarchy.menu`
// lets PluginRegistry route the call to whichever menu implementation is
// enabled, so this button keeps working if Keystroke is disabled.
BarWidget {
  id: root
  moduleName: "evindor.keystroke"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    fontFamily: "omarchy"
    horizontalMargin: 7.5
    onPressed: function(pressedButton) {
      if (!root.bar) return
      if (pressedButton === Qt.RightButton) root.bar.run("xdg-terminal-exec")
      else root.bar.run("omarchy-shell shell toggle omarchy.menu '{\"menu\":\"root\"}'")
    }
  }
}
