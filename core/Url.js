.pragma library

// Recognize browser destinations without a network request or a shell. Keep
// the original spelling/escaping of the path, query and fragment intact.
function ipv4(host) {
  var parts = host.split(".")
  return parts.length === 4 && parts.every(function(p) { return /^(0|[1-9][0-9]{0,2})$/.test(p) && Number(p) <= 255 })
}

function ipv6(host) {
  if (host.indexOf(":") < 0 || !/^[0-9a-f:.]+$/i.test(host)) return false
  // An IPv4 tail occupies two of the eight groups.
  if (host.indexOf(".") >= 0) {
    var end = host.lastIndexOf(":")
    if (!ipv4(host.slice(end + 1))) return false
    host = host.slice(0, end + 1) + "0:0"
  }
  var halves = host.split("::")
  if (halves.length > 2) return false
  if (!halves.every(function(p) { return p === "" || /^[0-9a-f]{1,4}(?::[0-9a-f]{1,4})*$/i.test(p) })) return false
  var groups = halves.join(":").split(":").filter(function(p) { return p !== "" })
  if (!groups.every(function(p) { return /^[0-9a-f]{1,4}$/i.test(p) })) return false
  if (halves.length === 2) return groups.length < 8
  return groups.length === 8 && host.charAt(0) !== ":" && host.slice(-1) !== ":"
}

function domain(host, explicit) {
  // DNS permits a final root dot. QML's JS engine does not implement Unicode
  // property escapes, so use the conventional non-ASCII IDN character range
  // (excluding surrogates, separators and punctuation blocks).
  var name = host.replace(/\.$/, "")
  if (!name || name.length > 253 || /[\u2000-\u206f\u2e00-\u2e7f\u3000-\u303f\ud800-\udfff]/.test(name)) return false
  var labels = name.split(".")
  if (!labels.every(function(p) {
    return p.length <= 63 && /^[a-z0-9\u00a1-\uffef](?:[a-z0-9\u00a1-\uffef-]*[a-z0-9\u00a1-\uffef])?$/i.test(p)
  })) return false
  if (explicit || name.toLowerCase() === "localhost") return true
  var tld = labels[labels.length - 1]
  return labels.length > 1 && (/^[a-z\u00a1-\uffef]{2,}$/i.test(tld) || /^xn--[a-z0-9-]+$/i.test(tld))
}

// Launcher queries are full of file names, and a file extension is not a
// reliable tell: some are no TLD at all (notes.txt), others are live ones
// (readme.md, archive.zip). Bare two-part words ending in one of these are a
// file far more often than a host, so they need a scheme, a prefix, a port or
// a path before the palette offers to open a browser. Extensions that read as
// ordinary destinations stay out: io, co, rs, dev, app, ai, me, tv, so, cc.
var FILE_TAILS = ("txt md rst json yaml yml toml ini conf cfg log csv tsv xml html htm css scss sass less " +
  "js jsx ts tsx py pyc sh bash zsh fish lua rb php java kt swift cpp hpp pdf doc docx xls xlsx ppt pptx " +
  "odt ods png jpg jpeg gif webp svg ico bmp tiff psd mp3 mp4 mkv webm mov wav flac ogg " +
  "zip tar gz bz2 xz zst rar iso deb rpm exe dll bin img bak tmp swp lock patch diff " +
  "sql db sqlite epub ttf otf woff woff2 desktop service socket nix whl jar apk dmg msi srt torrent"
).split(" ").reduce(function(set, ext) { set[ext] = true; return set }, {})

// The === true keeps an inherited name (foo.constructor) from reading as a hit.
function fileTail(host) {
  var labels = host.replace(/\.$/, "").split(".")
  return labels.length > 1 && FILE_TAILS[labels[labels.length - 1].toLowerCase()] === true
}

// A typed prefix permits a single-label intranet host. Unprefixed text needs
// a domain, IP, localhost or an explicit http(s) scheme to be high confidence.
// Other schemes belong to other providers; this provider opens web pages.
function parse(value, explicit) {
  var text = String(value || "").trim()
  if (!text || /[\s\u0000-\u001f\u007f\\<>"`]/.test(text)) return null
  var scheme = /^(https?):\/\//i.exec(text)
  var relative = text.indexOf("//") === 0
  var rest = scheme ? text.slice(scheme[0].length) : relative ? text.slice(2) : text
  var split = rest.search(/[/?#]/)
  var authority = split < 0 ? rest : rest.slice(0, split)
  var suffix = split < 0 ? "" : rest.slice(split)
  if (!authority) return null
  // Userinfo is unambiguous only with an explicit scheme (never an email).
  var at = authority.lastIndexOf("@")
  if (at >= 0) {
    if (!scheme || !authority.slice(0, at) || authority.slice(0, at).indexOf("@") >= 0) return null
    authority = authority.slice(at + 1)
  }
  var match = /^(\[[^\]]+\]|[^:]+)(?::([0-9]+))?$/.exec(authority)
  if (!match || (match[2] !== undefined && (Number(match[2]) < 1 || Number(match[2]) > 65535))) return null
  var host = match[1], local = false
  if (host.charAt(0) === "[") {
    if (!ipv6(host.slice(1, -1))) return null
    local = true
  } else if (/^[0-9.]+$/.test(host)) {
    if (!ipv4(host)) return null
    local = true
  } else {
    if (!domain(host, !!scheme || !!explicit)) return null
    if (!scheme && !explicit && !suffix && match[2] === undefined && fileTail(host)) return null
    local = /(^|\.)localhost\.?$/i.test(host)
  }
  // Explicit schemes always win. Bare IP/localhost addresses are commonly
  // local HTTP services; all other scheme-less destinations default to HTTPS.
  var url = scheme ? text : (relative ? "https:" : local ? "http://" : "https://") + text
  return { url: url, host: host, suffix: suffix }
}
