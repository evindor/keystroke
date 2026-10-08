pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Quickshell
import qs.Commons
import qs.Ui as Ui
import "core/TOTP.js" as TOTPModel

Item {
  id: root
  property var host: null
  property var service: null

  readonly property color foreground: root.host ? root.host.foreground : "white"
  readonly property color muted: root.host ? root.host.muted : "#aaa"
  readonly property color accent: root.host ? root.host.accent : "#ea580c"
  readonly property color hairline: root.host ? root.host.hairline : "#333"
  readonly property string fontFamily: root.host && root.host.fontFamily ? root.host.fontFamily : Style.font.menuFamily
  readonly property int fontInput: root.host && root.host.fontInput ? root.host.fontInput : Style.font.heading
  readonly property int fontTitle: root.host && root.host.fontTitle ? root.host.fontTitle : Style.font.title
  readonly property int fontLabel: root.host && root.host.fontLabel ? root.host.fontLabel : Style.font.bodySmall
  readonly property int fontCaption: root.host && root.host.fontCaption ? root.host.fontCaption : Style.font.caption

  readonly property bool isEditing: !!(root.service && root.service.editingAccount)
  readonly property var editingAccount: root.service ? root.service.editingAccount : null

  property string algorithm: "SHA1"
  property int digits: 6
  property int period: 30

  property string validationError: ""
  property string previewCode: ""
  property int previewRemaining: 0
  property bool secretValid: false
  property string cleanSecret: ""
  property bool showSecret: false

  function focusInput() {
    nameField.forceActiveFocus()
  }

  function initForm() {
    if (root.isEditing && root.editingAccount) {
      nameField.text = root.editingAccount.name || ""
      issuerField.text = root.editingAccount.issuer || ""
      secretField.text = root.editingAccount.secret || ""
      root.algorithm = root.editingAccount.algorithm || "SHA1"
      root.digits = root.editingAccount.digits || 6
      root.period = root.editingAccount.period || 30
    } else {
      nameField.text = ""
      issuerField.text = ""
      secretField.text = ""
      root.algorithm = "SHA1"
      root.digits = 6
      root.period = 30
    }
    updateValidation()
    Qt.callLater(focusInput)
  }

  function updateValidation() {
    var raw = secretField.text.trim()
    if (!raw) {
      root.secretValid = false
      root.previewCode = ""
      root.cleanSecret = ""
      root.validationError = ""
      return
    }

    if (raw.toLowerCase().indexOf("otpauth:") === 0) {
      try {
        var parsed = TOTPModel.parseInput(raw)
        if (parsed.name && !nameField.text) nameField.text = parsed.name
        if (parsed.issuer && !issuerField.text) issuerField.text = parsed.issuer
        raw = parsed.secret
        secretField.text = raw
        root.algorithm = parsed.algorithm || "SHA1"
        root.digits = parsed.digits || 6
        root.period = parsed.period || 30
      } catch (_) {}
    }

    var norm = raw.toUpperCase().replace(/[\s-]/g, "")
    root.cleanSecret = norm

    try {
      TOTPModel.decodeBase32(norm)
      var code = TOTPModel.generateCode({
        secret: norm,
        algorithm: root.algorithm,
        digits: root.digits,
        period: root.period
      }, Date.now())
      root.previewCode = TOTPModel.formatCode(code.value)
      root.previewRemaining = code.remainingSeconds
      root.secretValid = true
      root.validationError = ""
    } catch (e) {
      root.secretValid = false
      root.previewCode = ""
      root.validationError = "Invalid Base32 secret (allowed: A-Z, 2-7)"
    }
  }

  function save() {
    var name = nameField.text.trim()
    if (!name) {
      root.validationError = "Please enter an account name or email."
      nameField.forceActiveFocus()
      return
    }
    updateValidation()
    if (!root.secretValid || !root.cleanSecret) {
      root.validationError = root.validationError || "Please enter a valid Base32 secret key."
      secretField.forceActiveFocus()
      return
    }

    var id = root.isEditing && root.editingAccount ? root.editingAccount.id : TOTPModel.generateId()
    var acc = {
      id: id,
      name: name,
      issuer: issuerField.text.trim(),
      secret: root.cleanSecret,
      algorithm: root.algorithm,
      digits: root.digits,
      period: root.period
    }

    if (root.service) {
      root.service.saveAccount(acc)
    }
  }

  Component.onCompleted: {
    initForm()
  }

  Timer {
    interval: 1000
    repeat: true
    running: root.secretValid
    onTriggered: root.updateValidation()
  }

  // Backdrop for older hosts
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

  component ChoicePill: Rectangle {
    id: pill
    property string label: ""
    property bool selected: false
    signal picked()
    implicitWidth: pillText.implicitWidth + Style.space(16)
    implicitHeight: Style.space(26)
    radius: Style.space(13)
    color: pill.selected ? Util.alpha(root.accent, 0.22) : Util.alpha(root.foreground, 0.06)
    border.width: 1
    border.color: pill.selected ? root.accent : Util.alpha(root.foreground, 0.15)

    Text {
      id: pillText
      anchors.centerIn: parent
      text: pill.label
      color: pill.selected ? root.accent : root.foreground
      font.family: root.fontFamily
      font.pixelSize: root.fontLabel
      font.weight: pill.selected ? Font.Bold : Font.Normal
    }

    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: pill.picked()
    }
  }

  // ---------------------------------------------------------------- Header
  Item {
    id: top
    x: Style.space(22); y: Style.space(12); width: parent.width - x * 2; height: Style.space(40)
    ActionButton {
      id: back
      label: "←"
      tooltipText: "Back to results"
      onTriggered: {
        if (root.host) root.host.goBack()
      }
    }
    Row {
      anchors.left: back.right; anchors.leftMargin: Style.space(10); anchors.verticalCenter: back.verticalCenter; spacing: Style.space(8)
      Text { text: "OMARCHY"; color: root.accent; font.family: root.fontFamily; font.pixelSize: root.fontCaption; font.letterSpacing: 2; font.weight: Font.Bold }
      Text { text: "›"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
      Text { text: "TOTP"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
      Text { text: "›"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
      Text { text: root.isEditing ? "Edit Account" : "Add New Account"; color: root.foreground; font.family: root.fontFamily; font.pixelSize: root.fontLabel; font.weight: Font.Bold }
    }
    Cap { anchors.right: parent.right; anchors.verticalCenter: back.verticalCenter; label: "esc" }
  }
  Rectangle { y: top.y + top.height + Style.space(6); width: parent.width; height: 1; color: root.hairline }

  // ---------------------------------------------------------------- Form Body
  Flickable {
    id: scroll
    x: Style.space(22); y: top.y + top.height + Style.space(14)
    width: parent.width - x * 2; height: Math.max(0, bottomSeparator.y - y - Style.space(10))
    clip: true
    contentWidth: width
    contentHeight: formColumn.height + Style.space(16)
    boundsBehavior: Flickable.StopAtBounds

    Column {
      id: formColumn
      width: scroll.width
      spacing: Style.space(12)

      // Account Name / Email
      Column {
        width: parent.width
        spacing: Style.space(4)
        Text { text: "Account Name / Email *"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
        Ui.TextField {
          id: nameField
          width: parent.width
          foreground: root.foreground
          accent: root.accent
          font.family: root.fontFamily
          font.pixelSize: root.fontTitle
          placeholderText: "e.g. alice@example.com"
          Keys.onReturnPressed: event => { issuerField.forceActiveFocus(); event.accepted = true }
          Keys.onPressed: event => {
            if (event.key === Qt.Key_Escape) { if (root.host) root.host.goBack(); event.accepted = true; return }
            if (event.modifiers & Qt.ControlModifier && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_S)) {
              root.save(); event.accepted = true
            }
          }
        }
      }

      // Issuer / Service
      Column {
        width: parent.width
        spacing: Style.space(4)
        Text { text: "Issuer / Service (optional)"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel }
        Ui.TextField {
          id: issuerField
          width: parent.width
          foreground: root.foreground
          accent: root.accent
          font.family: root.fontFamily
          font.pixelSize: root.fontTitle
          placeholderText: "e.g. Google, GitHub, AWS, GitLab"
          Keys.onReturnPressed: event => { secretField.forceActiveFocus(); event.accepted = true }
          Keys.onPressed: event => {
            if (event.key === Qt.Key_Escape) { if (root.host) root.host.goBack(); event.accepted = true; return }
            if (event.modifiers & Qt.ControlModifier && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_S)) {
              root.save(); event.accepted = true
            }
          }
        }
      }

      // Secret Key
      Column {
        width: parent.width
        spacing: Style.space(4)
        Item {
          width: parent.width
          height: labelText.height
          Text {
            id: labelText
            anchors.left: parent.left
            text: "Secret Key (Base32) *"
            color: root.muted
            font.family: root.fontFamily
            font.pixelSize: root.fontLabel
          }
          Text {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: root.showSecret ? "󰈈 Hide (Ctrl+H)" : "󰈉 Reveal (Ctrl+H)"
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: root.fontCaption
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.showSecret = !root.showSecret
            }
          }
        }
        Ui.TextField {
          id: secretField
          width: parent.width
          password: !root.showSecret
          foreground: root.foreground
          accent: root.accent
          font.family: root.fontFamily
          font.pixelSize: root.fontTitle
          placeholderText: "e.g. JBSWY3DPEHPK3PXP (or paste otpauth:// URI)"
          onTextEdited: root.updateValidation()
          Keys.onReturnPressed: event => { root.save(); event.accepted = true }
          Keys.onPressed: event => {
            if (event.modifiers & Qt.ControlModifier && event.key === Qt.Key_H) {
              root.showSecret = !root.showSecret
              event.accepted = true
              return
            }
            if (event.key === Qt.Key_Escape) { if (root.host) root.host.goBack(); event.accepted = true; return }
            if (event.modifiers & Qt.ControlModifier && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_S)) {
              root.save(); event.accepted = true
            }
          }
        }
      }

      // Live validation banner
      Rectangle {
        width: parent.width
        height: Style.space(34)
        radius: Style.space(6)
        visible: root.secretValid
        color: Util.alpha("#22c55e", 0.12)
        border.width: 1
        border.color: Util.alpha("#22c55e", 0.35)
        Row {
          anchors.centerIn: parent
          spacing: Style.space(8)
          Text { text: "󰄲"; color: "#22c55e"; font.family: root.fontFamily; font.pixelSize: root.fontTitle }
          Text {
            text: "Valid Secret · Live OTP: " + root.previewCode + " (" + root.previewRemaining + "s)"
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: root.fontLabel
            font.weight: Font.DemiBold
          }
        }
      }

      // Error banner
      Text {
        width: parent.width
        visible: !root.secretValid && !!root.validationError
        text: "󰅙 " + root.validationError
        color: "#ef4444"
        font.family: root.fontFamily
        font.pixelSize: root.fontLabel
        wrapMode: Text.Wrap
      }

      // Advanced Settings: Digits & Period & Algorithm
      Column {
        width: parent.width
        spacing: Style.space(8)

        Row {
          spacing: Style.space(12)
          Text { anchors.verticalCenter: parent.verticalCenter; text: "Digits:"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel; width: Style.space(70) }
          ChoicePill { label: "6 digits"; selected: root.digits === 6; onPicked: { root.digits = 6; root.updateValidation() } }
          ChoicePill { label: "8 digits"; selected: root.digits === 8; onPicked: { root.digits = 8; root.updateValidation() } }
        }

        Row {
          spacing: Style.space(12)
          Text { anchors.verticalCenter: parent.verticalCenter; text: "Period:"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel; width: Style.space(70) }
          ChoicePill { label: "30s"; selected: root.period === 30; onPicked: { root.period = 30; root.updateValidation() } }
          ChoicePill { label: "60s"; selected: root.period === 60; onPicked: { root.period = 60; root.updateValidation() } }
        }

        Row {
          spacing: Style.space(12)
          Text { anchors.verticalCenter: parent.verticalCenter; text: "Algorithm:"; color: root.muted; font.family: root.fontFamily; font.pixelSize: root.fontLabel; width: Style.space(70) }
          ChoicePill { label: "SHA-1"; selected: root.algorithm === "SHA1"; onPicked: { root.algorithm = "SHA1"; root.updateValidation() } }
          ChoicePill { label: "SHA-256"; selected: root.algorithm === "SHA256"; onPicked: { root.algorithm = "SHA256"; root.updateValidation() } }
          ChoicePill { label: "SHA-512"; selected: root.algorithm === "SHA512"; onPicked: { root.algorithm = "SHA512"; root.updateValidation() } }
        }
      }
    }
  }

  // ---------------------------------------------------------------- Footer
  Rectangle { id: bottomSeparator; y: bottomBar.y - Style.space(8); width: parent.width; height: 1; color: root.hairline }

  Row {
    id: bottomBar
    x: Style.space(22); y: parent.height - height - Style.space(12); spacing: Style.space(12); height: Style.space(32)
    ActionButton {
      label: root.isEditing ? "Save Changes" : "Save Account"
      accent: root.accent
      onTriggered: root.save()
    }
    Cap { anchors.verticalCenter: parent.verticalCenter; label: "↵"; bright: true }
    ActionButton {
      label: "Cancel"
      onTriggered: {
        if (root.host) root.host.goBack()
      }
    }
    Cap { anchors.verticalCenter: parent.verticalCenter; label: "esc" }
  }
}
