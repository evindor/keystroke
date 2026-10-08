.pragma library

// TOTP: Time-Based One-Time Password generator for the Keystroke command palette.
// Pure functions for Base32 decoding, SHA-1 / SHA-256 / SHA-512 HMAC,
// RFC 6238 code generation, account persistence, and palette row building.

var NAME = "TOTP"
var ICON = "󰌆"
var COLOR = "#4ec9b0"
var DEFAULT_KEY = "totp"

var SETTINGS = [
  { key: "notifyOnCopy", type: "boolean", label: "Notification on copy", "default": true,
    description: "Show a desktop notification when an OTP code is copied" },
  { key: "searchInRoot", type: "boolean", label: "Search accounts in general launcher", "default": false,
    description: "Show matching accounts in the main search bar without typing 'totp' (off by default)" },
  { key: "backupDirectory", type: "string", label: "Auto-backup directory", "default": "",
    description: "Directory to save encrypted totp-backup.json after changes (leave empty to disable)" },
  { key: "backupPassphrase", type: "string", password: true, label: "Auto-backup passphrase", "default": "",
    description: "Passphrase for AES-256-GCM encryption. Both directory and passphrase are required." },
  { key: "showBackupPassphrase", type: "boolean", label: "Show backup passphrase", "default": false,
    description: "Display backup passphrase in plain text instead of masking it" },
  { key: "defaultDigits", type: "number", label: "Default digits", "default": 6, min: 6, max: 8, integer: true },
  { key: "defaultPeriod", type: "number", label: "Default period (seconds)", "default": 30, min: 10, max: 120, integer: true }
]

function resolveBackupPath(dir, home) {
  var d = String(dir || "").trim()
  if (!d) return ""
  if (d.charAt(0) === "~") {
    d = String(home || "") + d.slice(1)
  }
  return d.replace(/\/+$/, "") + "/totp-backup.json"
}

var PATTERNS = [
  { id: "otpauth", regex: "^\\s*otpauth:\\/\\/totp\\/", flags: "i", boost: 25, example: "otpauth://totp/GitHub:user?secret=JBSWY3DP", description: "Pasted TOTP URI" },
  { id: "base32", regex: "^\\s*[2-7A-Za-z]{16,64}\\s*$", flags: "", boost: 15, example: "JBSWY3DPEHPK3PXP", description: "Base32 secret key" }
]

// ------------------------------------------------------------------ helpers
function pad(n, width) {
  var s = String(n)
  while (s.length < width) s = "0" + s
  return s
}

function randomId() {
  return "totp-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8)
}

function normalizeSecret(secret) {
  return String(secret || "").toUpperCase().replace(/[\s\-=]/g, "")
}

function decodeBase32(secret) {
  var normalized = normalizeSecret(secret)
  if (!normalized) throw new Error("Secret cannot be empty.")

  var bits = 0
  var value = 0
  var bytes = []

  for (var i = 0; i < normalized.length; i++) {
    var code = normalized.charCodeAt(i)
    var digit = code >= 65 && code <= 90 ? code - 65 : code >= 50 && code <= 55 ? code - 24 : -1
    if (digit < 0) throw new Error("Invalid Base32 character: " + normalized.charAt(i))

    value = (value << 5) | digit
    bits += 5
    if (bits >= 8) {
      bytes.push((value >>> (bits -= 8)) & 0xff)
    }
  }

  if (!bytes.length) throw new Error("Secret is too short.")
  return new Uint8Array(bytes)
}

// ------------------------------------------------------------- cryptography
// Pure JS SHA-1
function sha1(bytes) {
  var l = bytes.length
  var bitLenHigh = Math.floor((l * 8) / 0x100000000)
  var bitLenLow = (l * 8) >>> 0
  var paddedLen = (((l + 8) >> 6) + 1) << 6
  var words = new Int32Array(paddedLen >> 2)
  for (var i = 0; i < l; i++) {
    words[i >> 2] |= (bytes[i] & 0xff) << (24 - (i % 4) * 8)
  }
  words[l >> 2] |= 0x80 << (24 - (l % 4) * 8)
  words[words.length - 2] = bitLenHigh
  words[words.length - 1] = bitLenLow

  var h0 = 0x67452301, h1 = 0xefcdab89, h2 = 0x98badcfe, h3 = 0x10325476, h4 = 0xc3d2e1f0
  var w = new Int32Array(80)

  for (var chunk = 0; chunk < words.length; chunk += 16) {
    for (var j = 0; j < 16; j++) w[j] = words[chunk + j]
    for (var j = 16; j < 80; j++) {
      var temp = w[j - 3] ^ w[j - 8] ^ w[j - 14] ^ w[j - 16]
      w[j] = (temp << 1) | (temp >>> 31)
    }

    var a = h0, b = h1, c = h2, d = h3, e = h4
    for (var j = 0; j < 80; j++) {
      var f, k
      if (j < 20) { f = (b & c) | ((~b) & d); k = 0x5a827999 }
      else if (j < 40) { f = b ^ c ^ d; k = 0x6ed9eba1 }
      else if (j < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8f1bbcdc }
      else { f = b ^ c ^ d; k = 0xca62c1d6 }

      var temp = (((a << 5) | (a >>> 27)) + f + e + k + w[j]) | 0
      e = d; d = c; c = (b << 30) | (b >>> 2); b = a; a = temp
    }

    h0 = (h0 + a) | 0
    h1 = (h1 + b) | 0
    h2 = (h2 + c) | 0
    h3 = (h3 + d) | 0
    h4 = (h4 + e) | 0
  }

  var res = new Uint8Array(20)
  var hs = [h0, h1, h2, h3, h4]
  for (var i = 0; i < 5; i++) {
    res[i * 4] = (hs[i] >>> 24) & 0xff
    res[i * 4 + 1] = (hs[i] >>> 16) & 0xff
    res[i * 4 + 2] = (hs[i] >>> 8) & 0xff
    res[i * 4 + 3] = hs[i] & 0xff
  }
  return res
}

// Pure JS SHA-256
var K256 = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
]

