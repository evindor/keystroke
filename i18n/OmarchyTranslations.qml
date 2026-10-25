import QtQuick
import qs.Commons as Commons

// Loaded only after Locale.qml detects Omarchy's 4.5 translation API.
// Keeping the new type here lets Omarchy 4.x compile the legacy path.
Commons.Translations {
  readonly property string formatLocale: Commons.I18n.formatLocale
  readonly property bool rightToLeft: Commons.I18n.rightToLeft
  function formatNumber(value, decimals) { return Commons.I18n.formatNumber(value, decimals) }
}
