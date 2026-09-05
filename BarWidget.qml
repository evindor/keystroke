import QtQuick
import Quickshell
import qs.Ui as OmarchyUi

OmarchyUi.BarWidget {
    id: root
    moduleName: "community.flint"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    OmarchyUi.WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "\ue900"
        fontFamily: "omarchy"
        horizontalMargin: 7.5
        onPressed: function(buttonCode) {
            if (buttonCode === Qt.RightButton) Quickshell.execDetached(["xdg-terminal-exec"])
            else Quickshell.execDetached(["omarchy-shell", "shell", "toggle", "community.flint", "{}"])
        }
    }
}