function sha256(bytes) {
  var l = bytes.length
  var bitLenHigh = Math.floor((l * 8) / 0x100000000)
  var bitLenLow = (l * 8) >>> 0
  var paddedLen = (((l + 8) >> 6) + 1) << 6
  var words = new Int32Array(paddedLen >> 2)
  for (var i = 0; i < l; i++) {
    words[i >> 2] |= (bytes[i] & 0xff) << (24 - (i % 4) * 8)
  }
  words[l >> 2] |= 0x80 << (24 - (l % 4) * 8)
  words[words.length - 2] = bitLenHigh
  words[words.length - 1] = bitLenLow

  var h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a
  var h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19
  var w = new Int32Array(64)

  for (var chunk = 0; chunk < words.length; chunk += 16) {
    for (var j = 0; j < 16; j++) w[j] = words[chunk + j]
    for (var j = 16; j < 64; j++) {
      var s0 = ((w[j - 15] >>> 7) | (w[j - 15] << 25)) ^ ((w[j - 15] >>> 18) | (w[j - 15] << 14)) ^ (w[j - 15] >>> 3)
      var s1 = ((w[j - 2] >>> 17) | (w[j - 2] << 15)) ^ ((w[j - 2] >>> 19) | (w[j - 2] << 13)) ^ (w[j - 2] >>> 10)
      w[j] = (w[j - 16] + s0 + w[j - 7] + s1) | 0
    }

    var a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7
    for (var j = 0; j < 64; j++) {
      var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))
      var ch = (e & f) ^ ((~e) & g)
      var temp1 = (h + S1 + ch + K256[j] + w[j]) | 0
      var S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))
      var maj = (a & b) ^ (a & c) ^ (b & c)
      var temp2 = (S0 + maj) | 0

      h = g; g = f; f = e; e = (d + temp1) | 0
      d = c; c = b; b = a; a = (temp1 + temp2) | 0
    }

    h0 = (h0 + a) | 0
    h1 = (h1 + b) | 0
    h2 = (h2 + c) | 0
    h3 = (h3 + d) | 0
    h4 = (h4 + e) | 0
    h5 = (h5 + f) | 0
    h6 = (h6 + g) | 0
    h7 = (h7 + h) | 0
  }

  var res = new Uint8Array(32)
  var hs = [h0, h1, h2, h3, h4, h5, h6, h7]
  for (var i = 0; i < 8; i++) {
    res[i * 4] = (hs[i] >>> 24) & 0xff
    res[i * 4 + 1] = (hs[i] >>> 16) & 0xff
    res[i * 4 + 2] = (hs[i] >>> 8) & 0xff
    res[i * 4 + 3] = hs[i] & 0xff
  }
  return res
}

// Pure JS SHA-512 (using 32-bit word pairs for 64-bit arithmetic)
var K512 = [
  [0x428a2f98, 0xd728ae22], [0x71374491, 0x23ef65cd], [0xb5c0fbcf, 0xec4d3b2f], [0xe9b5dba5, 0x8189dbbc],
  [0x3956c25b, 0xf348b538], [0x59f111f1, 0xb605d019], [0x923f82a4, 0xaf194f9b], [0xab1c5ed5, 0xda6d8118],
  [0xd807aa98, 0xa3030242], [0x12835b01, 0x45706fbe], [0x243185be, 0x4ee4b28c], [0x550c7dc3, 0xd5ffb4e2],
  [0x72be5d74, 0xf27b896f], [0x80deb1fe, 0x3b1696b1], [0x9bdc06a7, 0x25c71235], [0xc19bf174, 0xcf692694],
  [0xe49b69c1, 0x9ef14ad2], [0xefbe4786, 0x384f25e3], [0x0fc19dc6, 0x8b8cd5b5], [0x240ca1cc, 0x77ac9c65],
  [0x2de92c6f, 0x592b0275], [0x4a7484aa, 0x6ea6e483], [0x5cb0a9dc, 0xbd41fbd4], [0x76f988da, 0x831153b5],
  [0x983e5152, 0xee66dfab], [0xa831c66d, 0x2db43210], [0xb00327c8, 0x98fb213f], [0xbf597fc7, 0xbeef0ee4],
  [0xc6e00bf3, 0x3da88fc2], [0xd5a79147, 0x930aa725], [0x06ca6351, 0xe003826f], [0x14292967, 0x0a0e6e70],
  [0x27b70a85, 0x46d22ffc], [0x2e1b2138, 0x5c26c926], [0x4d2c6dfc, 0x5ac42aed], [0x53380d13, 0x9d95b3df],
  [0x650a7354, 0x8baf63de], [0x766a0abb, 0x3c77b2a8], [0x81c2c92e, 0x47edaee6], [0x92722c85, 0x1482353b],
  [0xa2bfe8a1, 0x4cf10364], [0xa81a664b, 0xbc423001], [0xc24b8b70, 0xd0f89791], [0xc76c51a3, 0x0654be30],
  [0xd192e819, 0xd6ef5218], [0xd6990624, 0x5565a910], [0xf40e3585, 0x5771202a], [0x106aa070, 0x32bbd1b8],
  [0x19a4c116, 0xb8d2d0c8], [0x1e376c08, 0x5141ab53], [0x2748774c, 0xdf8eeb99], [0x34b0bcb5, 0xe19b48a8],
  [0x391c0cb3, 0xc5c95a63], [0x4ed8aa4a, 0xe3418acb], [0x5b9cca4f, 0x7763e373], [0x682e6ff3, 0xd6b2b8a3],
  [0x748f82ee, 0x5defb2fc], [0x78a5636f, 0x43172f60], [0x84c87814, 0xa1f0ab72], [0x8cc70208, 0x1a6439ec],
  [0x90befffa, 0x23631e28], [0xa4506ceb, 0xde82bde9], [0xbef9a3f7, 0xb2c67915], [0xc67178f2, 0xe372532b],
  [0xca273ece, 0xea26619c], [0xd186b8c7, 0x21c0c207], [0xeada7dd6, 0xcde0eb1e], [0xf57d4f7f, 0xee6ed178],
  [0x06f067aa, 0x72176fba], [0x0a637dc5, 0xa2c898a6], [0x113f9804, 0xbef90dae], [0x1b710b35, 0x131c471b],
  [0x28db77f5, 0x23047d84], [0x32caab7b, 0x40c72493], [0x3c9ebe0a, 0x15c9bebc], [0x431d67c4, 0x9c100d4c],
  [0x4cc5d4be, 0xcb3e42b6], [0x597f299c, 0xfc657e2a], [0x5fcb6fab, 0x3ad6faec], [0x6c44198c, 0x4a475817]
]

