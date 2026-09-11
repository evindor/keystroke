pragma ComponentBehavior: Bound
import QtQuick
import qs.Commons
import qs.Ui as Ui
import "core/Parser.js" as Parser

// The countdown while input is blocked. Keystroke loads this component
// over its results (`provider-view`), injects `host`, and calls
// focusInput(); colors and sizes come from the host so the view keeps the
// palette's theme and type scale. State comes from the service: how many
// devices went quiet, when they come back, or why nothing was blocked.
//
// While the block runs no key reaches us, so the keys below matter only
// once input is back:
//   Esc              close
//   ← or Backspace   back to the results
FocusScope {
  id: root
  property var host: null
  property var service: null

  readonly property color foreground: root.host ? root.host.foreground : "white"
  readonly property color muted: root.host ? root.host.muted : "#aaa"
  readonly property color accent: root.host ? root.host.accent : "#7aa2f7"
  readonly property color hairline: root.host ? root.host.hairline : "#333"
  readonly property string fontFamily: root.host && root.host.fontFamily ? root.host.fontFamily : Style.font.menuFamily
  readonly property int fontTitle: root.host && root.host.fontTitle ? root.host.fontTitle : Style.font.title
  readonly property int fontLabel: root.host && root.host.fontLabel ? root.host.fontLabel : Style.font.bodySmall
  readonly property int fontCaption: root.host && root.host.fontCaption ? root.host.fontCaption : Style.font.caption

  // A snapshot of the service, refreshed on its `changed` signal and every
  // quarter second: sub-properties of a `var` do not re-bind on their own.
  property bool active: false
  property int total: 0
  property int remaining: 0
  property int blocked: -1
  property string error: ""
  property string note: ""
  property real elapsedFraction: 0
  readonly property bool done: !root.active && !root.error && root.total > 0
  readonly property real progress: root.active ? root.elapsedFraction : (root.done ? 1 : 0)
  readonly property bool urgent: root.active && root.remaining > 0 && root.remaining <= 5
  property real pulse: 1

  function refresh() {
    if (!root.service) return
    root.active = root.service.active
    root.total = root.service.seconds
    root.blocked = root.service.blocked
    root.error = root.service.error
    root.note = root.service.label
    var left = Math.max(0, root.service.until - Date.now())
    root.remaining = Math.ceil(left / 1000)
    root.elapsedFraction = root.total > 0 ? Math.max(0, Math.min(1, 1 - left / (root.total * 1000))) : 0
  }
  function focusInput() { root.forceActiveFocus() }
  function dismiss() { }
  function headline() {
    var suffix = root.note ? " · " + root.note : ""
    if (root.error) return "Nothing was blocked"
    if (!root.active) return root.done ? "Input restored" + suffix : "Nothing running"
    if (root.blocked < 0) return "Switching input off…"
    return "Blocking " + root.blocked + (root.blocked === 1 ? " device" : " devices") + " · back in " + Parser.describeDuration(root.remaining) + suffix
  }
  function body() {
    if (root.error) return root.error
    if (root.done) return "Wipe finished. The keyboard and pointer are back."
    return "Wipe away. Nothing you press or move counts until the countdown ends."
  }

  Component.onCompleted: { refresh(); Qt.callLater(focusInput) }
  Connections {
    target: root.service
    ignoreUnknownSignals: true
    function onChanged() { root.refresh() }
  }
  Timer { interval: 250; repeat: true; running: true; onTriggered: root.refresh() }

  Keys.onPressed: function(event) {
    if (event.key === Qt.Key_Escape) { root.host.cancel(); event.accepted = true }
    else if (event.key === Qt.Key_Left || event.key === Qt.Key_Backspace) { root.host.goBack(); event.accepted = true }
  }

  SequentialAnimation on pulse {
    running: root.urgent
    loops: Animation.Infinite
    NumberAnimation { from: 1; to: 0.55; duration: 400; easing.type: Easing.InOutQuad }
    NumberAnimation { from: 0.55; to: 1; duration: 400; easing.type: Easing.InOutQuad }
  }

  // A current Keystroke paints the backdrop behind this view, inside the
  // card border; only an older host needs one from us.
  Rectangle {
    anchors.fill: parent
    visible: !(root.host && root.host.paintsViewBackdrop)
    color: root.host ? root.host.background : "#222"
  }

  component Cap: Rectangle {
    property string label: ""
    implicitWidth: capText.implicitWidth + Style.space(12)
    implicitHeight: Style.space(22)
    radius: Math.min(Style.cornerRadius, Style.space(5))
    color: Util.alpha(root.foreground, 0.07)
    border.width: 1
    border.color: Util.alpha(root.foreground, 0.14)
    Text { id: capText; anchors.centerIn: parent; text: parent.label; textFormat: Text.PlainText; color: Util.alpha(root.foreground, 0.6); font.family: root.fontFamily; font.pixelSize: root.fontCaption }
  }

  component ActionButton: Ui.Button {
    id: control
    property alias label: control.text
    signal triggered()
    focusable: true
    foreground: root.foreground
    accent: root.accent
    fontFamily: root.fontFamily
    fontSize: root.fontLabel
    width: implicitWidth; height: implicitHeight
    onClicked: triggered()
    Keys.onReturnPressed: event => { if (!event.isAutoRepeat) triggered(); event.accepted = true }
    Keys.onEnterPressed: event => { if (!event.isAutoRepeat) triggered(); event.accepted = true }
    Keys.onSpacePressed: event => { if (!event.isAutoRepeat) triggered(); event.accepted = true }
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: triggered()
  }

  // ---------------------------------------------------------------- header
  Item {
    id: top
    x: Style.space(22); y: Style.space(12); width: parent.width - x * 2; height: Style.space(74)
    ActionButton { id: back; label: "←"; tooltipText: "Back to results"; onTriggered: root.host.goBack() }
    Row {
      anchors.left: back.right; anchors.leftMargin: Style.space(10); y: Style.space(8); spacing: Style.space(10)
      Text { text: "OMARCHY"; color: root.accent; font.family: root.fontFamily; font.pixelSize: root.fontCaption; font.letterSpacing: 2; font.weight: Font.Bold }
      Text { text: "›"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
      Text { text: Parser.NAME; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
    }
    Cap { anchors.right: parent.right; y: Style.space(5); label: "esc" }
    Text {
      y: Style.space(43); width: parent.width; elide: Text.ElideRight
      text: root.headline()
      color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel
    }
  }
  Rectangle { y: top.y + top.height; width: parent.width; height: 1; color: root.hairline }

  // ---------------------------------------------------------------- countdown
  Item {
    anchors.top: parent.top
    anchors.topMargin: top.y + top.height + Style.space(14)
    anchors.bottom: bar.top
    anchors.left: parent.left; anchors.right: parent.right
    Column {
      anchors.centerIn: parent
      width: parent.width * 0.85
      spacing: Style.space(14)
      Text {
        opacity: root.urgent ? root.pulse : 1
        text: root.error ? "!" : root.done ? "✓" : Parser.shortDuration(root.remaining)
        color: root.done || root.urgent ? root.accent : root.foreground
        font.family: root.fontFamily
        font.pixelSize: root.fontTitle * 6
        font.weight: Font.DemiBold
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        Behavior on color { ColorAnimation { duration: 200 } }
      }
      Text {
        text: root.body()
        color: root.muted
        font.family: root.fontFamily
        font.pixelSize: root.fontLabel
        width: parent.width
        wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignHCenter
      }
    }
  }

  // ---------------------------------------------------------------- progress
  Item {
    id: bar
    x: Style.space(22)
    y: footer.y - Style.space(38)
    width: parent.width - x * 2
    height: Style.space(10)
    Rectangle { anchors.fill: parent; radius: height / 2; color: Util.alpha(root.foreground, 0.08) }
    Rectangle {
      anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
      width: parent.width * root.progress
      radius: height / 2
      color: root.error ? root.muted : root.accent
      opacity: root.urgent ? root.pulse : 1
      Behavior on width { NumberAnimation { duration: 250; easing.type: Easing.Linear } }
    }
  }

  // ---------------------------------------------------------------- footer
  Item {
    id: footer
    x: 0; y: parent.height - Style.space(44); width: parent.width; height: Style.space(44)
    Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: root.hairline }
    Row {
      anchors.centerIn: parent; spacing: Style.space(16)
      ActionButton { label: "←"; tooltipText: "Back to results"; onTriggered: root.host.goBack() }
      Text { anchors.verticalCenter: parent.verticalCenter; text: "Back to results"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
      Rectangle { width: 1; height: Style.space(18); color: root.hairline }
      ActionButton { label: "Close"; tooltipText: "Esc"; onTriggered: root.host.cancel() }
      Rectangle { width: 1; height: Style.space(18); color: root.hairline }
      Text { anchors.verticalCenter: parent.verticalCenter; text: "Total"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
      Cap { anchors.verticalCenter: parent.verticalCenter; label: Parser.shortDuration(root.total) }
    }
  }
}
