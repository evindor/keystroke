import QtQuick
import Quickshell
import qs.Commons
import "../ui"
import "../voice"

Item {
  id: root
  property var host: null
  property var session: null
  property string voicePrefix: ""
  property string localStatus: ""
  property var answers: ({})
  readonly property color foreground: host ? host.foreground : "white"
  readonly property color muted: host ? host.muted : "#aaa"
  readonly property color accent: host ? host.accent : "#cba6f7"
  readonly property var approval: session && session.approvals.length ? session.approvals[0] : null
  function focusInput() { composer.forceActiveFocus(); composer.cursorPosition = composer.text.length }
  function beginVoice() { voicePrefix = session.draft ? session.draft.replace(/\s*$/, " ") : "" }
  function transcript(text, final) { session.draft = voicePrefix + text; composer.cursorPosition = composer.text.length }
  function dismiss() { session.dismiss() }
  function markdown(text) { return String(text).replace(/</g, "&lt;").replace(/!\[([^\]]*)\]\(([^)]*)\)/g, "[$1]($2)") }
  function syncMessages() {
    if (!session) return
    var rows = session.messages
    var follow = history.atYEnd || !history.count
    // Keep delegates stable while tokens stream, including selections and scroll.
    while (display.count > rows.length) display.remove(display.count - 1)
    for (var i = 0; i < rows.length; i++) {
      if (i >= display.count) display.append(rows[i])
      else if (display.get(i).id !== rows[i].id) display.set(i, rows[i])
      else if (display.get(i).text !== rows[i].text) display.setProperty(i, "text", rows[i].text)
    }
    if (follow) Qt.callLater(() => history.positionViewAtEnd())
  }
  onSessionChanged: syncMessages()
  Component.onCompleted: Qt.callLater(focusInput)
  Connections {
    target: root.session
    function onMessagesChanged() { root.syncMessages() }
    function onDraftChanged() { if (composer.text !== root.session.draft) composer.text = root.session.draft }
    function onApprovalsChanged() { root.answers = ({}); if (root.approval) decline.forceActiveFocus(); else root.focusInput() }
  }
  Keys.onPressed: function(event) {
    if (event.key === Qt.Key_Escape) { host.cancel(); event.accepted = true }
  }
  Rectangle { anchors.fill: parent; color: host ? host.background : "#222" }
  component ActionButton: Rectangle {
    property string label: ""
    property bool available: true
    signal triggered()
    implicitWidth: caption.implicitWidth + Style.space(20)
    implicitHeight: Style.space(30)
    width: implicitWidth; height: implicitHeight
    activeFocusOnTab: true
    enabled: available
    Keys.onPressed: function(event) {
      if (available && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space)) {
        if (!event.isAutoRepeat) triggered()
        event.accepted = true
      }
    }
    border.width: activeFocus ? 1 : 0
    border.color: root.accent
    radius: Style.space(6)
    color: mouse.containsMouse && available ? Util.alpha(root.accent, 0.18) : Util.alpha(root.foreground, 0.06)
    opacity: available ? 1 : 0.4
    Text { id: caption; anchors.centerIn: parent; text: parent.label; color: root.foreground; font.family: Style.font.menuFamily; font.pixelSize: Style.font.bodySmall }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; enabled: parent.available; onClicked: parent.triggered() }
    Accessible.role: Accessible.Button
    Accessible.name: label
  }
  Item {
    id: top
    enabled: !root.approval
    x: Style.space(20); y: Style.space(16); width: parent.width - x * 2; height: Style.space(52)
    Text { text: "✳  Codex · " + (session.mode === "agent" ? "Task" : "Quick question"); color: root.foreground; font.family: Style.font.menuFamily; font.pixelSize: Style.font.title }
    Text { y: Style.space(27); width: parent.width - external.width - Style.space(15); elide: Text.ElideMiddle; text: session.mode === "agent" ? session.cwd : (session.settings.model || "gpt-5.6-luna") + (session.settings.fast === false ? " · Standard" : " · Fast"); color: root.muted; font.family: Style.font.menuFamily; font.pixelSize: Style.font.bodySmall }
    ActionButton { id: external; anchors.right: parent.right; label: session.busy ? "Stop & continue ↗" : "Continue in Codex ↗"; available: !!session.threadId; onTriggered: session.requestHandoff() }
  }
  ListModel { id: display }
  ListView {
    id: history
    enabled: !root.approval
    x: Style.space(22); y: top.y + top.height + Style.space(8)
    width: parent.width - x * 2; height: Math.max(0, status.y - y - Style.space(12))
    clip: true; spacing: Style.space(16); model: display
    boundsBehavior: Flickable.StopAtBounds
    delegate: Item {
      required property string id
      required property string role
      required property string text
      width: history.width; height: label.height + body.height + Style.space(6)
      Text { id: label; text: parent.role === "user" ? "You" : parent.role === "activity" ? "Activity" : "Codex"; color: parent.role === "user" ? root.muted : root.accent; font.family: Style.font.menuFamily; font.pixelSize: Style.font.bodySmall }
      TextEdit {
        id: body; y: label.height + Style.space(6); width: parent.width; height: contentHeight
        text: root.markdown(parent.text); textFormat: TextEdit.MarkdownText; wrapMode: TextEdit.Wrap
        readOnly: true; selectByMouse: true; color: root.foreground
        selectionColor: Util.alpha(root.accent, 0.4)
        font.family: Style.font.menuFamily; font.pixelSize: parent.role === "activity" ? Style.font.bodySmall : Style.font.body
        onLinkActivated: function(link) { if (/^https?:\/\//.test(link)) Qt.openUrlExternally(link) }
      }
    }
    Text { visible: !history.count; anchors.centerIn: parent; width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; text: session.busy ? "Connecting to Codex…" : "Ask a question. Keep the conversation here.\nType or use your voice hotkey."; color: root.muted; font.family: Style.font.menuFamily; font.pixelSize: Style.font.body }
  }
  Text {
    id: status
    x: Style.space(22); y: inputBox.y - height - Style.space(10); width: parent.width - x * 2
    text: host && host.voice.active ? (host.voice.phase === "transcribing" ? "Finishing transcript…" : "Listening…") : session.error || root.localStatus || session.activity
    color: session.error ? Color.urgent : root.muted; elide: Text.ElideRight
    font.family: Style.font.menuFamily; font.pixelSize: Style.font.bodySmall
  }
  Rectangle {
    id: inputBox
    enabled: !root.approval
    x: Style.space(18); width: parent.width - x * 2
    height: Math.min(Style.space(115), Math.max(Style.space(50), composer.contentHeight + Style.space(24)))
    y: bottom.y - height - Style.space(12)
    radius: Style.space(8); color: Util.alpha(root.foreground, 0.05); border.color: Util.alpha(root.foreground, 0.15)
    Flickable {
      id: editorScroll
      x: Style.space(12); y: Style.space(12); width: parent.width - Style.space(80); height: parent.height - y * 2
      clip: true; contentWidth: width; contentHeight: Math.max(height, composer.contentHeight)
      boundsBehavior: Flickable.StopAtBounds
      function revealCursor() {
        var y = composer.cursorRectangle.y, h = composer.cursorRectangle.height
        if (y < contentY) contentY = y
        else if (y + h > contentY + height) contentY = y + h - height
      }
    TextEdit {
      id: composer
      objectName: "composer"
      width: editorScroll.width; height: Math.max(editorScroll.height, contentHeight)
      text: session.draft; wrapMode: TextEdit.Wrap; clip: true; selectByMouse: true
      onCursorRectangleChanged: editorScroll.revealCursor()
      color: root.foreground; selectionColor: Util.alpha(root.accent, 0.4)
      font.family: Style.font.menuFamily; font.pixelSize: Style.font.body
      onTextChanged: if (activeFocus && text !== session.draft) session.draft = text
      Keys.priority: Keys.BeforeItem
      Keys.onReleased: function(event) { if (host.voice.active && host.voiceTrigger === "hold" && host.isSuperKey(event.key)) { host.voiceStop(); event.accepted = true } }
      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) { host.cancel(); event.accepted = true; return }
        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && event.isAutoRepeat) { event.accepted = true; return }
        if (host.voice.active) {
          if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { host.voiceStop(); event.accepted = true; return }
          if (host.isModifierKey(event.key)) return
          host.voiceCancel()
        }
        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !(event.modifiers & Qt.ShiftModifier)) {
          if (event.modifiers & Qt.ControlModifier) session.requestHandoff(); else session.submit()
          event.accepted = true
        }
      }
      Text { anchors.fill: parent; visible: !composer.text; text: session.messages.length ? "Follow up…" : "Ask anything…"; color: root.muted; font: composer.font }
    }
    }
    VoiceWave { anchors.right: parent.right; anchors.rightMargin: Style.space(12); anchors.verticalCenter: parent.verticalCenter; width: Style.space(48); height: Style.space(32); visible: host && host.voice.active; mode: host ? host.voice.phase : "idle"; level: host ? host.voice.level : 0; history: host ? host.voice.history : []; accent: root.accent; foreground: root.foreground }
    ActionButton { anchors.right: parent.right; anchors.rightMargin: Style.space(9); anchors.verticalCenter: parent.verticalCenter; visible: host && !host.voice.active; label: "Mic"; onTriggered: { root.focusInput(); host.voiceBegin("tap") } }
  }
  Row {
    id: bottom
    enabled: !root.approval
    x: Style.space(18); y: parent.height - height - Style.space(16); spacing: Style.space(8); height: Style.space(30)
    ActionButton { label: session.busy ? "Update request ↵" : "Send ↵"; available: session.draft.trim().length > 0 && (!session.busy || session.phase === "running") && !root.approval; onTriggered: session.submit() }
    ActionButton { label: "Stop"; available: session.busy; onTriggered: session.stop() }
    ActionButton { label: "Copy answer"; available: session.answer().length > 0; onTriggered: answerCopy.submit(session.answer(), false) }
    ActionButton { label: "New question"; available: !session.busy; onTriggered: { session.newQuestion(""); root.focusInput() } }
    ActionButton { label: "Esc Close"; onTriggered: host.cancel() }
  }
  ClipboardTransfer { id: answerCopy; onCopied: root.localStatus = "Answer copied"; onFailed: message => root.localStatus = message }
  Rectangle {
    anchors.fill: parent; visible: !!root.approval; color: host ? host.background : "#222"; z: 10
    MouseArea { anchors.fill: parent }
    Flickable {
      anchors.fill: parent; anchors.margins: Style.space(22); clip: true
      contentHeight: approvalContent.height
    Column {
      id: approvalContent
      width: parent.width; spacing: Style.space(16)
      Text { text: "Codex needs your input"; color: root.foreground; font.family: Style.font.menuFamily; font.pixelSize: Style.font.title }
      TextEdit { width: parent.width; height: contentHeight; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; color: root.foreground; font.family: Style.font.menuFamily; font.pixelSize: Style.font.body;
        text: session.approvalDetail(root.approval) }

      Repeater {
        model: root.approval ? root.approval.params.questions || [] : []
        Column {
          required property var modelData
          width: parent.width; spacing: Style.space(8)
          Text { width: parent.width; wrapMode: Text.Wrap; text: modelData.question + ((modelData.options || []).length ? "\n" + modelData.options.map(x => x.label).join(" · ") : ""); color: root.foreground; font.family: Style.font.menuFamily; font.pixelSize: Style.font.body }
          Rectangle { width: parent.width; height: Style.space(38); color: Util.alpha(root.foreground, 0.1); radius: Style.space(6)
            TextInput { anchors.fill: parent; anchors.margins: Style.space(8); color: root.foreground; font.family: Style.font.menuFamily; font.pixelSize: Style.font.body; onTextEdited: { var a = Object.assign({}, root.answers); a[modelData.id] = text; root.answers = a } }
          }
        }
      }
      Row { spacing: Style.space(10)
        ActionButton { label: root.approval && root.approval.params.questions ? "Answer" : "Allow once"; onTriggered: session.decide(true, root.answers) }
        ActionButton { id: decline; label: "Decline"; onTriggered: session.decide(false) }
        ActionButton { label: "Stop & continue in Codex"; onTriggered: session.requestHandoff() }
      }
    }
    }
  }
}
