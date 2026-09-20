import QtQuick
import qs.Commons
import qs.Ui

// Keystroke's confirmation: a sheet that rises from the bottom of the card
// under an accent rule, dimming the results above it. The question, an
// optional note in the muted colour (turning an extension on says what was
// checked and that the code runs at the user's own risk), and the two keys
// that answer it, each named for what it does ("Turn on", "Keep off").
// ↵ confirms, Esc keeps things as they are. No link: opening anything from
// here would move focus away from the palette, and the palette cannot
// survive that.
Item {
  id: root

  property bool opened: false
  property string message: ""
  property string detail: ""
  property string cancelText: "Cancel"
  property string confirmText: "Confirm"
  property color background: Color.background
  property color foreground: Color.foreground
  property color muted: Util.alpha(Color.foreground, 0.6)
  property color scrim: Util.alpha(Color.background, 0.7)
  property color selectedText: Color.accent
  property string fontFamily: Style.font.family
  property int cornerRadius: Style.cornerRadius

  signal canceled()
  signal confirmed()

  function handleKey(event) {
    if (!root.opened) return false
    if (event.key === Qt.Key_Escape) { root.canceled(); return true }
    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { root.confirmed(); return true }
    return true // nothing else reaches the search field while the question is open
  }

  visible: opened

  Rectangle {
    anchors.fill: parent
    color: root.scrim
    MouseArea { anchors.fill: parent; onClicked: root.canceled() }
  }

  // Only the sheet's bottom corners follow the card: the rectangle runs
  // past the top of this clip so its upper corners never show.
  Item {
    id: sheet
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: Style.space(2) + column.implicitHeight + Style.space(24) + Style.space(26)
    clip: true

    Rectangle {
      x: 0; y: -root.cornerRadius
      width: parent.width; height: parent.height + root.cornerRadius
      radius: root.cornerRadius
      color: root.background
      Rectangle { anchors.fill: parent; radius: parent.radius; color: Util.alpha(root.foreground, 0.05) }
      MouseArea { anchors.fill: parent; onClicked: {} }
    }
    Rectangle { x: 0; y: 0; width: parent.width; height: Style.space(2); color: root.selectedText }

    Column {
      id: column
      x: Style.space(22)
      y: Style.space(2) + Style.space(24)
      width: parent.width - Style.space(44)
      spacing: Style.space(14)

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: root.message
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.title
        wrapMode: Text.WordWrap
      }
      Text {
        width: parent.width
        visible: root.detail.length > 0
        textFormat: Text.PlainText
        text: root.detail
        color: root.muted
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        lineHeight: 1.25
        wrapMode: Text.WordWrap
      }
      Item { width: 1; height: Style.space(6) }
      Row {
        spacing: Style.space(24)
        Item {
          width: confirmAction.width; height: confirmAction.height
          Row {
            id: confirmAction
            spacing: Style.space(10)
            Keycap { label: "↵"; bright: true; foreground: root.foreground; anchors.verticalCenter: parent.verticalCenter }
            Text {
              textFormat: Text.PlainText; text: root.confirmText; color: root.selectedText
              font.family: root.fontFamily; font.pixelSize: Style.font.body; anchors.verticalCenter: parent.verticalCenter
            }
          }
          MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.confirmed() }
        }
        Item {
          width: cancelAction.width; height: cancelAction.height
          Row {
            id: cancelAction
            spacing: Style.space(10)
            Keycap { label: "esc"; foreground: root.foreground; anchors.verticalCenter: parent.verticalCenter }
            Text {
              textFormat: Text.PlainText; text: root.cancelText; color: root.muted
              font.family: root.fontFamily; font.pixelSize: Style.font.body; anchors.verticalCenter: parent.verticalCenter
            }
          }
          MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.canceled() }
        }
      }
    }
  }
}
