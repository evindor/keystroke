import QtQuick

Rectangle {
    id: root
    property string label: ""
    property bool bright: false
    implicitWidth: key.implicitWidth + 12
    implicitHeight: 22
    radius: 5
    color: bright ? "#3d3b41" : "#29282e"
    border.color: bright ? "#5b565b" : "#37353c"
    Text {
        id: key
        anchors.centerIn: parent
        text: root.label
        textFormat: Text.PlainText
        color: root.bright ? "#eeedf0" : "#99969f"
        font.family: "Adwaita Sans"
        font.pixelSize: 11
    }
}
