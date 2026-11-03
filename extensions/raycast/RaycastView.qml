pragma ComponentBehavior: Bound
import QtQuick
import qs.Commons
import qs.Commons as Commons
import "core/Raycast.js" as Raycast

// The running Raycast command. The Node host speaks JSON lines; this draws
// the list, detail or form with the palette's own colours.
Item {
  id: root
  objectName: "raycastView"
  property var host: null
  property var service: null
  property var view: null
  property var entries: []
  property int current: 0
  property bool actionsOpen: false
  property int actionIndex: 0
  property string voicePrefix: ""

  readonly property color foreground: host ? host.foreground : Commons.Color.menu.text
  readonly property color muted: host ? host.muted : Commons.Color.menu.text
  readonly property color accent: host ? host.accent : Commons.Color.menu.text
  readonly property color hairline: host ? host.hairline : Commons.Color.menu.text
  readonly property string family: host && host.fontFamily ? host.fontFamily : Style.font.menuFamily
  readonly property int fontInput: host && host.fontInput ? host.fontInput : Style.font.heading
  readonly property int fontTitle: host && host.fontTitle ? host.fontTitle : Style.font.title
  readonly property int fontLabel: host && host.fontLabel ? host.fontLabel : Style.font.bodySmall
  readonly property int fontCaption: host && host.fontCaption ? host.fontCaption : Style.font.caption
  readonly property var actions: {
    if (!root.view) return []
    if (root.view.kind === "list" && root.entries.length) {
      var row = root.entries[root.current]
      if (row && row.kind === "item" && row.actions && row.actions.length) return row.actions
    }
    return root.view.actions || []
  }

  function focusInput() {
    if (root.view && root.view.kind === "list") search.forceActiveFocus()
    else root.forceActiveFocus()
  }
  function dismiss() { if (service) service.dismiss() }
  function beginVoice() { voicePrefix = search.text ? search.text.replace(/\s*$/, " ") : "" }
  function transcript(text, final) {
    if (!root.view || root.view.kind !== "list") return
    search.text = voicePrefix + text
  }

  function rebuild() {
    var next = service ? service.screen : null
    root.view = next
    root.entries = Raycast.flatten(next)
    if (!next || next.kind !== "list") { root.actionsOpen = false; return }
    var selected = next.selected
    var found = -1
    for (var i = 0; i < root.entries.length; i++) {
      if (root.entries[i].kind !== "item") continue
      if (found < 0) found = i
      if (root.entries[i].id === selected) { found = i; break }
    }
    root.current = found < 0 ? 0 : found
    Qt.callLater(root.reveal)
  }

  function reveal() {
    var item = rows.itemAt(root.current)
    if (!item || !scroller.height) return
    if (item.y < scroller.contentY) scroller.contentY = item.y
    else if (item.y + item.height > scroller.contentY + scroller.height)
      scroller.contentY = item.y + item.height - scroller.height
  }

  function move(delta) {
    var n = root.entries.length
    if (!n) return
    var next = root.current
    for (var step = 0; step < n; step++) {
      next = (next + delta + n) % n
      if (root.entries[next].kind === "item") break
    }
    root.current = next
    root.reveal()
    var row = root.entries[next]
    if (row && service) service.send({ type: "select", id: row.id })
  }

  function runCurrent(alternate) {
    var list = root.actions
    if (!list.length) return
    var action = alternate && list.length > 1 ? list[1] : list[0]
    if (service) service.send({ type: "action", id: action.id })
  }

  function runActionAt(index) {
    var list = root.actions
    if (!list.length) return
    var action = list[Math.max(0, Math.min(list.length - 1, index))]
    root.actionsOpen = false
    if (service) service.send({ type: "action", id: action.id })
  }

  function handleKey(event) {
    if (!service) return false
    if (service.confirmReq) {
      if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { service.decide(true); return true }
      if (event.key === Qt.Key_Escape) { service.decide(false); return true }
      return true
    }
    if (root.actionsOpen) {
      if (event.key === Qt.Key_Escape) { root.actionsOpen = false; return true }
      if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { root.runActionAt(root.actionIndex); return true }
      if (event.key === Qt.Key_Down) { root.actionIndex = Math.min(root.actions.length - 1, root.actionIndex + 1); return true }
      if (event.key === Qt.Key_Up) { root.actionIndex = Math.max(0, root.actionIndex - 1); return true }
      return true
    }
    if (event.key === Qt.Key_Escape) { service.send({ type: "pop" }); return true }
    if (event.key === Qt.Key_K && (event.modifiers & Qt.ControlModifier)) {
      root.actionsOpen = root.actions.length > 0
      root.actionIndex = 0
      return true
    }
    if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !(root.view && root.view.kind === "form" && !(event.modifiers & Qt.ControlModifier))) {
      root.runCurrent(!!(event.modifiers & Qt.ControlModifier))
      return true
    }
    if (root.view && root.view.kind === "form" && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
      root.runCurrent(false)
      return true
    }
    if (event.key === Qt.Key_Down && root.view && root.view.kind === "list") { root.move(1); return true }
    if (event.key === Qt.Key_Up && root.view && root.view.kind === "list") { root.move(-1); return true }
    if (event.key === Qt.Key_Backspace && root.view && root.view.kind === "list" && !search.text && event.modifiers === Qt.NoModifier) {
      if (root.host) root.host.goBack()
      return true
    }
    return false
  }

  function footerText() {
    if (service && service.banner) return service.banner
    if (root.view && root.view.loading) return "Loading…"
    var list = root.actions
    if (!list.length) return root.view && root.view.kind === "list" ? "Type to filter" : ""
    var line = "Enter  " + list[0].title
    if (list.length > 1) line += "    Ctrl+Enter  " + list[1].title
    if (list.length > 2) line += "    Ctrl+K  more"
    return line
  }

  Keys.onPressed: function(event) { if (root.handleKey(event)) event.accepted = true }
  Component.onCompleted: { if (service) service.start(); root.rebuild(); Qt.callLater(root.focusInput) }
  Connections {
    target: root.service
    function onScreenChanged() { root.rebuild(); Qt.callLater(root.focusInput) }
  }

  Column {
    anchors.fill: parent
    anchors.margins: Style.space(20)
    spacing: Style.space(12)
    Text {
      width: parent.width
      text: (root.view && root.view.title) || (root.service && root.service.launch && root.service.launch.title) || "Raycast"
      color: root.foreground
      font.family: root.family
      font.pixelSize: root.fontTitle
      elide: Text.ElideRight
    }
    TextInput {
      id: search
      objectName: "raycastSearch"
      visible: !root.view || root.view.kind === "list"
      width: parent.width
      height: visible ? Math.max(implicitHeight, Style.space(32)) : 0
      color: root.foreground
      selectionColor: root.accent
      font.family: root.family
      font.pixelSize: root.fontInput
      clip: true
      selectByMouse: true
      onTextChanged: if (service) service.send({ type: "search", text: text })
      Keys.onPressed: function(event) { if (root.handleKey(event)) event.accepted = true }
      Text {
        anchors.fill: parent
        verticalAlignment: Text.AlignVCenter
        visible: !search.text && search.visible
        text: (root.view && root.view.placeholder) || "Search"
        color: root.muted
        font: search.font
      }
    }
    Rectangle { width: parent.width; height: 1; color: root.hairline }
    Item {
      id: body
      width: parent.width
      height: Math.max(120, root.height - y - footer.height - Style.space(20) * 2 - Style.space(12))
      Flickable {
        id: scroller
        anchors.fill: parent
        visible: !root.view || root.view.kind === "list"
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
          id: column
          width: scroller.width
          spacing: Style.space(4)
          Repeater {
            id: rows
            model: root.entries
            delegate: Item {
              id: rowItem
              required property var modelData
              required property int index
              width: column.width
              height: modelData.kind === "header" ? Style.space(28) : Style.space(48)
              Rectangle {
                anchors.fill: parent
                radius: 6
                visible: modelData.kind === "item" && index === root.current
                color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.18)
              }
              Row {
                anchors.fill: parent
                anchors.leftMargin: Style.space(8)
                anchors.rightMargin: Style.space(8)
                spacing: Style.space(10)
                Text {
                  width: Style.space(24)
                  height: parent.height
                  verticalAlignment: Text.AlignVCenter
                  horizontalAlignment: Text.AlignHCenter
                  text: Raycast.iconText(modelData.icon)
                  color: root.foreground
                  font.pixelSize: root.fontTitle
                  visible: modelData.kind === "item" && !image.visible && text
                }
                Image {
                  id: image
                  width: Style.space(22)
                  height: Style.space(22)
                  anchors.verticalCenter: parent.verticalCenter
                  visible: modelData.kind === "item" && source !== ""
                  source: Raycast.iconSource(modelData.icon)
                  fillMode: Image.PreserveAspectFit
                  asynchronous: true
                }
                Column {
                  width: parent.width - x
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: 0
                  Text {
                    width: parent.width
                    text: modelData.title || ""
                    color: modelData.kind === "header" ? root.muted : root.foreground
                    font.family: root.family
                    font.pixelSize: modelData.kind === "header" ? root.fontCaption : root.fontTitle
                    font.capitalization: modelData.kind === "header" ? Font.AllUppercase : Font.MixedCase
                    elide: Text.ElideRight
                  }
                  Text {
                    width: parent.width
                    visible: modelData.kind === "item" && text
                    text: modelData.subtitle || ""
                    color: root.muted
                    font.family: root.family
                    font.pixelSize: root.fontLabel
                    elide: Text.ElideRight
                  }
                }
              }
              Text {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(8)
                anchors.verticalCenter: parent.verticalCenter
                visible: modelData.kind === "item" && text
                text: (modelData.accessories || []).join("  ")
                color: root.muted
                font.family: root.family
                font.pixelSize: root.fontCaption
              }
              MouseArea {
                anchors.fill: parent
                enabled: modelData.kind === "item"
                onClicked: { root.current = index; root.runCurrent(false) }
              }
            }
          }
        }
        Text {
          anchors.centerIn: parent
          visible: scroller.visible && !root.entries.length
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          wrapMode: Text.Wrap
          color: root.muted
          font.family: root.family
          font.pixelSize: root.fontLabel
          text: root.view && root.view.empty
                ? ((root.view.empty.title || "Nothing here") + (root.view.empty.description ? "\n" + root.view.empty.description : ""))
                : (root.view && root.view.loading ? "Loading…" : "No results")
        }
      }
      Flickable {
        anchors.fill: parent
        visible: root.view && root.view.kind === "detail"
        contentWidth: width
        contentHeight: detail.implicitHeight
        clip: true
        Text {
          id: detail
          width: parent.width
          wrapMode: Text.Wrap
          textFormat: Text.MarkdownText
          color: root.foreground
          font.family: root.family
          font.pixelSize: root.fontTitle
          text: root.view && root.view.markdown ? root.view.markdown : ""
          onLinkActivated: function(link) { if (service) service.openTarget(link) }
        }
      }
      Flickable {
        id: formScroll
        anchors.fill: parent
        visible: root.view && root.view.kind === "form"
        contentHeight: form.implicitHeight
        clip: true
        Column {
          id: form
          width: formScroll.width
          spacing: Style.space(10)
          Repeater {
            model: root.view && root.view.kind === "form" ? root.view.fields : []
            delegate: Column {
              required property var modelData
              width: form.width
              spacing: Style.space(4)
              visible: modelData.type !== "separator"
              Text {
                width: parent.width
                visible: modelData.type === "description" || modelData.type === "checkbox"
                wrapMode: Text.Wrap
                color: modelData.type === "checkbox" ? root.foreground : root.muted
                font.family: root.family
                font.pixelSize: root.fontLabel
                text: modelData.type === "checkbox"
                      ? ((modelData.value ? "☑  " : "☐  ") + (modelData.title || modelData.id))
                      : (modelData.title || modelData.value || "")
                MouseArea {
                  anchors.fill: parent
                  enabled: modelData.type === "checkbox"
                  onClicked: service.send({ type: "field", id: modelData.id, value: !modelData.value })
                }
              }
              Text {
                visible: modelData.type !== "description" && modelData.type !== "checkbox" && modelData.title
                text: modelData.title
                color: root.muted
                font.family: root.family
                font.pixelSize: root.fontCaption
              }
              TextInput {
                visible: modelData.type !== "description" && modelData.type !== "checkbox" && modelData.type !== "separator"
                width: parent.width
                color: root.foreground
                font.family: root.family
                font.pixelSize: root.fontInput
                echoMode: modelData.type === "password" ? TextInput.Password : TextInput.Normal
                clip: true
                selectByMouse: true
                Component.onCompleted: text = modelData.value == null ? "" : String(modelData.value)
                onTextEdited: service.send({ type: "field", id: modelData.id, value: text })
                Keys.onPressed: function(event) { if (root.handleKey(event)) event.accepted = true }
              }
            }
          }
        }
      }
    }
    Text {
      id: footer
      width: parent.width
      color: root.muted
      font.family: root.family
      font.pixelSize: root.fontLabel
      elide: Text.ElideRight
      text: root.footerText()
    }
  }

  Rectangle {
    anchors.fill: parent
    visible: root.actionsOpen
    color: Qt.rgba(root.host && root.host.background ? root.host.background.r : 0, root.host && root.host.background ? root.host.background.g : 0, root.host && root.host.background ? root.host.background.b : 0, 0.92)
    Column {
      anchors.fill: parent
      anchors.margins: Style.space(20)
      spacing: Style.space(6)
      Text {
        text: "Actions"
        color: root.foreground
        font.family: root.family
        font.pixelSize: root.fontTitle
      }
      Repeater {
        model: root.actions
        delegate: Text {
          required property var modelData
          required property int index
          width: parent.width
          text: modelData.title || "Action"
          color: index === root.actionIndex ? root.accent : root.foreground
          font.family: root.family
          font.pixelSize: root.fontTitle
          elide: Text.ElideRight
        }
      }
    }
  }

  Rectangle {
    anchors.fill: parent
    visible: !!(service && service.confirmReq)
    color: Qt.rgba(0, 0, 0, 0.55)
    Column {
      anchors.centerIn: parent
      width: Math.min(parent.width - Style.space(40), 420)
      spacing: Style.space(8)
      Text {
        width: parent.width
        wrapMode: Text.Wrap
        text: service && service.confirmReq ? service.confirmReq.title : ""
        color: "white"
        font.family: root.family
        font.pixelSize: root.fontTitle
      }
      Text {
        width: parent.width
        wrapMode: Text.Wrap
        text: service && service.confirmReq ? service.confirmReq.message : ""
        color: "#ddd"
        font.family: root.family
        font.pixelSize: root.fontLabel
      }
      Text {
        width: parent.width
        text: service && service.confirmReq ? ("Enter  " + service.confirmReq.ok + "    Esc  " + service.confirmReq.cancel) : ""
        color: root.accent
        font.family: root.family
        font.pixelSize: root.fontLabel
      }
    }
  }
}