function rotr64(h, l, n) {
  if (n < 32) {
    return [
      (((h >>> n) | (l << (32 - n)))) >>> 0,
      (((l >>> n) | (h << (32 - n)))) >>> 0
    ]
  } else {
    n -= 32
    return [
      (((l >>> n) | (h << (32 - n)))) >>> 0,
      (((h >>> n) | (l << (32 - n)))) >>> 0
    ]
  }
}

function shr64(h, l, n) {
  if (n < 32) {
    return [
      (h >>> n) >>> 0,
      (((l >>> n) | (h << (32 - n)))) >>> 0
    ]
  } else {
    return [
      0,
      (h >>> (n - 32)) >>> 0
    ]
  }
}

function add64(aH, aL, bH, bL) {
  var low = (aL + bL) >>> 0
  var carry = (aL + bL) > 0xffffffff ? 1 : 0
  return [
    (aH + bH + carry) >>> 0,
    low
  ]
}

function sha512(bytes) {
  var l = bytes.length
  var rem = l % 128
  var paddedLen = rem < 112 ? l + (128 - rem) : l + (256 - rem)
  var buf = new Uint8Array(paddedLen)
  buf.set(bytes)
  buf[l] = 0x80

  var bitLen = l * 8
  var bitLenHigh = Math.floor(bitLen / 0x100000000)
  var bitLenLow = bitLen >>> 0
  buf[paddedLen - 8] = (bitLenHigh >>> 24) & 0xff
  buf[paddedLen - 7] = (bitLenHigh >>> 16) & 0xff
  buf[paddedLen - 6] = (bitLenHigh >>> 8) & 0xff
  buf[paddedLen - 5] = bitLenHigh & 0xff
  buf[paddedLen - 4] = (bitLenLow >>> 24) & 0xff
  buf[paddedLen - 3] = (bitLenLow >>> 16) & 0xff
  buf[paddedLen - 2] = (bitLenLow >>> 8) & 0xff
  buf[paddedLen - 1] = bitLenLow & 0xff

  var H = [
    [0x6a09e667, 0xf3bcc908], [0xbb67ae85, 0x84caa73b],
    [0x3c6ef372, 0xfe94f82b], [0xa54ff53a, 0x5f1d36f1],
    [0x510e527f, 0xade682d1], [0x9b05688c, 0x2b3e6c1f],
    [0x1f83d9ab, 0xfb41bd6b], [0x5be0cd19, 0x137e2179]
  ]

  var W_H = new Uint32Array(80)
  var W_L = new Uint32Array(80)

  for (var chunk = 0; chunk < paddedLen; chunk += 128) {
    for (var j = 0; j < 16; j++) {
      var offset = chunk + j * 8
      W_H[j] = (((buf[offset] << 24) >>> 0) | (buf[offset + 1] << 16) | (buf[offset + 2] << 8) | buf[offset + 3]) >>> 0
      W_L[j] = (((buf[offset + 4] << 24) >>> 0) | (buf[offset + 5] << 16) | (buf[offset + 6] << 8) | buf[offset + 7]) >>> 0
    }
    for (var j = 16; j < 80; j++) {
      var w15h = W_H[j - 15], w15l = W_L[j - 15]
      var r1 = rotr64(w15h, w15l, 1), r8 = rotr64(w15h, w15l, 8), s7 = shr64(w15h, w15l, 7)
      var s0h = (r1[0] ^ r8[0] ^ s7[0]) >>> 0, s0l = (r1[1] ^ r8[1] ^ s7[1]) >>> 0

      var w2h = W_H[j - 2], w2l = W_L[j - 2]
      var r19 = rotr64(w2h, w2l, 19), r61 = rotr64(w2h, w2l, 61), s6 = shr64(w2h, w2l, 6)
      var s1h = (r19[0] ^ r61[0] ^ s6[0]) >>> 0, s1l = (r19[1] ^ r61[1] ^ s6[1]) >>> 0

      var sum1 = add64(W_H[j - 16], W_L[j - 16], s0h, s0l)
      var sum2 = add64(sum1[0], sum1[1], W_H[j - 7], W_L[j - 7])
      var sum3 = add64(sum2[0], sum2[1], s1h, s1l)
      W_H[j] = sum3[0]
      W_L[j] = sum3[1]
    }

    var aH = H[0][0], aL = H[0][1], bH = H[1][0], bL = H[1][1], cH = H[2][0], cL = H[2][1], dH = H[3][0], dL = H[3][1]
    var eH = H[4][0], eL = H[4][1], fH = H[5][0], fL = H[5][1], gH = H[6][0], gL = H[6][1], hH = H[7][0], hL = H[7][1]

    for (var j = 0; j < 80; j++) {
      var r14 = rotr64(eH, eL, 14), r18 = rotr64(eH, eL, 18), r41 = rotr64(eH, eL, 41)
      var S1h = (r14[0] ^ r18[0] ^ r41[0]) >>> 0, S1l = (r14[1] ^ r18[1] ^ r41[1]) >>> 0
      var chh = ((eH & fH) ^ ((~eH) & gH)) >>> 0, chl = ((eL & fL) ^ ((~eL) & gL)) >>> 0

      var t1_1 = add64(hH, hL, S1h, S1l)
      var t1_2 = add64(t1_1[0], t1_1[1], chh, chl)
      var t1_3 = add64(t1_2[0], t1_2[1], K512[j][0], K512[j][1])
      var t1 = add64(t1_3[0], t1_3[1], W_H[j], W_L[j])

      var r28 = rotr64(aH, aL, 28), r34 = rotr64(aH, aL, 34), r39 = rotr64(aH, aL, 39)
      var S0h = (r28[0] ^ r34[0] ^ r39[0]) >>> 0, S0l = (r28[1] ^ r34[1] ^ r39[1]) >>> 0
      var majh = ((aH & bH) ^ (aH & cH) ^ (bH & cH)) >>> 0, majl = ((aL & bL) ^ (aL & cL) ^ (bL & cL)) >>> 0
      var t2 = add64(S0h, S0l, majh, majl)

      hH = gH; hL = gL
      gH = fH; gL = fL
      fH = eH; fL = eL
      var newE = add64(dH, dL, t1[0], t1[1])
      eH = newE[0]; eL = newE[1]
      dH = cH; dL = cL
      cH = bH; cL = bL
      bH = aH; bL = aL
      var newA = add64(t1[0], t1[1], t2[0], t2[1])
      aH = newA[0]; aL = newA[1]
    }

    H[0] = add64(H[0][0], H[0][1], aH, aL)
    H[1] = add64(H[1][0], H[1][1], bH, bL)
    H[2] = add64(H[2][0], H[2][1], cH, cL)
    H[3] = add64(H[3][0], H[3][1], dH, dL)
    H[4] = add64(H[4][0], H[4][1], eH, eL)
    H[5] = add64(H[5][0], H[5][1], fH, fL)
    H[6] = add64(H[6][0], H[6][1], gH, gL)
    H[7] = add64(H[7][0], H[7][1], hH, hL)
  }

  var res = new Uint8Array(64)
  for (var i = 0; i < 8; i++) {
    var high = H[i][0], low = H[i][1]
    res[i * 8] = (high >>> 24) & 0xff
    res[i * 8 + 1] = (high >>> 16) & 0xff
    res[i * 8 + 2] = (high >>> 8) & 0xff
    res[i * 8 + 3] = high & 0xff
    res[i * 8 + 4] = (low >>> 24) & 0xff
    res[i * 8 + 5] = (low >>> 16) & 0xff
    res[i * 8 + 6] = (low >>> 8) & 0xff
    res[i * 8 + 7] = low & 0xff
  }
  return res
}

