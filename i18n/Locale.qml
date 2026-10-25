import QtQuick
import Quickshell
import Quickshell.Io
import "Legacy.js" as Legacy
import "Plural.js" as Plural

// Omarchy 4.5 owns language choice and live switching. Older shells use the
// process's QLocale (LC_ALL/LC_MESSAGES/LANG), never the 4.5 language file.
QtObject {
  id: root
  property var directory: ""
  property string omarchyPath: ""
  property string systemLocale: Quickshell.env("LC_ALL") || Quickshell.env("LC_MESSAGES") || Quickshell.env("LANG") || Qt.locale().name
  property bool nativeAvailable: false
  readonly property bool nativeActive: !!native.item
  readonly property string legacyLanguage: Legacy.language(root.systemLocale)
  readonly property string language: nativeActive ? native.item.language : legacyLanguage
  readonly property string baseLanguage: legacyLanguage.split("-")[0]
  readonly property string formatLocale: nativeActive ? native.item.formatLocale : root.legacyLanguage
  readonly property bool rightToLeft: nativeActive ? native.item.rightToLeft : ["ar", "fa", "he", "ur", "ps", "yi", "dv"].indexOf(baseLanguage) >= 0
  readonly property var strings: nativeActive ? native.item.strings : Legacy.merge([english, base, selected])
  property var english: ({})
  property var base: ({})
  property var selected: ({})
  readonly property string directoryPath: String(directory).replace(/^file:\/\//, "").replace(/\/+$/, "")

  function catalog(code) { return root.directoryPath ? root.directoryPath + "/" + code + ".json" : "" }
  function t(key, fallback) {
    if (root.nativeActive) return native.item.t(key, fallback)
    var value = root.strings[key]
    if (value && typeof value === "object") value = value.other
    return typeof value === "string" && value.length ? value : fallback !== undefined ? fallback : key
  }
  function tn(key, count, fallback) {
    if (root.nativeActive) return native.item.tn(key, count, fallback)
    var layers = [[root.selected, root.legacyLanguage], [root.base, root.baseLanguage], [root.english, "en"]]
    for (var i = 0; i < layers.length; i++) {
      var value = Plural.pick(layers[i][0][key], layers[i][1], count)
      if (typeof value === "string" && value.length) return value
    }
    return fallback !== undefined ? fallback : key
  }
  function formatNumber(value, decimals) {
    if (root.nativeActive) return native.item.formatNumber(value, decimals)
    var number = Number(value)
    if (!isFinite(number)) return String(value)
    return decimals === undefined
      ? number.toLocaleString(Qt.locale(root.legacyLanguage), "g", 15)
      : number.toLocaleString(Qt.locale(root.legacyLanguage), "f", decimals)
  }

  // Capability detection also works with dev checkouts and backported APIs.
  // No version subprocess or unconditional reference to a new QML type.
  property FileView apiProbe: FileView {
    path: root.omarchyPath ? root.omarchyPath + "/shell/Commons/Translations.qml" : ""
    blockLoading: true
    printErrors: false
    onLoaded: root.nativeAvailable = true
    onLoadFailed: root.nativeAvailable = false
  }
  property Loader nativeLoader: Loader {
    id: native
    active: root.nativeAvailable
    onActiveChanged: if (active) setSource(Qt.resolvedUrl("OmarchyTranslations.qml"), { directory: root.directory })
    onStatusChanged: if (status === Loader.Error) root.nativeAvailable = false
  }
  onDirectoryChanged: if (native.item) native.item.directory = root.directory

  property FileView englishFile: FileView {
    path: root.catalog("en")
    blockLoading: true
    watchChanges: true
    printErrors: false
    onLoaded: root.english = Legacy.parse(text())
    onLoadFailed: root.english = ({})
    onFileChanged: reload()
  }
  property FileView baseFile: FileView {
    path: !root.nativeAvailable && root.baseLanguage !== root.legacyLanguage && root.baseLanguage !== "en" ? root.catalog(root.baseLanguage) : ""
    blockLoading: true
    watchChanges: true
    printErrors: false
    onLoaded: root.base = Legacy.parse(text())
    onLoadFailed: root.base = ({})
    onPathChanged: if (path === "") root.base = ({})
    onFileChanged: reload()
  }
  property FileView selectedFile: FileView {
    path: !root.nativeAvailable && root.legacyLanguage !== "en" ? root.catalog(root.legacyLanguage) : ""
    blockLoading: true
    watchChanges: true
    printErrors: false
    onLoaded: root.selected = Legacy.parse(text())
    onLoadFailed: root.selected = ({})
    onPathChanged: if (path === "") root.selected = ({})
    onFileChanged: reload()
  }
}
