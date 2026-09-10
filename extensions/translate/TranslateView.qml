pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import qs.Commons
import qs.Ui as Ui
import "core/Translate.js" as Translate

// The editor: type or dictate on top, one block per target language below,
// then the reverse translation as a check. Keystroke loads this component
// over its results (`provider-view`), injects `host`, and calls focusInput(),
// dismiss(), beginVoice() and transcript() as documented in docs/providers.md.
// Colors and sizes come from the host so the view keeps the palette's theme
// and type scale.
//
//   ↵         copy the main translation and close (or paste, per the Default action setting)
//   ^↵        the other one
//   ⇧↵        new line
//   ^O        open in translate.google.com
//   ^S        speak the main translation (when playback is on and mpv is installed)
//   Esc       close; ← or Backspace on an empty editor goes back to the results
Item {
  id: root
  property var host: null
  property var service: null
  property string voicePrefix: ""
  property string status: ""
  property var result: null
  property var blocks: []
  readonly property color foreground: root.host ? root.host.foreground : "white"
  readonly property color muted: root.host ? root.host.muted : "#aaa"
  readonly property color accent: root.host ? root.host.accent : "#61afef"
  readonly property color hairline: root.host ? root.host.hairline : "#333"
  readonly property string fontFamily: root.host && root.host.fontFamily ? root.host.fontFamily : Style.font.menuFamily
  readonly property int fontInput: root.host && root.host.fontInput ? root.host.fontInput : Style.font.heading
  readonly property int fontTitle: root.host && root.host.fontTitle ? root.host.fontTitle : Style.font.title
  readonly property int fontLabel: root.host && root.host.fontLabel ? root.host.fontLabel : Style.font.bodySmall
  readonly property int fontCaption: root.host && root.host.fontCaption ? root.host.fontCaption : Style.font.caption
  readonly property bool pasteDefault: root.service && root.service.settings.defaultAction === "paste"
  readonly property string mainText: root.result && root.result.main ? root.result.main.text : ""
  readonly property bool canSpeak: !!(root.service && root.service.settings.speak && root.service.canSpeak)

  function focusInput() { editor.forceActiveFocus(); editor.cursorPosition = editor.text.length }
  function dismiss() { if (service) service.setSubject(null, false) }
  function beginVoice() { voicePrefix = editor.text ? editor.text.replace(/\s*$/, " ") : "" }
  function transcript(text, final) { editor.text = voicePrefix + text; editor.cursorPosition = editor.text.length }

  function refresh() {
    if (!service) return
    root.result = service.viewState()
    root.blocks = root.result ? Translate.viewBlocks(root.result) : []
  }
  function deliver(paste, close) {
    if (!root.mainText) { root.status = root.result ? "No translation yet" : "Type something to translate"; return }
    Quickshell.execDetached(paste ? Translate.pasteArgv(root.mainText) : ["wl-copy", "--", root.mainText])
    if (close && root.host) root.host.cancel()
    else root.status = (paste ? "Pasted " : "Copied ") + Translate.ellipsis(root.mainText, 60)
  }
  function openWeb() {
    if (!root.result) return
    Quickshell.execDetached(["xdg-open", Translate.webUrl(root.result.text, root.result.from, root.result.main.to)])
    if (root.host) root.host.cancel()
  }
  function speak() {
    if (!root.canSpeak || !root.mainText) return
    Quickshell.execDetached(Translate.speakArgv(root.mainText, root.result.main.to))
    root.status = "Playing the " + Translate.languageName(root.result.main.to) + " pronunciation"
  }
  function headline() {
    if (root.service && root.service.blockedUntil > Date.now()) return "Google is rate-limiting this address; paused for a minute"
    if (!root.result) return "Into " + root.service.targets.map(Translate.languageName).join(", ") + " · type or dictate, ⇧↵ for a new line"
    var from = root.result.detected ? Translate.languageName(root.result.detected) : (root.result.from === "auto" ? "Detecting…" : Translate.languageName(root.result.from))
    var shown = [root.result.main.to].concat(root.result.extras.map(function(x) { return x.to }))
    return from + " → " + shown.map(Translate.languageName).join(", ")
  }

  Component.onCompleted: { if (service) editor.text = service.draft; refresh(); Qt.callLater(focusInput) }
  Connections {
    target: root.service
    function onTranslated() { root.refresh() }
  }

  // A current Keystroke paints the backdrop behind this view, inside the card
  // border. Filling the card here would cover that border, so only do it for a
  // host that does not.
  Rectangle {
    anchors.fill: parent
    visible: !(root.host && root.host.paintsViewBackdrop)
    color: root.host ? root.host.background : "#222"
  }

  component ActionButton: Ui.Button {
    id: control
    property alias label: control.text
    property bool available: true
    signal triggered()
    focusable: true
    enabled: available
    opacity: enabled ? 1 : 0.4
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
    Accessible.onPressAction: if (enabled) triggered()
  }
  component Cap: Rectangle {
    property string label: ""
    property bool bright: false
    implicitWidth: capText.implicitWidth + Style.space(12)
    implicitHeight: Style.space(22)
    radius: Math.min(Style.cornerRadius, Style.space(5))
    color: Util.alpha(root.foreground, bright ? 0.14 : 0.07)
    border.width: 1
    border.color: Util.alpha(root.foreground, bright ? 0.28 : 0.14)
    Text { id: capText; anchors.centerIn: parent; text: parent.label; textFormat: Text.PlainText; color: Util.alpha(root.foreground, parent.bright ? 0.95 : 0.6); font.family: root.fontFamily; font.pixelSize: root.fontCaption }
  }
  component FooterHint: Row {
    property string label: ""
    property string cap: ""
    spacing: Style.space(8)
    Text { anchors.verticalCenter: parent.verticalCenter; text: parent.label; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
    Cap { anchors.verticalCenter: parent.verticalCenter; label: parent.cap }
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
      Image { source: root.service ? root.service.iconSource : ""; width: Style.space(14); height: width; anchors.verticalCenter: parent.verticalCenter; sourceSize.width: width * 2; sourceSize.height: height * 2; fillMode: Image.PreserveAspectFit; asynchronous: true }
      Text { text: Translate.NAME; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
    }
    Cap { anchors.right: parent.right; y: Style.space(5); label: "esc" }
    Text {
      y: Style.space(43); width: parent.width - external.width - Style.space(12); elide: Text.ElideRight
      text: root.headline()
      color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel
    }
    ActionButton { id: external; anchors.right: parent.right; y: Style.space(33); label: "Google Translate ↗"; tooltipText: "Ctrl+O"; available: !!root.result; onTriggered: root.openWeb() }
  }
  Rectangle { y: top.y + top.height; width: parent.width; height: 1; color: root.hairline }

  // ---------------------------------------------------------------- editor
  Flickable {
    id: scroll
    x: Style.space(22); y: top.y + top.height + Style.space(10)
    width: parent.width - x * 2; height: Math.max(0, statusLine.y - y - Style.space(10))
    clip: true; contentWidth: width; contentHeight: column.height + Style.space(8)
    boundsBehavior: Flickable.StopAtBounds
    function reveal(item) {
      var r = item.mapToItem(column, 0, 0)
      if (r.y < contentY) contentY = r.y
      else if (r.y + item.height > contentY + height) contentY = Math.max(0, r.y + item.height - height)
    }
    Column {
      id: column
      width: scroll.width
      spacing: Style.space(14)
      TextEdit {
        id: editor
        objectName: "editor"
        width: parent.width
        height: Math.max(Style.space(64), contentHeight)
        wrapMode: TextEdit.Wrap; selectByMouse: true; textFormat: TextEdit.PlainText
        color: root.foreground; selectionColor: Style.selectionFillFor(root.foreground, root.accent)
        font.family: root.fontFamily; font.pixelSize: root.fontInput
        onCursorRectangleChanged: { var r = cursorRectangle; if (r.y + r.height > scroll.contentY + scroll.height) scroll.contentY = r.y + r.height - scroll.height; else if (r.y < scroll.contentY) scroll.contentY = r.y }
        onTextChanged: { if (root.service) root.service.setDraft(text); root.refresh(); if (root.status.indexOf("Copied") === 0 || root.status.indexOf("Pasted") === 0 || root.status.indexOf("No ") === 0) root.status = "" }
        Keys.priority: Keys.BeforeItem
        Keys.onReleased: function(event) { if (root.host.voice.active && root.host.voiceTrigger === "hold" && root.host.isSuperKey(event.key)) { root.host.voiceStop(); event.accepted = true } }
        Keys.onPressed: function(event) {
          var enter = event.key === Qt.Key_Return || event.key === Qt.Key_Enter
          var ctrl = event.modifiers & Qt.ControlModifier, shift = event.modifiers & Qt.ShiftModifier
          if (event.key === Qt.Key_Escape) { root.host.cancel(); event.accepted = true; return }
          if (enter && event.isAutoRepeat) { event.accepted = true; return }
          if (root.host.voice.active) {
            if (enter) { root.host.voiceStop(); event.accepted = true; return }
            if (root.host.isModifierKey(event.key)) return
            root.host.voiceCancel()
          }
          if ((event.key === Qt.Key_Left || event.key === Qt.Key_Backspace) && !text && !preeditText && event.modifiers === Qt.NoModifier) { root.host.goBack(); event.accepted = true; return }
          if (enter && shift) { insert(cursorPosition, "\n"); event.accepted = true; return }
          if (enter && ctrl) { root.deliver(!root.pasteDefault, true); event.accepted = true; return }
          if (enter) { root.deliver(root.pasteDefault, true); event.accepted = true; return }
          if (ctrl && event.key === Qt.Key_O) { root.openWeb(); event.accepted = true; return }
          if (ctrl && event.key === Qt.Key_S) { root.speak(); event.accepted = true; return }
        }
        Text {
          anchors.fill: parent; visible: !editor.text
          text: "Type or dictate text to translate"
          color: Util.alpha(root.foreground, 0.3); font: editor.font
        }
      }
      Rectangle { width: parent.width; height: 1; color: root.hairline; visible: root.blocks.length > 0 }
      Repeater {
        model: root.blocks
        Column {
          id: block
          required property var modelData
          width: column.width
          spacing: Style.space(4)
          Row {
            spacing: Style.space(8)
            Text { text: block.modelData.label; color: root.accent; font.family: root.fontFamily; font.pixelSize: root.fontLabel; font.weight: Font.DemiBold }
            Text { visible: !!block.modelData.pronunciation; text: block.modelData.pronunciation; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel; elide: Text.ElideRight; width: Math.min(implicitWidth, column.width * 0.6) }
          }
          TextEdit {
            width: parent.width; height: contentHeight
            visible: !!block.modelData.text
            text: block.modelData.text; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText
            color: root.foreground; selectionColor: Style.selectionFillFor(root.foreground, root.accent)
            font.family: root.fontFamily; font.pixelSize: root.fontTitle
          }
          Text {
            visible: !block.modelData.text
            text: block.modelData.error || "Translating…"
            color: block.modelData.error ? Color.urgent : root.muted; font.family: root.fontFamily; font.pixelSize: root.fontTitle
          }
          Text {
            visible: !!block.modelData.detail; width: parent.width; wrapMode: Text.Wrap
            text: block.modelData.detail; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel
          }
        }
      }
      Text {
        visible: !!(root.result && root.result.correction)
        text: root.result && root.result.correction ? "Did you mean: " + root.result.correction.text : ""
        color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { editor.text = root.result.correction.text; editor.cursorPosition = editor.text.length } }
      }
    }
  }

  Text {
    id: statusLine
    x: Style.space(22); y: bottom.y - height - Style.space(12); width: parent.width - x * 2
    text: root.host && root.host.voice.active ? (root.host.voice.phase === "transcribing" ? "Finishing transcript…" : "Listening…") : root.status
    color: root.muted; elide: Text.ElideRight
    font.family: root.fontFamily; font.pixelSize: root.fontLabel
  }

  // ---------------------------------------------------------------- footer
  Rectangle { y: bottom.y - Style.space(10); width: parent.width; height: 1; color: root.hairline }
  Row {
    id: bottom
    x: Style.space(18); y: parent.height - height - Style.space(16); spacing: Style.space(14); height: Style.space(30)
    ActionButton { label: root.pasteDefault ? "Paste" : "Copy"; available: root.mainText.length > 0; onTriggered: root.deliver(root.pasteDefault, true) }
    Cap { anchors.verticalCenter: parent.verticalCenter; label: "↵"; bright: true }
    FooterHint { anchors.verticalCenter: parent.verticalCenter; label: root.pasteDefault ? "Copy" : "Paste"; cap: "ctrl ↵" }
    FooterHint { anchors.verticalCenter: parent.verticalCenter; label: "New line"; cap: "⇧ ↵" }
    FooterHint { anchors.verticalCenter: parent.verticalCenter; label: "Google Translate"; cap: "ctrl O" }
    FooterHint { anchors.verticalCenter: parent.verticalCenter; visible: root.canSpeak; label: "Speak"; cap: "ctrl S" }
  }
}
