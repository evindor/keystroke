import QtQuick
import Quickshell
import qs.Commons
import qs.Ui as Ui
import "core/Gifs.js" as Gifs

Item {
  id: root
  objectName: "gifSearchView"
  property var host: null
  property var service: null
  readonly property color foreground: host ? host.foreground : Color.menu.text
  readonly property color muted: host ? host.muted : Color.menu.text
  readonly property color accent: host ? host.accent : Color.menu.text
  readonly property color hairline: host ? host.hairline : Color.menu.text
  readonly property string family: host ? host.fontFamily : Style.font.menuFamily
  readonly property int labelSize: host ? host.fontLabel : Style.font.bodySmall
  function focusInput() { search.forceActiveFocus() }
  function dismiss() { service.dismiss() }
  function transcript(text, final) { search.text = text }
  readonly property bool linkDefault: service.settings.defaultAction === "link"
  function openSignup() { Quickshell.execDetached(["xdg-open", Gifs.SIGNUP_URL]) }
  function choose(alternate) {
    if (service.needsKey) { openSignup(); return }
    var link = alternate ? !linkDefault : linkDefault
    if (grid.currentIndex >= 0) service.copy(service.items[grid.currentIndex], link)
  }
  function move(delta) {
    grid.currentIndex = Math.max(0, Math.min(grid.count - 1, grid.currentIndex + delta))
    grid.positionViewAtIndex(grid.currentIndex, GridView.Contain)
  }
  Keys.onPressed: function(event) {
    if (event.key === Qt.Key_Escape) host.cancel()
    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) choose(!!(event.modifiers & Qt.ControlModifier))
    else if (event.key === Qt.Key_Down) move(3)
    else if (event.key === Qt.Key_Up) move(-3)
    else return
    event.accepted = true
  }
  Component.onCompleted: { search.text = service.term; Qt.callLater(focusInput) }
  Connections {
    target: root.service
    function onCopySucceeded() { if (root.service.settings.closeAfterCopy) root.host.cancel() }
  }

  Column {
    anchors.fill: parent
    anchors.margins: Style.space(20)
    spacing: Style.space(12)
    Row {
      width: parent.width
      spacing: Style.space(12)
      Text {
        text: "󰍉"
        height: search.height
        verticalAlignment: Text.AlignVCenter
        color: root.accent
        font.family: root.family
        font.pixelSize: root.host ? root.host.fontInput : Style.font.heading
      }
      TextInput {
        id: search
        objectName: "gifSearchInput"
        width: parent.width - x
        height: Math.max(implicitHeight, Style.space(32))
        verticalAlignment: TextInput.AlignVCenter
        color: root.foreground
        selectionColor: root.accent
        font.family: root.family
        font.pixelSize: root.host ? root.host.fontInput : Style.font.heading
        clip: true
        selectByMouse: true
        maximumLength: 300
        onTextChanged: root.service.search(text)
        Accessible.name: "Search GIFs"
        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Tab) { grid.forceActiveFocus(); event.accepted = true }
          else if (event.key === Qt.Key_Right && event.modifiers === Qt.NoModifier
                   && cursorPosition === text.length && selectionStart === selectionEnd && grid.count) {
            grid.forceActiveFocus()
            root.move(1)
            event.accepted = true
          }
          else if (event.key === Qt.Key_Backspace && !text) { root.host.goBack(); event.accepted = true }
        }
        Text {
          anchors.fill: parent
          verticalAlignment: Text.AlignVCenter
          visible: !search.text
          text: "Search GIFs..."
          color: root.muted
          font: search.font
        }
      }
    }
    Rectangle { width: parent.width; height: 1; color: root.hairline }
    Item {
      width: parent.width
      height: Math.max(120, root.height - y - footer.height - Style.space(20) * 2 - Style.space(12))
      GridView {
        id: grid
        objectName: "gifSearchGrid"
        anchors.fill: parent
        clip: true
        model: root.service.items
        cellWidth: width / 3
        cellHeight: cellWidth * 0.72
        keyNavigationEnabled: false
        onCountChanged: currentIndex = count ? 0 : -1
        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Left) root.move(-1)
          else if (event.key === Qt.Key_Right) root.move(1)
          else if (event.key === Qt.Key_Tab) root.focusInput()
          else return
          event.accepted = true
        }
        delegate: Item {
          id: tile
          required property var modelData
          required property int index
          width: grid.cellWidth
          height: grid.cellHeight
          Rectangle {
            anchors.fill: parent
            anchors.margins: Style.space(4)
            radius: Style.cornerRadius
            color: "transparent"
            border.width: grid.currentIndex === tile.index ? 2 : 1
            border.color: grid.currentIndex === tile.index ? root.accent : root.hairline
            AnimatedImage {
              id: preview
              objectName: "gifPreview"
              anchors { fill: parent; margins: Style.space(4); bottomMargin: title.height + Style.space(8) }
              source: tile.modelData.preview
              asynchronous: true
              // Leave cache alone. `cache: false` on a remote animation drops the
              // downloaded data after the first pass, so QMovie cannot rewind: it
              // halts on the last frame and clears `playing`. A local file re-reads
              // itself and loops either way, which is why only the real grid shows it.
              playing: visible && root.service.active
              fillMode: Image.PreserveAspectFit
            }
            Text {
              anchors.centerIn: preview
              visible: preview.status !== Image.Ready
              text: preview.status === Image.Error ? "Preview unavailable" : "Loading..."
              color: root.muted
              font.family: root.family
              font.pixelSize: root.labelSize
            }
            Text {
              id: title
              anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Style.space(8) }
              text: tile.modelData.title
              elide: Text.ElideRight
              color: root.foreground
              font.family: root.family
              font.pixelSize: root.labelSize
            }
            MouseArea {
              anchors.fill: parent
              onClicked: function(mouse) { grid.currentIndex = tile.index; grid.forceActiveFocus(); root.choose(!!(mouse.modifiers & Qt.ControlModifier)) }
            }
            Accessible.role: Accessible.Button
            Accessible.name: "Copy " + tile.modelData.title
            Accessible.onPressAction: { grid.currentIndex = tile.index; root.choose(false) }
          }
        }
      }
      Text {
        anchors.centerIn: parent
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        visible: !grid.count && !root.service.needsKey
        text: root.service.loading ? "Searching GIPHY..." : root.service.message
        color: root.muted
        font.family: root.family
        font.pixelSize: root.labelSize
      }
      // Without a key there is nothing to search, so the empty grid explains
      // itself and offers the one action that gets the user out of the state.
      Column {
        anchors.centerIn: parent
        width: Math.min(parent.width, Style.space(420))
        spacing: Style.space(10)
        visible: root.service.needsKey
        Text {
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          text: "GIPHY API key is not set"
          color: root.foreground
          font.family: root.family
          font.pixelSize: root.host ? root.host.fontInput : Style.font.heading
          font.weight: Font.DemiBold
        }
        Text {
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          wrapMode: Text.WordWrap
          text: "GIF Search needs your own free key from the GIPHY developer dashboard. Paste it into Settings → GIF Search → GIPHY API key."
          color: root.muted
          font.family: root.family
          font.pixelSize: root.labelSize
        }
        Item {
          width: parent.width
          height: signup.height
          Ui.Button {
            id: signup
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Get a free key"
            foreground: root.foreground; accent: root.accent
            fontFamily: root.family; fontSize: root.labelSize
            onClicked: root.openSignup()
          }
        }
        Text {
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          text: "↵ opens developers.giphy.com"
          color: root.muted
          font.family: root.family
          font.pixelSize: root.labelSize
        }
      }
    }
    Column {
      id: footer
      width: parent.width
      spacing: Style.space(8)
      Item {
        width: parent.width
        height: pagination.height
        Row {
          id: pagination
          spacing: Style.space(12)
          visible: !root.service.needsKey
          Ui.Button {
            text: "Previous"
            enabled: !root.service.loading && root.service.page > 0
            foreground: root.foreground; accent: root.accent
            fontFamily: root.family; fontSize: root.labelSize
            onClicked: root.service.turnPage(-1)
          }
          Ui.Button {
            text: "Next"
            enabled: !root.service.loading && root.service.more
            foreground: root.foreground; accent: root.accent
            fontFamily: root.family; fontSize: root.labelSize
            onClicked: root.service.turnPage(1)
          }
          Ui.Button {
            text: "Retry"
            visible: !root.service.loading && !grid.count
            foreground: root.foreground; accent: root.accent
            fontFamily: root.family; fontSize: root.labelSize
            onClicked: root.service.refresh()
          }
        }
        Text {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          text: "Powered by GIPHY"
          color: root.muted
          font.family: root.family
          font.pixelSize: root.labelSize
        }
      }
      Text {
        width: parent.width
        elide: Text.ElideRight
        text: root.service.needsKey
          ? "Settings → GIF Search → GIPHY API key"
          : root.service.message || (root.linkDefault
            ? "Enter copies link  ·  Ctrl+Enter copies GIF  ·  Tab switches to grid"
            : "Enter copies GIF  ·  Ctrl+Enter copies link  ·  Tab switches to grid")
        color: root.muted
        font.family: root.family
        font.pixelSize: root.labelSize
      }
    }
  }
}
