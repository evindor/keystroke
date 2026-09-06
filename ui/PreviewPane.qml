import QtQuick
import qs.Commons

// Right-hand detail for the selected row: label, swatch, text or image, hint.
Item {
  id: root
  property var row: ({})
  property bool compact: true
  property color accent: Color.accent
  property color foreground: Color.menu.text
  readonly property bool clipboard: (row.previewLabel || "") === "CLIPBOARD" || (row.previewLabel || "") === "DICTATION"
  readonly property bool emoji: row.emoji === true

  Text {
    id: label
    x: 0; y: Style.space(10)
    text: root.row.previewLabel || "PREVIEW"
    textFormat: Text.PlainText
    font.family: Style.font.menuFamily
    font.pixelSize: Style.font.caption
    font.letterSpacing: 2
    color: Util.alpha(root.foreground, 0.5)
  }
  Rectangle {
    id: swatch
    y: Style.space(44); width: parent.width; height: Style.space(96)
    radius: Style.cornerRadius
    visible: !!root.row.swatch
    color: root.row.swatch || "transparent"
    border.width: 1
    border.color: Util.alpha(root.foreground, 0.15)
  }
  Text {
    y: root.row.swatch ? swatch.y + swatch.height + Style.space(18) : Style.space(46)
    width: parent.width
    height: parent.height - y - Style.space(66)
    visible: !!root.row.preview
    text: root.row.preview || ""
    textFormat: Text.PlainText
    color: root.clipboard ? Util.alpha(root.foreground, 0.85) : root.accent
    font.family: root.emoji ? "Noto Color Emoji" : (root.clipboard ? Style.font.menuFamily : "monospace")
    font.pixelSize: root.emoji ? Style.space(72) : (root.clipboard ? Style.font.body : (root.compact ? Style.font.display : Style.font.displayLarge))
    wrapMode: Text.WrapAnywhere
    elide: Text.ElideRight
  }
  Image {
    anchors.fill: parent
    anchors.topMargin: Style.space(40)
    anchors.bottomMargin: Style.space(50)
    visible: !!root.row.previewImage
    source: root.row.previewImage ? Util.fileUrl(root.row.previewImage) : ""
    fillMode: Image.PreserveAspectFit
    sourceSize.width: width * Screen.devicePixelRatio
    sourceSize.height: height * Screen.devicePixelRatio
    asynchronous: true
  }
  Text {
    anchors.bottom: parent.bottom
    anchors.bottomMargin: Style.space(16)
    width: parent.width
    text: root.row.previewDetail || (root.row.verb ? "Press return to " + String(root.row.verb).toLowerCase() : "")
    textFormat: Text.PlainText
    color: Util.alpha(root.foreground, 0.55)
    font.family: Style.font.menuFamily
    font.pixelSize: Style.font.bodySmall
    wrapMode: Text.Wrap
    maximumLineCount: 3
    elide: Text.ElideRight
  }
}
