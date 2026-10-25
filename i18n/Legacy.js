.pragma library

// QLocale names use underscores; catalogs use Omarchy/BCP-47 spellings.
function language(locale) {
  var code = String(locale || "").split(/[.@]/)[0].replace(/_/g, "-")
  if (!code || /^(C|POSIX)$/i.test(code)) return "en"
  var parts = code.split("-")
  if (!/^[A-Za-z]{2,3}$/.test(parts[0])) return "en"
  var out = [parts[0].toLowerCase()]
  for (var i = 1; i < parts.length; i++) {
    if (!/^[A-Za-z0-9]{2,8}$/.test(parts[i])) return "en"
    out.push(parts[i].length === 4 ? parts[i].charAt(0).toUpperCase() + parts[i].slice(1).toLowerCase() : parts[i].toUpperCase())
  }
  return out.join("-")
}

function parse(raw) {
  try {
    var value = JSON.parse(raw || "{}")
    return value && typeof value === "object" && !Array.isArray(value) ? value : ({})
  } catch (error) { return ({}) }
}

function merge(layers) {
  var out = ({})
  for (var i = 0; i < layers.length; i++)
    for (var key in layers[i]) out[key] = layers[i][key]
  return out
}
