pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "ui"

Item {
    id: root
    property var shell: null
    property var manifest: null
    property bool opened: false
    property bool ready: false
    property bool busy: false
    property string scope: ""
    property string scopeTitle: ""
    property var history: []
    property var rows: []
    property int selected: 0
    property bool selectionTouched: false
    property int querySerial: 0
    property int displaySerial: -1
    property bool activateWhenReady: false
    property bool showLoading: false
    property bool pointerArmed: false
    property int rowCreationCount: 0
    property real pointerX: 0
    property real pointerY: 0
    property string errorMessage: ""
    property string statusMessage: ""
    property var confirmation: null
    property var dmenu: null
    property var appearance: ({})
    property var pendingLaunches: []
    readonly property string projectPath: decodeURIComponent(Qt.resolvedUrl(".").toString().replace(/^file:\/\//, ""))
    readonly property var current: rows.length && selected >= 0 && selected < rows.length ? rows[selected] : ({})
    readonly property color accent: appearance.accent === "violet" ? "#b5a0ef" : appearance.accent === "mint" ? "#8bceb4" : "#ee987e"
    readonly property bool previewVisible: appearance.showPreview !== false && !!(current.preview || current.previewImage || current.swatch)
    readonly property bool compact: appearance.density !== "comfortable"
    readonly property int headerHeight: compact ? 70 : 82
    readonly property int contentTop: compact ? 116 : 132
    onBusyChanged: {
        if (busy) loadingDelay.restart()
        else { loadingDelay.stop(); showLoading = false }
    }

    function rowKey(entry) { return (entry.extensionId || "picker") + "/" + entry.id }
    function applyRows(nextRows) {
        var keys = ({})
        for (var i = 0; i < nextRows.length; i++) keys[rowKey(nextRows[i])] = true
        for (var j = resultModel.count - 1; j >= 0; j--) {
            if (!keys[resultModel.get(j).uid]) resultModel.remove(j)
        }
        for (var n = 0; n < nextRows.length; n++) {
            var uid = rowKey(nextRows[n])
            var at = -1
            for (var k = n; k < resultModel.count; k++) {
                if (resultModel.get(k).uid === uid) { at = k; break }
            }
            if (at < 0) resultModel.insert(n, {uid: uid, entry: nextRows[n]})
            else {
                if (at !== n) resultModel.move(at, n, 1)
                resultModel.setProperty(n, "entry", nextRows[n])
            }
        }
        rows = nextRows
    }
    function edited() {
        confirmation = null
        querySerial++ // Immediately reject replies to the previous input.
        activateWhenReady = false
        selected = 0
        selectionTouched = false
        pointerArmed = false
        busy = true
        debounce.restart()
    }
    function setQuery(text) { search.text = text; edited() }
    function selectFromPointer(index, x, y) {
        if (!pointerArmed) { pointerX = x; pointerY = y; pointerArmed = true; return }
        if (Math.abs(x - pointerX) + Math.abs(y - pointerY) < 2) return
        pointerX = x; pointerY = y
        if (displaySerial !== querySerial) return
        selectionTouched = true
        selected = index
    }

    function send(message) {
        if (ready) backend.write(JSON.stringify(message) + "\n")
    }
    function syncApps() {
        var apps = []
        var values = DesktopEntries.applications.values || []
        for (var i = 0; i < values.length; i++) {
            var e = values[i]
            if (e.noDisplay || (root.shell && root.shell.appLibrary && root.shell.appLibrary.isHiddenEntry(e))) continue
            apps.push({id: String(e.id), name: String(e.name), icon: String(e.icon), comment: String(e.comment || e.genericName || "Application"), keywords: (e.keywords || []).join(" ")})
        }
        send({type: "apps", apps: apps})
    }
    function open(payloadJson) {
        var payload = ({})
        try { payload = JSON.parse(payloadJson || "{}") } catch (e) {}
        if (dmenu) finishDmenu(null)
        dmenu = payload.mode === "select" || payload.mode === "input" ? payload : null
        scope = payload.scope || (payload.menu && payload.menu !== "root" ? "flint.omarchy/" + payload.menu : "")
        scopeTitle = dmenu ? dmenu.prompt : (payload.title || (scope ? "Omarchy" : ""))
        history = []
        confirmation = null
        errorMessage = ""
        statusMessage = ""
        selected = 0
        selectionTouched = false
        pointerArmed = false
        activateWhenReady = false
        applyRows([])
        opened = true
        search.text = payload.query || ""
        if (!backend.running) backend.running = true
        syncApps()
        refresh()
        Qt.callLater(function() { search.forceActiveFocus() })
    }
    function close() {
        if (dmenu) finishDmenu(null)
        opened = false
        confirmation = null
        activateWhenReady = false
        querySerial++
        debounce.stop()
        busy = false
        send({type: "cancel"})
    }
    function toggle() { if (opened) close(); else open("{}") }
    function ping() { return "ok" }
    function refresh() {
        if (!opened) return "ok"
        debounce.stop()
        querySerial++
        selected = 0
        selectionTouched = false
        pointerArmed = false
        if (dmenu) {
            var result = []
            var options = dmenu.options || []
            for (var i = 0; i < options.length; i++) {
                var parts = String(options[i]).split("\t")
                var title = parts.length > 1 ? parts[1] : parts[0]
                var detail = parts.length > 2 ? parts.slice(2).join("\t") : ""
                if ((title + " " + detail).toLowerCase().indexOf(search.text.toLowerCase()) < 0) continue
                result.push({id: String(i), title: title, subtitle: detail, icon: parts.length > 1 ? parts[0] : "›",
                             tint: "#aaa9b0", section: "Select an option", verb: "Select", value: title + (detail ? "\t" + detail : "")})
            }
            applyRows(result)
            displaySerial = querySerial
            busy = false
            if (activateWhenReady) { activateWhenReady = false; activate() }
        } else {
            busy = true
            send({type: "query", id: querySerial, query: search.text, scope: scope})
        }
        return "ok"
    }
    function navigate(nextScope, title) {
        history = history.concat([{scope: scope, title: scopeTitle, query: search.text}])
        scope = nextScope
        scopeTitle = title || "Extensions"
        search.text = ""
        applyRows([])
        selected = 0
        selectionTouched = false
        activateWhenReady = false
        pointerArmed = false
        refresh()
        resultList.positionViewAtBeginning()
    }
    function goBack(clearSearch) {
        if (confirmation) { confirmation = null; return }
        if (clearSearch && search.text) { search.text = ""; refresh(); return }
        if (history.length) {
            var prior = history[history.length - 1]
            history = history.slice(0, -1)
            scope = prior.scope; scopeTitle = prior.title; search.text = prior.query
            applyRows([]); refresh()
        } else if (scope) {
            scope = ""; scopeTitle = ""; search.text = ""; applyRows([]); refresh()
        }
        selected = 0
        selectionTouched = false
        pointerArmed = false
        activateWhenReady = false
        resultList.positionViewAtBeginning()
    }
    function select(delta) {
        if (!rows.length) return
        selectionTouched = true
        pointerArmed = false
        selected = (selected + delta + rows.length) % rows.length
        resultList.positionViewAtIndex(selected, ListView.Contain)
    }
    function activate() {
        if (confirmation) return
        if (debounce.running || displaySerial !== querySerial) { activateWhenReady = true; return }
        if (current.disabled) return
        if (dmenu) {
            if (dmenu.mode === "input") finishDmenu(search.text)
            else if (rows.length) finishDmenu(current.value)
            return
        }
        if (current.token) send({type: "activate", token: current.token})
    }
    function finishDmenu(value) {
        var payload = dmenu
        dmenu = null
        opened = false
        if (!payload || !payload.doneFile) return
        // Each reply owns immutable paths, including when two callers overlap.
        var argv = ["python", root.projectPath + "/flint/reply.py", payload.selectionFile || "", payload.doneFile]
        if (value !== null) argv.push(String(value))
        Quickshell.execDetached(argv)
    }
    function receive(message) {
        if (message.type === "ready") {
            ready = true
            syncApps()
            if (opened) refresh()
        } else if (message.type === "results" && message.id === querySerial && opened && !dmenu) {
            var selectedId = selectionTouched ? current.id : ""
            var selectedExt = current.extensionId
            if (!message.pending || message.rows.length) {
                applyRows(message.rows)
                displaySerial = message.id
            }
            busy = message.pending
            if (message.appearance) appearance = message.appearance
            errorMessage = message.errors.join(" · ")
            if (selectedId) {
                for (var i = 0; i < rows.length; i++) {
                    if (rows[i].id === selectedId && rows[i].extensionId === selectedExt) { selected = i; break }
                }
            }
            selected = Math.max(0, Math.min(selected, rows.length - 1))
            if (!selectionTouched) {
                selected = 0
                resultList.positionViewAtBeginning()
            }
            if (activateWhenReady && !message.pending) {
                activateWhenReady = false
                activate()
            }
        } else if (message.type === "action") {
            if (message.confirm) { confirmation = message; return }
            if (message.scope !== undefined) navigate(message.scope, current.title)
            if (message.refresh) refresh()
            if (message.close) opened = false
            if (message.launch) {
                pendingLaunches = message.launch
                launchDelay.restart()
            }
            statusMessage = message.message || ""
        } else if (message.type === "error") {
            busy = false
            errorMessage = message.message
        }
    }
    function capture(path) {
        card.grabToImage(function(result) { result.saveToFile(path) })
        return "ok"
    }
    function inspect() {
        return JSON.stringify({opened: opened, ready: ready, busy: busy, scope: scope, query: search.text,
            count: rows.length, titles: rows.map(function(r) { return r.title }), selected: selected,
            selectedTitle: current.title || "", density: compact ? "compact" : "comfortable",
            modelCount: resultModel.count, loadingVisible: showLoading && !rows.length,
            rowCreations: rowCreationCount,
            querySerial: querySerial, displaySerial: displaySerial, error: errorMessage})
    }

    ListModel { id: resultModel; dynamicRoles: true }

    Process {
        id: backend
        command: ["python", "-u", "-m", "flint.host"]
        workingDirectory: root.projectPath
        stdinEnabled: true
        running: true
        stdout: SplitParser {
            onRead: function(data) {
                try { root.receive(JSON.parse(data)) } catch (e) { root.errorMessage = "Extension host: " + e.message }
            }
        }
        stderr: SplitParser { onRead: function(data) { console.warn("Flint host:", data) } }
        onExited: {
            root.ready = false
            root.busy = false
            root.errorMessage = "Extension host stopped. Close and reopen Flint to restart it."
        }
    }
    Timer { id: debounce; interval: 24; onTriggered: root.refresh() }
    Timer { id: loadingDelay; interval: 180; onTriggered: root.showLoading = root.busy }
    Timer {
        id: launchDelay
        interval: 70
        onTriggered: {
            var commands = root.pendingLaunches
            root.pendingLaunches = []
            for (var i = 0; i < commands.length; i++) Quickshell.execDetached(commands[i])
        }
    }
    Connections {
        target: DesktopEntries.applications
        function onValuesChanged() { root.syncApps(); if (root.opened) root.refresh() }
    }

    PanelWindow {
        id: panel
        visible: root.opened
        anchors { top: true; bottom: true; left: true; right: true }
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "flint"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

        Rectangle {
            anchors.fill: parent
            color: "#65000000"
            MouseArea { anchors.fill: parent; onClicked: root.close() }
        }
        Rectangle {
            id: card
            anchors.horizontalCenter: parent.horizontalCenter
            y: Math.max(24, (parent.height - height) * 0.40)
            width: Math.min(root.compact ? 640 : 760, parent.width - 40)
            height: Math.min(root.compact ? 540 : 576, parent.height - 48)
            radius: 17
            color: "#222126"
            border.width: 1
            border.color: "#51474a"
            clip: true
            Accessible.role: Accessible.Dialog
            Accessible.name: "Flint command palette"

            Item {
                id: searchBar
                x: root.compact ? 20 : 24; y: 0; width: parent.width - x * 2; height: root.headerHeight
                Item {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 22; height: 22
                    Rectangle { x: 1; y: 1; width: 15; height: 15; radius: 7.5; color: "transparent"; border.color: root.accent; border.width: 1.8 }
                    Rectangle { x: 13; y: 13; width: 9; height: 1.8; radius: 0.9; rotation: 45; transformOrigin: Item.Left; color: root.accent }
                }
                TextInput {
                    id: search
                    x: 39; width: parent.width - 103; height: 40
                    anchors.verticalCenter: parent.verticalCenter
                    verticalAlignment: TextInput.AlignVCenter
                    color: "#f1edf0"
                    selectionColor: "#6b5049"
                    selectedTextColor: "#ffffff"
                    font.family: "Adwaita Sans"
                    font.pixelSize: root.compact ? 18 : 20
                    selectByMouse: true
                    clip: true
                    focus: true
                    Accessible.name: root.dmenu ? root.dmenu.prompt : "Search commands, apps and extensions"
                    Text {
                        anchors.fill: parent
                        verticalAlignment: Text.AlignVCenter
                        text: root.dmenu ? root.dmenu.prompt : root.scope ? "Search " + root.scopeTitle.toLowerCase() + "…" : "What would you like to do?"
                        color: "#79747f"
                        font: parent.font
                        visible: !parent.text && !parent.preeditText
                        elide: Text.ElideRight
                    }
                    onTextEdited: root.edited()
                    Keys.onPressed: function(event) {
                        if (root.confirmation && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && event.modifiers & Qt.ControlModifier) {
                            var token = root.confirmation.token
                            root.confirmation = null
                            root.send({type: "activate", token: token, confirmed: true})
                            event.accepted = true
                        }
                        else if (event.key === Qt.Key_Escape) { root.close(); event.accepted = true }
                        else if (event.key === Qt.Key_Left && !text && !preeditText && (root.scope || root.history.length)) { root.goBack(false); event.accepted = true }
                        else if (event.key === Qt.Key_Down || event.key === Qt.Key_N && event.modifiers & Qt.ControlModifier) { root.select(1); event.accepted = true }
                        else if (event.key === Qt.Key_Up || event.key === Qt.Key_P && event.modifiers & Qt.ControlModifier) { root.select(-1); event.accepted = true }
                        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { root.activate(); event.accepted = true }
                        else if (event.key === Qt.Key_Backspace && !text && root.scope) { root.goBack(false); event.accepted = true }
                        else if (event.key === Qt.Key_Comma && event.modifiers & Qt.ControlModifier) { root.navigate("flint.settings", "Settings"); event.accepted = true }
                        else if (event.key === Qt.Key_K && event.modifiers & Qt.ControlModifier) { root.navigate("flint.settings/" + (root.current.extensionId || "flint.settings"), "Extension settings"); event.accepted = true }
                    }
                }
                Keycap { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; label: "esc" }
            }
            Rectangle { x: 1; y: root.headerHeight; width: parent.width - 2; height: 1; color: "#37333b" }

            Row {
                id: breadcrumb
                x: root.compact ? 22 : 26; y: root.headerHeight + 16; spacing: 10; height: 18
                Text { id: brand; anchors.verticalCenter: parent.verticalCenter; text: "FLINT"; color: root.accent; font.family: "Adwaita Sans"; font.pixelSize: 10; font.letterSpacing: 2; font.weight: Font.Bold }
                Text { anchors.baseline: brand.baseline; text: root.scope || root.dmenu ? "›" : "/"; color: "#635c68"; font.pixelSize: 11; font.family: "Adwaita Sans" }
                Text {
                    anchors.baseline: brand.baseline
                    text: root.scope || root.dmenu ? root.scopeTitle : search.text ? "Search results" : "A little less friction. A little more flow."
                    color: "#96909e"; font.family: "Adwaita Sans"; font.pixelSize: 11
                }
            }
            Item {
                x: 12; y: root.contentTop; width: parent.width - 24; height: parent.height - y - 57
                ListView {
                    id: resultList
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: root.previewVisible ? parent.width * 0.55 : parent.width
                    model: resultModel
                    clip: true
                    spacing: 3
                    boundsBehavior: Flickable.StopAtBounds
                    currentIndex: root.selected
                    cacheBuffer: 100
                    delegate: Column {
                        id: delegateRoot
                        required property var entry
                        required property int index
                        width: resultList.width
                        property bool sectionStart: (!root.scope && !search.text) ? index === 0 : (index === 0 || !!(root.rows[index - 1] && root.rows[index - 1].section !== entry.section))
                        Item {
                            width: parent.width
                            height: delegateRoot.sectionStart ? (root.compact ? 22 : 26) : 0
                            visible: delegateRoot.sectionStart
                            Text {
                                x: 14; y: 4
                                text: !root.scope && !search.text ? (delegateRoot.index === 0 ? "Your everyday essentials" : "") : delegateRoot.entry.section
                                color: "#827b89"
                                font.family: "Adwaita Sans"; font.pixelSize: 10; font.weight: Font.Medium
                            }
                        }
                        ResultRow {
                            Component.onCompleted: root.rowCreationCount++
                            width: parent.width
                            entry: delegateRoot.entry
                            compact: root.compact
                            selected: root.selected === delegateRoot.index
                            accent: root.accent
                            onHovered: function(x, y) { root.selectFromPointer(delegateRoot.index, x, y) }
                            onActivated: { root.selected = delegateRoot.index; root.activate() }
                        }
                    }
                }
                Rectangle {
                    visible: root.previewVisible
                    x: resultList.width + 12; width: 1; height: parent.height - 12; color: "#37333b"
                }
                Item {
                    id: preview
                    visible: root.previewVisible
                    x: resultList.width + 30
                    width: parent.width - x - 18
                    height: parent.height
                    Text {
                        x: 0; y: 10; text: root.current.previewLabel || "PREVIEW"
                        font.family: "Adwaita Sans"; font.pixelSize: 10; font.letterSpacing: 2
                        color: "#8d8795"
                    }
                    Rectangle {
                        y: 55; width: parent.width; height: 100; radius: 12
                        visible: !!root.current.swatch
                        color: root.current.swatch || "transparent"
                    }
                    Text {
                        y: root.current.swatch ? 175 : 60
                        width: parent.width
                        height: parent.height - y - 66
                        text: root.current.preview || ""
                        textFormat: Text.PlainText
                        color: root.current.previewLabel === "CLIPBOARD" ? "#d5d0da" : root.accent
                        font.family: root.current.emoji ? "Noto Color Emoji" : root.current.previewLabel === "CLIPBOARD" ? "Adwaita Sans" : "Adwaita Mono"
                        font.pixelSize: root.current.emoji ? 72 : root.current.previewLabel === "CLIPBOARD" ? 13 : root.compact ? 24 : 30
                        wrapMode: Text.WrapAnywhere
                        elide: Text.ElideRight
                    }
                    Image {
                        anchors.fill: parent; anchors.topMargin: 44; anchors.bottomMargin: 50
                        source: root.current.previewImage ? "file://" + root.current.previewImage : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }
                    Text {
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 18
                        width: parent.width
                        text: root.current.previewDetail || "Press return to copy"
                        textFormat: Text.PlainText
                        color: "#928b9b"; font.family: "Adwaita Sans"; font.pixelSize: 11
                        wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight
                    }
                }
                Column {
                    visible: root.rows.length === 0 && (!root.busy || root.showLoading)
                    anchors.centerIn: parent
                    spacing: 14
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "✳"; color: root.accent; font.pixelSize: 42 }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: root.busy ? "Finding your next move…" : root.dmenu && root.dmenu.mode === "input" ? "Type above, then press return" : search.text ? "No matching results" : root.scope === "flint.clipboard" ? "Your clipboard is empty" : "Ready when you are"
                        color: "#cbc5d0"; font.family: "Adwaita Sans"; font.pixelSize: 16
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: root.scope === "flint.converter" ? "Try 2m in feet or 10 am in London" : root.scope === "flint.calculator" ? "Try sqrt(144) + 15% of 80" : "Search by name. Follow your curiosity."
                        color: "#827a8d"; font.family: "Adwaita Sans"; font.pixelSize: 12
                    }
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom; anchors.bottomMargin: 48
                x: 1; width: parent.width - 2; height: 1; color: "#37333b"
            }
            Item {
                x: 24; y: parent.height - 47; width: parent.width - 48; height: 47
                Row {
                    anchors.verticalCenter: parent.verticalCenter; spacing: 9
                    Image { source: "assets/flint.svg"; width: 22; height: 22; sourceSize: Qt.size(44, 44); anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: root.busy && root.showLoading ? "Searching…" : root.statusMessage || (root.errorMessage ? "Extension needs attention" : "Flint")
                        color: root.errorMessage ? "#edae92" : "#a09aa7"; font.family: "Adwaita Sans"; font.pixelSize: 11
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                Row {
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                    Text { text: root.current.verb || "Select"; color: "#c8c1ce"; font.family: "Adwaita Sans"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    Keycap { label: "↵"; bright: true }
                    Item { width: 9; height: 1 }
                    Text { text: root.compact ? "Settings" : "Extension settings"; color: "#8b8295"; font.family: "Adwaita Sans"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    Keycap { label: "ctrl K" }
                }
            }
            Rectangle {
                visible: !!root.errorMessage
                x: 18; y: parent.height - 92; width: parent.width - 36; height: 38; radius: 6
                color: "#49322d"
                Text {
                    anchors.fill: parent; anchors.margins: 9
                    text: root.errorMessage; textFormat: Text.PlainText
                    color: "#f0bda9"; font.family: "Adwaita Sans"; font.pixelSize: 11; elide: Text.ElideRight
                }
            }
            Rectangle {
                anchors.fill: parent; radius: parent.radius; color: "#ed222126"
                visible: root.confirmation !== null
                MouseArea { anchors.fill: parent }
                Column {
                    anchors.centerIn: parent; spacing: 20
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "↗"; color: root.accent; font.pixelSize: 38 }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter; text: root.confirmation ? root.confirmation.confirm : ""
                        textFormat: Text.PlainText; color: "#eee8ee"; font.family: "Adwaita Sans"; font.pixelSize: 20
                    }
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "This action changes your system."; color: "#a49aaa"; font.family: "Adwaita Sans"; font.pixelSize: 13 }
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter; spacing: 12
                        Rectangle {
                            width: 110; height: 38; radius: 7; color: "#3b353f"
                            Text { anchors.centerIn: parent; text: "Cancel · esc"; color: "#eee8ee"; font.family: "Adwaita Sans"; font.pixelSize: 12 }
                            MouseArea { anchors.fill: parent; onClicked: root.confirmation = null }
                        }
                        Rectangle {
                            width: 140; height: 38; radius: 7; color: root.accent
                            Text { anchors.centerIn: parent; text: "Confirm · ctrl ↵"; color: "#2b2022"; font.family: "Adwaita Sans"; font.pixelSize: 12; font.bold: true }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    var token = root.confirmation.token
                                    root.confirmation = null
                                    root.send({type: "activate", token: token, confirmed: true})
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