function hmac(hashFn, blockSize, key, message) {
  var k = key
  if (k.length > blockSize) {
    k = hashFn(k)
  }
  var kPadded = new Uint8Array(blockSize)
  kPadded.set(k)

  var oPad = new Uint8Array(blockSize)
  var iPad = new Uint8Array(blockSize)
  for (var i = 0; i < blockSize; i++) {
    oPad[i] = kPadded[i] ^ 0x5c
    iPad[i] = kPadded[i] ^ 0x36
  }

  var innerMsg = new Uint8Array(blockSize + message.length)
  innerMsg.set(iPad)
  innerMsg.set(message, blockSize)
  var innerHash = hashFn(innerMsg)

  var outerMsg = new Uint8Array(blockSize + innerHash.length)
  outerMsg.set(oPad)
  outerMsg.set(innerHash, blockSize)
  return hashFn(outerMsg)
}

// ------------------------------------------------------------- code generator
function generateCode(config, date) {
  var secret = decodeBase32(config.secret)
  var period = config.period || 30
  var digits = config.digits || 6
  var algo = (config.algorithm || "SHA1").toUpperCase()
  var timestamp = typeof date === "number" ? date : (date ? date.getTime() : Date.now())
  var counter = Math.floor(timestamp / 1000 / period)

  var high = Math.floor(counter / 0x100000000)
  var low = counter >>> 0
  var msg = new Uint8Array(8)
  msg[0] = (high >>> 24) & 0xff
  msg[1] = (high >>> 16) & 0xff
  msg[2] = (high >>> 8) & 0xff
  msg[3] = high & 0xff
  msg[4] = (low >>> 24) & 0xff
  msg[5] = (low >>> 16) & 0xff
  msg[6] = (low >>> 8) & 0xff
  msg[7] = low & 0xff

  var digest
  if (algo === "SHA1") digest = hmac(sha1, 64, secret, msg)
  else if (algo === "SHA256") digest = hmac(sha256, 64, secret, msg)
  else if (algo === "SHA512") digest = hmac(sha512, 128, secret, msg)
  else throw new Error("Unsupported algorithm: " + algo)

  var offset = digest[digest.length - 1] & 0x0f
  var truncated = ((digest[offset] & 0x7f) << 24) |
                  ((digest[offset + 1] & 0xff) << 16) |
                  ((digest[offset + 2] & 0xff) << 8) |
                  (digest[offset + 3] & 0xff)

  var mod = Math.pow(10, digits)
  var val = String(truncated % mod)
  while (val.length < digits) val = "0" + val

  var seconds = Math.floor(timestamp / 1000)
  var remainder = seconds % period
  var remainingSeconds = remainder === 0 ? period : (period - remainder)

  return { value: val, remainingSeconds: remainingSeconds }
}

function formatCode(val) {
  var s = String(val || "")
  if (s.length === 6) return s.slice(0, 3) + " " + s.slice(3)
  if (s.length === 8) return s.slice(0, 4) + " " + s.slice(4)
  return s
}

