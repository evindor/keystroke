import QtQuick

// 4.0.2 injects the shared library. In 4.0.3, the panel Instantiator converts
// manifest.kinds to a QML sequence: manifestHasKind's Array.isArray check
// rejects it, leaving the scoped shell's appLibrary null.
// Reuse the installed Omarchy component in that case so desktop-entry
// filtering, icon refresh, launch feedback and removal keep matching the host.
//
// The same conversion also revokes the scoped shell itself. 4.0.3 stamps the
// API with a capability profile built from the converted manifest ("no-menu")
// and later recomputes it from the registry manifest ("menu"); the mismatch
// makes prunePluginApis() destroy the object, so `hostShell` drops back to null
// on a keepLoaded panel and never returns. Latch on the first injection and
// keep serving applications from the fallback once that happens.
Item {
  id: root
  property var hostShell: null
  property string omarchyPath: ""
  property bool hostSeen: false
  onHostShellChanged: if (hostShell) root.hostSeen = true
  readonly property var sharedLibrary: hostShell ? hostShell.appLibrary : null
  readonly property var library: sharedLibrary || fallback.item

  Loader {
    id: fallback
    active: root.hostSeen && !root.sharedLibrary && root.omarchyPath.length > 0
    source: active ? root.omarchyPath + "/shell/services/AppLibrary.qml" : ""
    onLoaded: item.omarchyPath = root.omarchyPath
  }
}
