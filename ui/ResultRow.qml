import QtQuick
import Quickshell

Rectangle {
    id: root
    required property var entry
    property bool selected: false
    property color accent: "#ee987e"
    property bool compact: false
    signal activated()
    signal hovered(real x, real y)
    height: compact ? 46 : 56
    radius: 9
    color: selected ? "#333138" : "transparent"
    border.width: selected ? 1 : 0
    border.color: "#444149"
    Accessible.role: Accessible.ListItem
    Accessible.name: entry.title + ". " + entry.subtitle
    Accessible.onPressAction: activated()

    Rectangle {
        x: 12; anchors.verticalCenter: parent.verticalCenter
        width: root.compact ? 28 : 34; height: width; radius: root.compact ? 7 : 9
        color: root.entry.iconName ? "transparent" : "#16aaa0b5"
        Text {
            anchors.centerIn: parent
            visible: appIcon.status !== Image.Ready
            text: root.entry.icon
            textFormat: Text.PlainText
            color: root.entry.tint || "#aaa9b0"
            font.family: root.entry.emoji ? "Noto Color Emoji" : (root.entry.iconFont || "JetBrainsMono Nerd Font")
            font.pixelSize: root.compact ? 19 : 22
        }
        Image {
            id: appIcon
            anchors.fill: parent
            anchors.margins: 2
            source: root.entry.iconName ? (root.entry.iconName.startsWith("/") ? "file://" + root.entry.iconName : Quickshell.iconPath(root.entry.iconName, true)) : ""
            sourceSize: Qt.size(32, 32)
            asynchronous: true
        }
    }
    Column {
        x: root.compact ? 51 : 59
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - x - 16 - accessory.width
        spacing: root.compact ? 2 : 3
        Text {
            width: parent.width
            text: root.entry.title
            textFormat: Text.PlainText
            color: root.selected ? "#f6f3f2" : "#d8d5db"
            font.family: "Adwaita Sans"
            font.pixelSize: root.compact ? 13 : 14
            font.weight: root.selected ? Font.DemiBold : Font.Medium
            elide: Text.ElideRight
        }
        Text {
            visible: !!root.entry.subtitle
            width: parent.width
            text: root.entry.subtitle
            textFormat: Text.PlainText
            color: root.selected ? "#aaa4af" : "#86818e"
            font.family: "Adwaita Sans"
            font.pixelSize: 11
            elide: Text.ElideRight
        }
    }
    Text {
        id: accessory
        anchors.right: parent.right
        anchors.rightMargin: 15
        anchors.verticalCenter: parent.verticalCenter
        text: root.entry.accessory || (root.entry.disabled ? "" : root.selected ? "↵" : root.entry.verb === "Open" ? "›" : "")
        color: root.selected ? "#d5c9c6" : "#6c6873"
        font.pixelSize: root.entry.accessory ? 12 : 18
        font.family: "Adwaita Sans"
    }
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        // Selection changes only on real movement, not as new rows appear.
        onPositionChanged: function(mouse) {
            var point = root.mapToItem(null, mouse.x, mouse.y)
            root.hovered(point.x, point.y)
        }
        onClicked: root.activated()
    }
}