// ---------------------------------------------------------------- input parsing
function parseInput(input, name, issuerOverride) {
  var trimmed = String(input || "").trim()
  if (!trimmed) throw new Error("Secret or otpauth URI is required.")

  if (trimmed.toLowerCase().indexOf("otpauth:") !== 0) {
    var accountName = name ? String(name).trim() : ""
    if (!accountName) throw new Error("Name is required when entering a Base32 secret.")
    var secret = normalizeSecret(trimmed)
    decodeBase32(secret)
    return {
      name: accountName,
      issuer: issuerOverride ? String(issuerOverride).trim() : "",
      secret: secret,
      digits: 6,
      period: 30,
      algorithm: "SHA1"
    }
  }

  var url
  try {
    url = new URL(trimmed)
  } catch (_) {
    throw new Error("The otpauth URI is invalid.")
  }

  if (url.protocol !== "otpauth:" || url.hostname.toLowerCase() !== "totp") {
    throw new Error("Only otpauth://totp URIs are supported.")
  }

  var params = {}
  var search = url.search ? url.search.slice(1) : ""
  var pairs = search.split("&")
  for (var i = 0; i < pairs.length; i++) {
    if (!pairs[i]) continue
    var eq = pairs[i].indexOf("=")
    var k = (eq >= 0 ? pairs[i].slice(0, eq) : pairs[i]).toLowerCase()
    var v = eq >= 0 ? decodeURIComponent(pairs[i].slice(eq + 1).replace(/\+/g, " ")) : ""
    params[k] = v.trim()
  }

  var secretParam = normalizeSecret(params["secret"] || "")
  decodeBase32(secretParam)

  var label = ""
  try {
    label = decodeURIComponent(url.pathname || "").replace(/^\/+/, "").trim()
  } catch (_) {
    throw new Error("The otpauth URI is invalid.")
  }

  var labelParts = label.split(":")
  var labelIssuer = labelParts[0] ? labelParts[0].trim() : ""
  var labelName = labelParts.slice(1).join(":").trim()

  var issuer = (issuerOverride ? String(issuerOverride).trim() : "") ||
               params["issuer"] ||
               (labelName ? labelIssuer : "")
  var uriName = labelName || label
  var accName = (name ? String(name).trim() : "") || uriName || issuer
  if (!accName) throw new Error("The otpauth URI is missing an account name.")

  var digits = params["digits"] ? parseInt(params["digits"], 10) : 6
  if (isNaN(digits) || digits < 1 || digits > 10) digits = 6

  var period = params["period"] ? parseInt(params["period"], 10) : 30
  if (isNaN(period) || period <= 0) period = 30

  var algorithm = (params["algorithm"] || "SHA1").toUpperCase()
  if (algorithm !== "SHA1" && algorithm !== "SHA256" && algorithm !== "SHA512") {
    throw new Error("Unsupported algorithm: " + algorithm)
  }

  return {
    name: accName,
    issuer: issuer,
    secret: secretParam,
    digits: digits,
    period: period,
    algorithm: algorithm
  }
}

function parseAdd(text) {
  var t = String(text || "").trim()
  if (!t) return null
  if (t.toLowerCase().indexOf("add ") === 0) {
    t = t.slice(4).trim()
  }
  if (!t) return { incomplete: true, error: "Enter a secret or otpauth URI" }

  if (t.toLowerCase().indexOf("otpauth:") === 0) {
    try {
      var acc = parseInput(t)
      return { account: acc, incomplete: false }
    } catch (e) {
      return { incomplete: true, error: e.message || String(e) }
    }
  }

  var parts = t.split(/\s+/)
  var secretPart = parts[0]
  var namePart = parts.slice(1).join(" ").trim()
  try {
    var normalized = normalizeSecret(secretPart)
    decodeBase32(normalized)
    if (!namePart) {
      return {
        account: null,
        incomplete: true,
        secret: normalized,
        error: "Provide an account name (e.g. totp add " + secretPart + " GitHub)"
      }
    }
    return {
      account: {
        name: namePart,
        issuer: "",
        secret: normalized,
        digits: 6,
        period: 30,
        algorithm: "SHA1"
      },
      incomplete: false
    }
  } catch (_) {
    return { incomplete: true, error: "Invalid Base32 secret or otpauth URI" }
  }
}

// --------------------------------------------------------- account storage
function sortAccounts(accounts) {
  return (accounts || []).slice().sort(function(a, b) {
    var nameA = (a.name || "").toLowerCase()
    var nameB = (b.name || "").toLowerCase()
    if (nameA < nameB) return -1
    if (nameA > nameB) return 1
    return (a.id || "").localeCompare(b.id || "")
  })
}

function readAccounts(text) {
  var raw = String(text || "").trim()
  if (!raw) return []
  try {
    var parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    var out = []
    for (var i = 0; i < parsed.length; i++) {
      var item = parsed[i]
      if (!item || typeof item !== "object") continue
      if (!item.name || !item.secret) continue
      try {
        var secret = normalizeSecret(item.secret)
        decodeBase32(secret)
        out.push({
          id: String(item.id || randomId()),
          name: String(item.name).trim(),
          issuer: String(item.issuer || "").trim(),
          secret: secret,
          digits: Number(item.digits) || 6,
          period: Number(item.period) || 30,
          algorithm: (item.algorithm || "SHA1").toUpperCase()
        })
      } catch (_) { }
    }
    return sortAccounts(out)
  } catch (_) {
    return []
  }
}

function serializeAccounts(accounts) {
  return JSON.stringify(sortAccounts(accounts || []), null, 2) + "\n"
}

function addAccount(accounts, input) {
  var list = (accounts || []).slice()
  var acc = {
    id: input.id || randomId(),
    name: String(input.name || "").trim(),
    issuer: String(input.issuer || "").trim(),
    secret: normalizeSecret(input.secret),
    digits: Number(input.digits) || 6,
    period: Number(input.period) || 30,
    algorithm: (input.algorithm || "SHA1").toUpperCase()
  }
  var found = -1
  for (var i = 0; i < list.length; i++) {
    if (list[i].name === acc.name && list[i].issuer === acc.issuer && list[i].secret === acc.secret) {
      found = i
      break
    }
  }
  if (found >= 0) {
    list[found] = acc
  } else {
    list.push(acc)
  }
  return sortAccounts(list)
}

function generateId() {
  return randomId()
}

function updateAccount(accounts, input) {
  var list = (accounts || []).slice()
  var acc = {
    id: input.id || randomId(),
    name: String(input.name || "").trim(),
    issuer: String(input.issuer || "").trim(),
    secret: normalizeSecret(input.secret),
    digits: Number(input.digits) || 6,
    period: Number(input.period) || 30,
    algorithm: (input.algorithm || "SHA1").toUpperCase()
  }
  var found = -1
  for (var i = 0; i < list.length; i++) {
    if (list[i].id === acc.id) {
      found = i
      break
    }
  }
  if (found >= 0) {
    list[found] = acc
  } else {
    list.push(acc)
  }
  return sortAccounts(list)
}

function removeAccount(accounts, id) {
  var list = (accounts || []).filter(function(a) { return a.id !== id })
  return sortAccounts(list)
}

