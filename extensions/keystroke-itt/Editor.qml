pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import Quickshell.Io
import qs.Commons
import qs.Ui as Ui

Item {
  id: root
  property var host: null
  required property var settings
  required property string omarchyPath
  property string result: ""
  property string status: ""
  property bool dismissed: false
  readonly property bool busy: selection.running || request.running
  readonly property bool grok: settings.provider === "grok"

  function focusInput() {
    source.forceActiveFocus()
  }

  function dismiss() {
    dismissed = true
    selection.running = false
    request.running = false
  }

  function improve() {
    if (dismissed || busy || !source.text.trim()) return
    result = ""
    status = "Improving text..."
    request.stdinEnabled = true
    request.running = true
  }

  function deliver(type) {
    if (result && host) host.perform({ type: type, text: result }, null)
  }

  Component.onCompleted: selection.running = true

  Process {
    id: selection
    command: ["timeout", "2", "wl-paste", "--primary", "--no-newline", "--type", "text"]
    stdout: StdioCollector {}
    stderr: StdioCollector {}
    onExited: function(code, exitStatus) {
      if (root.dismissed) return
      if (code === 0 && stdout.text.trim() && !source.text.length) {
        source.text = stdout.text
        Qt.callLater(root.improve)
      }
    }
  }

  Process {
    id: request
    command: ["timeout", "95", "python3",
      decodeURIComponent(String(Qt.resolvedUrl("bin/improve.py")).replace(/^file:\/\//, ""))]
    stdout: StdioCollector {}
    stderr: StdioCollector {}
    onStarted: {
      write(JSON.stringify({
        provider: root.settings.provider || "openai",
        omarchyPath: root.omarchyPath,
        model: root.grok ? root.settings.grokModel : root.settings.openaiModel,
        keyFile: root.grok ? root.settings.grokKeyFile : root.settings.openaiKeyFile,
        text: source.text
      }))
      stdinEnabled = false
    }
    onExited: function(code, exitStatus) {
      if (root.dismissed) return
      try {
        var reply = JSON.parse(stdout.text)
        root.result = reply.text || ""
        root.status = reply.error || ""
      } catch (error) {
        root.status = code === 124 ? "The request timed out. Try again." : "Could not run the request. Check that Python 3 is installed."
      }
    }
  }

  component EditorButton: Ui.Button {
    focusable: true
    foreground: root.host ? root.host.foreground : source.palette.text
    accent: root.host ? root.host.accent : source.palette.highlight
    fontFamily: root.host ? root.host.fontFamily : Style.font.menuFamily
    fontSize: root.host ? root.host.fontLabel : Style.font.bodySmall
  }

  Keys.onPressed: function(event) {
    if (event.key === Qt.Key_Escape && host) {
      event.accepted = true
      host.cancel()
    }
  }

  ColumnLayout {
    anchors.fill: parent
    anchors.margins: Style.space(18)
    spacing: Style.space(8)

    Text {
      text: "Improve This Text"
      color: root.host ? root.host.foreground : source.palette.text
      font.family: source.font.family
      font.pixelSize: root.host ? root.host.fontTitle : Style.font.title
    }

    Controls.ScrollView {
      Layout.fillWidth: true
      Layout.fillHeight: true
      Controls.TextArea {
        id: source
        placeholderText: "Paste or type the text to improve"
        readOnly: root.busy
        wrapMode: TextEdit.Wrap
        textFormat: TextEdit.PlainText
        color: root.host ? root.host.foreground : palette.text
        placeholderTextColor: root.host ? root.host.muted : palette.placeholderText
        font.family: root.host ? root.host.fontFamily : Style.font.menuFamily
        font.pixelSize: root.host ? root.host.fontBody : Style.font.body
        background: Rectangle {
          color: "transparent"
          border.color: root.host ? root.host.hairline : source.palette.mid
        }
        onTextChanged: {
          root.result = ""
          root.status = ""
        }
        Keys.onPressed: function(event) {
          if (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter) return
          if (event.modifiers & Qt.ShiftModifier) return
          event.accepted = true
          if (root.result) root.deliver(event.modifiers & Qt.ControlModifier ? "copy" : "paste")
          else root.improve()
        }
      }
    }

    Text {
      text: root.status
      visible: text.length > 0
      Layout.fillWidth: true
      wrapMode: Text.Wrap
      textFormat: Text.PlainText
      color: root.host ? root.host.muted : source.palette.text
      font.family: source.font.family
      font.pixelSize: root.host ? root.host.fontLabel : Style.font.bodySmall
    }

    Controls.ScrollView {
      visible: root.result.length > 0
      Layout.fillWidth: true
      Layout.fillHeight: true
      Controls.TextArea {
        text: root.result
        readOnly: true
        selectByMouse: true
        wrapMode: TextEdit.Wrap
        textFormat: TextEdit.PlainText
        color: source.color
        font: source.font
        background: Rectangle {
          color: "transparent"
          border.color: root.host ? root.host.hairline : source.palette.mid
        }
        Keys.onPressed: function(event) {
          if (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter) return
          event.accepted = true
          root.deliver(event.modifiers & Qt.ControlModifier ? "copy" : "paste")
        }
      }
    }

    RowLayout {
      Layout.fillWidth: true
      EditorButton {
        visible: !root.result
        text: "Improve text"
        enabled: !root.busy && !!source.text.trim()
        onClicked: root.improve()
      }
      EditorButton {
        visible: !!root.result
        text: "Paste text (Enter)"
        onClicked: root.deliver("paste")
      }
      EditorButton {
        visible: !!root.result
        text: "Send to clipboard (Ctrl+Enter)"
        onClicked: root.deliver("copy")
      }
    }
  }
}
