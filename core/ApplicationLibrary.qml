import QtQuick

// 4.0.2 injects the shared library. In 4.0.3, the panel Instantiator converts
// manifest.kinds to a QML sequence: manifestHasKind's Array.isArray check
// rejects it, leaving the scoped shell's appLibrary null.
// Reuse the installed Omarchy component in that case so desktop-entry
// filtering, icon refresh, launch feedback and removal keep matching the host.
Item {
  id: root
  property var hostShell: null
  property string omarchyPath: ""
  readonly property var sharedLibrary: hostShell ? hostShell.appLibrary : null
  readonly property var library: sharedLibrary || fallback.item

  Loader {
    id: fallback
    active: !!root.hostShell && !root.sharedLibrary && root.omarchyPath.length > 0
    source: active ? root.omarchyPath + "/shell/services/AppLibrary.qml" : ""
    onLoaded: item.omarchyPath = root.omarchyPath
  }
}