function buildUri(account) {
  var label = encodeURIComponent(account.name || "Account")
  if (account.issuer) {
    label = encodeURIComponent(account.issuer) + ":" + label
  }
  var uri = "otpauth://totp/" + label + "?secret=" + encodeURIComponent(account.secret)
  if (account.issuer) uri += "&issuer=" + encodeURIComponent(account.issuer)
  if (account.algorithm && account.algorithm !== "SHA1") uri += "&algorithm=" + encodeURIComponent(account.algorithm)
  if (account.digits && account.digits !== 6) uri += "&digits=" + account.digits
  if (account.period && account.period !== 30) uri += "&period=" + account.period
  return uri
}

// ------------------------------------------------------------- palette rows
function accountAction(code, account, settings) {
  if (settings && settings.notifyOnCopy) {
    return {
      type: "compound",
      actions: [
        { type: "copy", text: code.value },
        { type: "notify", glyph: "󰌆", headline: "OTP Copied", body: code.value + " · " + account.name }
      ]
    }
  }
  return { type: "copy", text: code.value }
}

function accountActionRows(account, now, settings, scopeKey) {
  var sKey = scopeKey || DEFAULT_KEY
  var code = generateCode(account, now)
  var formatted = formatCode(code.value)
  var uri = buildUri(account)
  var out = []

  // 1. Copy OTP Code
  out.push({
    id: "act-copy-otp/" + account.id,
    title: "Copy OTP: " + formatted,
    subtitle: (account.issuer ? account.issuer + " · " : "") + code.remainingSeconds + "s remaining · Enter copies, Ctrl+Enter pastes",
    icon: ICON,
    tint: COLOR,
    section: account.name + (account.issuer ? " (" + account.issuer + ")" : ""),
    verb: "Copy OTP",
    altVerb: "Paste OTP",
    tier: "answer",
    score: 100,
    accessory: formatted + "  ·  " + code.remainingSeconds + "s",
    preview: formatted,
    previewLabel: (account.issuer || "TOTP").toUpperCase(),
    previewDetail: account.name + (account.issuer ? " (" + account.issuer + ")" : "") +
                   "\n\nAlgorithm: " + account.algorithm +
                   "\nDigits: " + account.digits +
                   "\nPeriod: " + account.period + "s" +
                   "\nRemaining: " + code.remainingSeconds + "s",
    action: accountAction(code, account, settings),
    altAction: { type: "paste", text: code.value }
  })

  // 2. Paste OTP Code
  out.push({
    id: "act-paste-otp/" + account.id,
    title: "Paste OTP Code",
    subtitle: "Paste " + formatted + " directly into the active window",
    icon: "󰌆",
    tint: COLOR,
    section: "Actions",
    verb: "Paste OTP",
    tier: "item",
    score: 90,
    action: { type: "paste", text: code.value }
  })

  // 3. Copy Secret Key
  out.push({
    id: "act-copy-secret/" + account.id,
    title: "Copy Secret Key",
    subtitle: account.secret + " (" + account.algorithm + ", " + account.digits + " digits)",
    icon: "󰌆",
    tint: COLOR,
    section: "Actions",
    verb: "Copy Secret",
    tier: "item",
    score: 80,
    action: { type: "copy", text: account.secret }
  })

  // 4. Copy otpauth:// URI
  out.push({
    id: "act-copy-uri/" + account.id,
    title: "Copy otpauth:// URI",
    subtitle: uri,
    icon: "󰌆",
    tint: COLOR,
    section: "Actions",
    verb: "Copy URI",
    tier: "item",
    score: 70,
    action: { type: "copy", text: uri }
  })

  // 5. Edit Account
  out.push({
    id: "act-edit/" + account.id,
    title: "Edit Account",
    subtitle: "Modify account name, issuer, secret key, algorithm, digits or period",
    icon: "󰏫",
    tint: "#3b82f6",
    section: "Manage",
    verb: "Edit Account",
    tier: "item",
    score: 60,
    action: { type: "totp-open-edit", account: account }
  })

  // 6. Delete Account
  out.push({
    id: "act-delete/" + account.id,
    title: "Delete Account",
    subtitle: "Permanently delete this account and secret key",
    icon: "󰆴",
    tint: "#ef4444",
    section: "Manage",
    verb: "Delete Account",
    tier: "item",
    score: 50,
    confirm: "Delete account " + account.name + (account.issuer ? " (" + account.issuer + ")" : "") + "?",
    confirmDetail: "This will permanently remove the account and secret key from Keystroke. This action cannot be undone.",
    confirmText: "Delete Account",
    cancelText: "Keep Account",
    action: { type: "totp-remove", id: account.id }
  })

  return out
}

function accountRow(account, now, settings, explicitScore, scopeKey, index) {
  var sKey = scopeKey || DEFAULT_KEY
  var code = generateCode(account, now)
  var formatted = formatCode(code.value)
  var subtitle = (account.issuer && account.issuer !== account.name ? account.issuer + " · " : "") +
                 formatted + " · " + code.remainingSeconds + "s"

  var quickPaste = !!(settings && settings.quickPasteOnCtrlEnter)
  var row = {
    id: "account/" + account.id,
    title: account.name,
    subtitle: subtitle,
    icon: ICON,
    tint: COLOR,
    section: "Accounts",
    verb: "Copy OTP",
    altVerb: quickPaste ? "Paste OTP" : "Actions",
    tier: "item",
    order: index !== undefined ? 10 + index : 10,
    keywords: "totp otp 2fa " + account.name + " " + (account.issuer || ""),
    description: "time-based one-time password " + account.name + " " + (account.issuer || ""),
    accessory: formatted + "  ·  " + code.remainingSeconds + "s",
    preview: formatted,
    previewLabel: (account.issuer || "TOTP").toUpperCase(),
    previewDetail: account.name + (account.issuer ? " (" + account.issuer + ")" : "") +
                   "\n\nAlgorithm: " + account.algorithm +
                   "\nDigits: " + account.digits +
                   "\nPeriod: " + account.period + "s" +
                   "\nRemaining: " + code.remainingSeconds + "s" +
                   "\n\n↵ Copy OTP  ·  ^↵ Actions (Edit, Delete, Copy Secret)",
    action: accountAction(code, account, settings),
    altAction: quickPaste ? { type: "paste", text: code.value } : { type: "navigate", scope: sKey + "/account/" + account.id, title: account.name }
  }
  if (explicitScore !== undefined) row.score = explicitScore
  return row
}

