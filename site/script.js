var dialog = document.getElementById('lightbox')
var lightboxImage = document.getElementById('lightbox-image')
var lightboxTitle = document.getElementById('lightbox-title')
var previousFocus
var labels = {
  apps: 'Applications', clipboard: 'Clipboard history', files: 'File search', codex: 'Codex inside Keystroke',
  voice: 'Voice control', calculator: 'Calculator', converter: 'Temperature conversion', extensions: 'Extensions',
  colors: 'Colors', timer: 'Timer extension', fuzzy: 'Fuzzy settings search', emoji: 'Emoji', settings: 'Settings',
  dictation: 'Dictate to Clipboard', units: 'Unit conversion', timezone: 'Time zones', 'extension-detail': 'An extension\u2019s page',
  commands: 'Commands explain themselves', translate: 'Translate extension', 'hotkeys-search': 'Hotkeys'
}
document.querySelectorAll('[data-image]').forEach(function (element) {
  element.addEventListener('click', function (event) {
    if (typeof dialog.showModal !== 'function') return
    event.preventDefault()
    previousFocus = element
    var image = element.querySelector('img')
    lightboxImage.src = image.getAttribute('src')   // the page's own path, so the guide in guide/ resolves ../assets
    lightboxImage.alt = image.alt
    lightboxTitle.textContent = element.dataset.label || labels[element.dataset.image] || 'Keystroke'
    dialog.showModal()
    document.body.style.overflow = 'hidden'
  })
})
document.getElementById('close-lightbox').addEventListener('click', function () { dialog.close() })
dialog.addEventListener('click', function (event) {
  var bounds = dialog.getBoundingClientRect()
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close()
})
dialog.addEventListener('close', function () {
  document.body.style.overflow = ''
  if (previousFocus) previousFocus.focus()
})
document.querySelectorAll('[data-copy]').forEach(function (button) {
  button.addEventListener('click', async function () {
    var source = document.getElementById(button.dataset.copy)
    try {
      await navigator.clipboard.writeText(source.textContent)
      button.textContent = 'Copied ✓'
      document.getElementById('copy-status').textContent = 'Install command copied.'
      window.setTimeout(function () { button.textContent = 'Copy command ⧉' }, 2200)
    } catch (error) {
      var selection = window.getSelection()
      var range = document.createRange()
      range.selectNodeContents(source)
      selection.removeAllRanges()
      selection.addRange(range)
      button.textContent = 'Selected — press Ctrl+C'
      document.getElementById('copy-status').textContent = 'Clipboard access unavailable. The command is selected for manual copying.'
    }
  })
})
