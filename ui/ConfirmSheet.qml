import QtQuick
import qs.Commons
import qs.Ui

// Keystroke's confirmation: the shell's ConfirmDialog (same look, same keys)
// with two optional lines under the question, a note in the muted colour and
// a highlighted link the user can click or open with Ctrl+O. Turning an
// extension on uses both: the note says what was checked, the link opens the
// exact folder whose code is about to run.
Item {
  id: root

  property bool opened: false
  property string message: ""
  property string detail: ""
  property string linkLabel: ""
  property string linkUrl: ""
  property string cancelText: "Cancel"
  property string confirmText: "Confirm"
  property int selectedIndex: 1
  property color background: Color.background
  property color foreground: Color.foreground
  property color muted: Util.alpha(Color.foreground, 0.6)
  property color accent: Color.accent
  property color scrim: Util.alpha(Color.background, 0.7)
  property color selectedBackground: Util.alpha(Color.foreground, 0.08)
  property color selectedText: Color.accent
  property string fontFamily: Style.font.family
  property int cornerRadius: Style.cornerRadius

  signal canceled()
  signal confirmed()
  signal linkOpened(string url)

  readonly property bool hasLink: linkUrl.length > 0

  function handleKey(event) {
    if (!root.opened) return false
    if (event.key === Qt.Key_Escape) { root.canceled(); return true }
    if (event.key === Qt.Key_Left || event.key === Qt.Key_Right || event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
      root.selectedIndex = root.selectedIndex === 0 ? 1 : 0
      return true
    }
    if (event.key === Qt.Key_O && (event.modifiers & Qt.ControlModifier) && root.hasLink) { root.linkOpened(root.linkUrl); return true }
    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
      if (root.selectedIndex === 0) root.canceled()
      else root.confirmed()
      return true
    }
    return false
  }

  visible: opened

  Rectangle {
    anchors.fill: parent
    color: root.scrim

    MouseArea { anchors.fill: parent; onClicked: root.canceled() }

    BorderSurface {
      id: card
      width: Math.min(parent.width - Style.space(32), Style.space(400))
      height: card.contentTopInset + card.contentBottomInset + column.implicitHeight + Style.space(20) + Style.space(34)
      anchors.centerIn: parent
      color: root.background
      borderSpec: Border.flat(root.selectedText, Style.normalBorderWidth)
      padding: Style.space(18)
      radius: root.cornerRadius

      MouseArea { anchors.fill: parent; onClicked: {} }

      Item {
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset

        Column {
          id: column
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: parent.top
          spacing: Style.space(8)

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
            wrapMode: Text.WordWrap
          }
          // The link: accent-coloured, underlined, a hand cursor, and a keycap for the keyboard.
          Row {
            visible: root.hasLink
            width: parent.width
            spacing: Style.space(8)
            Text {
              id: linkText
              width: parent.width - hint.width - parent.spacing
              textFormat: Text.PlainText
              text: root.linkLabel || root.linkUrl
              color: linkArea.containsMouse ? root.foreground : root.accent
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.underline: true
              wrapMode: Text.WrapAnywhere
              MouseArea {
                id: linkArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.linkOpened(root.linkUrl)
              }
            }
            Row {
              id: hint
              spacing: Style.space(4)
              anchors.verticalCenter: parent.verticalCenter
              Keycap { label: "ctrl O"; foreground: root.foreground }
              Text { text: "open"; textFormat: Text.PlainText; color: root.muted; font.family: root.fontFamily; font.pixelSize: Style.font.caption; anchors.verticalCenter: parent.verticalCenter }
            }
          }
        }

        Row {
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          spacing: Style.space(10)

          Repeater {
            model: [root.cancelText, root.confirmText]

            BorderSurface {
              required property int index
              required property string modelData

              readonly property bool selected: root.selectedIndex === index
              readonly property bool destructive: index === 1

              width: Style.space(88)
              height: Style.space(34)
              color: selected
                ? (destructive ? Util.alpha(Color.urgent, 0.22) : root.selectedBackground)
                : "transparent"
              borderSpec: Border.flat(destructive
                ? (selected ? Color.urgent : Util.alpha(Color.urgent, 0.56))
                : (selected ? root.selectedText : Util.alpha(root.foreground, 0.38)), Style.normalBorderWidth)
              radius: 0

              Text {
                textFormat: Text.PlainText
                anchors.centerIn: parent
                text: modelData
                color: destructive ? (selected ? Color.urgent : root.foreground) : (selected ? root.selectedText : root.foreground)
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }

              MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onEntered: root.selectedIndex = index
                onClicked: {
                  if (index === 0) root.canceled()
                  else root.confirmed()
                }
              }
            }
          }
        }
      }
    }
  }
}