function quickOtpRow(account, now, settings) {
  var code = generateCode(account, now)
  var formatted = formatCode(code.value)
  return {
    id: "quick-otp",
    title: "Quick OTP: " + formatted,
    subtitle: "Valid for " + code.remainingSeconds + "s · Enter copies, Ctrl+Enter pastes",
    icon: ICON,
    tint: COLOR,
    section: "Quick OTP",
    verb: "Copy OTP",
    altVerb: "Paste OTP",
    tier: "answer",
    score: 100,
    order: 0,
    accessory: formatted + "  ·  " + code.remainingSeconds + "s",
    preview: formatted,
    previewLabel: "QUICK OTP",
    previewDetail: "Temporary code from secret/URI\n\nAlgorithm: " + account.algorithm +
                   "\nDigits: " + account.digits +
                   "\nPeriod: " + account.period + "s" +
                   "\nRemaining: " + code.remainingSeconds + "s",
    action: accountAction(code, account, settings),
    altAction: { type: "paste", text: code.value }
  }
}

function navRow(accounts, score, scopeKey) {
  var count = (accounts || []).length
  return {
    id: "open",
    title: "TOTP Authenticator",
    subtitle: count ? count + " saved account" + (count === 1 ? "" : "s") : "Time-based one-time passwords: totp",
    icon: ICON,
    tint: COLOR,
    section: "Security",
    verb: "Open",
    tier: "item",
    score: score,
    order: 40,
    keywords: "totp otp 2fa authenticator 2-factor",
    description: "time-based one-time password authenticator codes",
    accessory: count ? String(count) : "",
    action: { type: "navigate", scope: scopeKey, title: "TOTP" }
  }
}

