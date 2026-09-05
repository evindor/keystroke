import QtQuick
import qs.Commons
import qs.Ui

// One result. Fixed roles only; the host updates delegates in place while
// typing, so nothing here may depend on object identity.
BorderSurface {
  id: root
  property string title: ""
  property string subtitle: ""
  property string icon: ""
  property string iconFont: ""
  property string iconSource: ""
  property string tint: ""
  property string verb: ""
  property string accessory: ""
  property string badge: ""
  property string hint: ""
  property bool disabled: false
  property bool answer: false
  property bool selected: false
  property bool compact: true
  property color accent: Color.accent
  property color foreground: Color.menu.text
  property color selectedBackground: Color.menu.selectedBackground
  property color selectedText: Color.menu.selectedText
  property var selectedBorderSpec: Border.none()
  signal activated()
  signal hovered(var item, var mouse)

  readonly property color textColor: selected ? selectedText : foreground
  readonly property int chip: compact ? Style.space(28) : Style.space(34)

  height: compact ? Style.space(46) : Style.space(56)
  radius: Style.cornerRadius
  color: selected ? selectedBackground : "transparent"
  borderSpec: selected ? selectedBorderSpec : Border.none()
  opacity: disabled ? 0.62 : 1
  Accessible.role: Accessible.ListItem
  Accessible.name: title + ". " + subtitle
  Accessible.onPressAction: root.activated()

  Rectangle {
    id: iconChip
    x: Style.space(10)
    anchors.verticalCenter: parent.verticalCenter
    width: root.chip
    height: width
    radius: Math.min(Style.cornerRadius, Style.space(root.compact ? 7 : 9))
    color: root.iconSource ? "transparent" : (root.answer ? Util.alpha(root.accent, 0.16) : Util.alpha(root.foreground, 0.07))
    Text {
      anchors.centerIn: parent
      visible: !root.iconSource || appIcon.status !== Image.Ready
      text: root.icon
      textFormat: Text.PlainText
      color: root.tint ? root.tint : (root.answer ? root.accent : Util.alpha(root.foreground, 0.8))
      font.family: root.iconFont ? root.iconFont : Style.font.menuFamily
      font.pixelSize: root.compact ? Style.font.iconLarge : Style.font.iconLarge + 3
    }
    Image {
      id: appIcon
      anchors.fill: parent
      anchors.margins: Style.space(2)
      visible: !!root.iconSource
      source: root.iconSource
      fillMode: Image.PreserveAspectFit
      sourceSize.width: width * Screen.devicePixelRatio
      sourceSize.height: height * Screen.devicePixelRatio
      asynchronous: true
    }
  }

  Column {
    id: body
    anchors.left: iconChip.right
    anchors.leftMargin: Style.space(11)
    anchors.right: trail.left
    anchors.rightMargin: Style.space(8)
    anchors.verticalCenter: parent.verticalCenter
    spacing: Style.space(2)
    Row {
      width: parent.width
      spacing: Style.space(6)
      Text {
        id: titleText
        width: Math.min(implicitWidth, parent.width - (badgeText.visible ? badgeText.width + Style.space(6) : 0))
        text: root.title
        textFormat: Text.PlainText
        color: root.textColor
        font.family: root.answer ? Style.font.menuFamily : Style.font.menuFamily
        font.pixelSize: root.answer ? Style.font.heading : (root.compact ? Style.font.title : Style.font.title + 1)
        font.weight: root.selected || root.answer ? Font.DemiBold : Font.Medium
        elide: Text.ElideRight
      }
      Rectangle {
        id: badgeText
        visible: !!root.badge
        anchors.verticalCenter: parent.verticalCenter
        width: badgeLabel.implicitWidth + Style.space(8)
        height: badgeLabel.implicitHeight + Style.space(3)
        radius: height / 2
        color: Util.alpha(root.foreground, 0.08)
        border.width: 1
        border.color: Util.alpha(root.foreground, 0.14)
        Text { id: badgeLabel; anchors.centerIn: parent; text: root.badge; textFormat: Text.PlainText; color: Util.alpha(root.foreground, 0.7); font.family: Style.font.menuFamily; font.pixelSize: Style.font.caption - 1 }
      }
    }
    Text {
      visible: !!root.subtitle
      width: parent.width
      text: root.subtitle
      textFormat: Text.PlainText
      color: Util.alpha(root.textColor, root.selected ? 0.72 : 0.55)
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
    }
  }

  Row {
    id: trail
    anchors.right: parent.right
    anchors.rightMargin: Style.space(12)
    anchors.verticalCenter: parent.verticalCenter
    spacing: Style.space(8)
    Text {
      visible: root.selected && !!root.hint && !root.disabled
      anchors.verticalCenter: parent.verticalCenter
      text: root.hint
      textFormat: Text.PlainText
      color: Util.alpha(root.textColor, 0.55)
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.caption
    }
    Text {
      anchors.verticalCenter: parent.verticalCenter
      text: root.accessory ? root.accessory : (root.disabled ? "" : (root.selected ? "↵" : (root.verb === "Open" ? "›" : "")))
      textFormat: Text.PlainText
      color: root.accessory ? root.textColor : Util.alpha(root.textColor, root.selected ? 0.9 : 0.4)
      font.family: Style.font.menuFamily
      font.pixelSize: root.accessory ? Style.font.bodySmall : Style.font.heading
    }
  }

  MouseArea {
    id: mouseArea
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: root.disabled ? Qt.ArrowCursor : Qt.PointingHandCursor
    onPositionChanged: function(mouse) { root.hovered(root, mouse) }
    onClicked: root.activated()
  }
}