function rows(query, accounts, settings, now, scoped, scopeKey, viaCommand, patterns) {
  var out = []
  var q = String(query || "").trim()
  var sKey = scopeKey || DEFAULT_KEY
  var list = accounts || []

  var scStr = typeof scoped === "string" ? scoped : (scoped ? sKey : "")

  // Sub-scope: individual account actions
  if (scStr && scStr.indexOf(sKey + "/account/") === 0) {
    var accId = scStr.slice((sKey + "/account/").length)
    for (var i = 0; i < list.length; i++) {
      if (list[i].id === accId) {
        return accountActionRows(list[i], now, settings, sKey)
      }
    }
    return [{
      id: "not-found",
      title: "Account not found",
      subtitle: "This account may have been removed",
      icon: ICON,
      verb: "",
      tier: "item",
      score: 1,
      disabled: true,
      action: { type: "noop" }
    }]
  }

  // Sub-scope: manage screen
  if (scStr && scStr === sKey + "/manage") {
    out.push({
      id: "manage-add",
      title: "Add New Account",
      subtitle: "Open form to add a new TOTP secret or scan URI",
      icon: "󰐿",
      tint: COLOR,
      section: "Actions",
      verb: "Add Account",
      tier: "item",
      order: 0,
      score: 100,
      action: { type: "totp-open-add" }
    })
    out.push({
      id: "manage-export",
      title: "Export Accounts Backup",
      subtitle: "Save encrypted or plain backup of all accounts",
      icon: "󰁯",
      section: "Backup",
      verb: "Export",
      tier: "item",
      order: 80,
      score: 10,
      action: { type: "totp-export" }
    })
    out.push({
      id: "manage-import",
      title: "Import Accounts Backup",
      subtitle: "Load accounts from backup file",
      icon: "󰁪",
      section: "Backup",
      verb: "Import",
      tier: "item",
      order: 81,
      score: 9,
      action: { type: "totp-import" }
    })
    var autoBackupDir = (settings && settings.backupDirectory) || ""
    var autoBackupPass = (settings && settings.backupPassphrase) || ""
    var showPass = !!(settings && settings.showBackupPassphrase)
    var passDisplay = autoBackupPass ? (showPass ? autoBackupPass : "•••••••• (" + autoBackupPass.length + " chars)") : "Not configured"
    out.push({
      id: "manage-backup-config",
      title: "Auto-backup: " + (autoBackupDir ? autoBackupDir : "Disabled"),
      subtitle: "Passphrase: " + passDisplay + " · Enter opens Settings",
      icon: "󰌆",
      tint: COLOR,
      section: "Backup",
      verb: "Settings",
      tier: "item",
      order: 85,
      score: 8,
      action: { type: "navigate", scope: "settings/" + sKey, title: "TOTP Settings" }
    })
    for (var i = 0; i < list.length; i++) {
      var a = list[i]
      out.push({
        id: "manage/" + a.id,
        title: a.name,
        subtitle: (a.issuer ? a.issuer + " · " : "") + "Secret: " + a.secret.slice(0, 4) + "••••" + a.secret.slice(-4),
        icon: ICON,
        tint: COLOR,
        section: "Manage Accounts",
        verb: "Actions",
        altVerb: "Delete",
        tier: "item",
        order: 10 + i,
        score: 50 - i,
        confirm: "Delete account " + a.name + (a.issuer ? " (" + a.issuer + ")" : "") + "?",
        confirmDetail: "This will permanently remove the account and secret key.",
        confirmText: "Delete Account",
        cancelText: "Keep Account",
        action: { type: "navigate", scope: sKey + "/account/" + a.id, title: a.name },
        altAction: { type: "totp-remove", id: a.id }
      })
    }
    return out
  }

  // Check if query is an "add" command or request
  var lowerQ = q.toLowerCase()
  if (lowerQ === "add" || lowerQ === "new") {
    out.push({
      id: "add-form-trigger",
      title: "Add New TOTP Account",
      subtitle: "Open form to configure secret key, algorithm, digits",
      icon: "󰐿",
      tint: COLOR,
      section: "Add Account",
      verb: "Open Form",
      tier: "answer",
      score: 100,
      action: { type: "totp-open-add" }
    })
    return out
  }

  if (lowerQ.indexOf("add ") === 0) {
    var addParsed = parseAdd(q)
    if (addParsed) {
      if (addParsed.incomplete) {
        out.push({
          id: "add-hint",
          title: "Add TOTP Account",
          subtitle: addParsed.error || "Type totp add <secret> <name> or press Enter to open form",
          icon: "󰐿",
          tint: COLOR,
          section: "Add Account",
          verb: "Open Form",
          tier: "answer",
          score: 100,
          action: { type: "totp-open-add" }
        })
      } else if (addParsed.account) {
        var previewCode = generateCode(addParsed.account, now)
        out.push({
          id: "add-save",
          title: "Save Account: " + addParsed.account.name,
          subtitle: (addParsed.account.issuer ? addParsed.account.issuer + " · " : "") +
                    "Current OTP: " + formatCode(previewCode.value) + " · Enter to save",
          icon: "󰄲",
          tint: COLOR,
          section: "Add Account",
          verb: "Save account",
          tier: "answer",
          score: 100,
          accessory: formatCode(previewCode.value) + "  ·  " + previewCode.remainingSeconds + "s",
          action: { type: "totp-add", account: addParsed.account }
        })
      }
      return out
    }
  }

  // Check if query is a direct Quick OTP secret or otpauth URI
  var isQuickOtp = lowerQ.indexOf("quick ") === 0
  var rawCandidate = isQuickOtp ? q.slice(6).trim() : q
  if (rawCandidate) {
    try {
      var candidateAcc = null
      if (rawCandidate.toLowerCase().indexOf("otpauth:") === 0) {
        candidateAcc = parseInput(rawCandidate)
        if (candidateAcc) {
          var previewCode = generateCode(candidateAcc, now)
          out.push({
            id: "save-from-uri",
            title: "Save Account: " + candidateAcc.name,
            subtitle: (candidateAcc.issuer ? candidateAcc.issuer + " · " : "") +
                      "From otpauth URI · Current OTP: " + formatCode(previewCode.value) + " · Enter to save",
            icon: "󰄲",
            tint: COLOR,
            section: "Save Account",
            verb: "Save Account",
            altVerb: "Copy OTP",
            tier: "answer",
            score: 100,
            accessory: formatCode(previewCode.value) + "  ·  " + previewCode.remainingSeconds + "s",
            action: { type: "totp-add", account: candidateAcc },
            altAction: { type: "copy", text: previewCode.value }
          })
          if (!scoped && !viaCommand) return out
        }
      } else if (!isQuickOtp && rawCandidate.length >= 16 && /^[2-7A-Za-z=\s-]+$/.test(rawCandidate)) {
        var norm = normalizeSecret(rawCandidate)
        decodeBase32(norm)
        candidateAcc = { name: "Quick OTP", issuer: "", secret: norm, digits: 6, period: 30, algorithm: "SHA1" }
      } else if (isQuickOtp) {
        var norm = normalizeSecret(rawCandidate)
        decodeBase32(norm)
        candidateAcc = { name: "Quick OTP", issuer: "", secret: norm, digits: 6, period: 30, algorithm: "SHA1" }
      }
      if (candidateAcc && candidateAcc.name === "Quick OTP") {
        out.push(quickOtpRow(candidateAcc, now, settings))
        if (!scoped && !viaCommand) return out
      }
    } catch (_) { }
  }

  // In scoped mode or viaCommand: filter accounts
  if (scStr || viaCommand) {
    var searchTerms = q.toLowerCase().split(/\s+/).filter(Boolean)
    var matchedCount = 0
    for (var i = 0; i < list.length; i++) {
      var acc = list[i]
      var match = true
      if (searchTerms.length > 0) {
        var hay = (acc.name + " " + (acc.issuer || "")).toLowerCase()
        for (var t = 0; t < searchTerms.length; t++) {
          if (hay.indexOf(searchTerms[t]) < 0) {
            match = false
            break
          }
        }
      }
      if (match) {
        matchedCount++
        out.push(accountRow(acc, now, settings, q ? undefined : 1, sKey, i))
      }
    }

    if (!matchedCount && !out.length) {
      out.push({
        id: "empty",
        title: list.length ? "No matching accounts" : "No TOTP accounts saved",
        subtitle: list.length ? "Try another search query or press Enter to add" : "Press Enter to add your first account",
        icon: ICON,
        tint: COLOR,
        section: "Accounts",
        verb: "Add Account",
        tier: "item",
        score: q ? undefined : 1,
        action: { type: "totp-open-add" }
      })
    }

    // Action row for adding an account (only when empty query, or if query matches 'add')
    if (!q || "add new create account".indexOf(q.toLowerCase()) >= 0) {
      out.push({
        id: "add-account-action",
        title: "Add New Account",
        subtitle: "Open form to configure secret key or scan URI",
        icon: "󰐿",
        tint: COLOR,
        section: "Actions",
        verb: "Add Account",
        tier: "item",
        order: 900,
        score: q ? undefined : 1,
        keywords: "add new create account",
        action: { type: "totp-open-add" }
      })
    }

    // Navigation and management rows (only when empty query, or if query matches 'manage' or 'backup')
    if (!q || "manage backup export import accounts".indexOf(q.toLowerCase()) >= 0) {
      out.push({
        id: "manage-screen",
        title: "Manage All Accounts & Backups",
        subtitle: "View secret keys, export encrypted backup, or import accounts",
        icon: "󰒓",
        section: "Actions",
        verb: "Manage",
        tier: "item",
        order: 901,
        score: q ? undefined : 1,
        keywords: "manage backup export import accounts",
        action: { type: "navigate", scope: sKey + "/manage", title: "Manage TOTP" }
      })
    }
    return out
  }

  // Unscoped mode (at root palette, without 'totp' prefix)
  if (!q) {
    out.push(navRow(list, 6, sKey))
  } else {
    // Navigation row for root palette matching ("totp", "2fa", "otp", "auth", etc.)
    // Score undefined allows Keystroke's built-in Match.match to score it dynamically.
    out.push(navRow(list, undefined, sKey))

    // Only search individual accounts at root if enabled in settings (default: false)
    if (settings && settings.searchInRoot === true) {
      for (var i = 0; i < list.length; i++) {
        out.push(accountRow(list[i], now, settings, undefined, sKey, i))
      }
    }
  }

  return out
}
