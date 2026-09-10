# Keystroke website

Static HTML, CSS and JavaScript, deployed to <https://evindor.github.io/keystroke/>.
No package installation, generated bundle, remote fonts, analytics or server.
Two pages: `index.html` (the showcase) and `guide/index.html` (the usage guide,
every feature with a screenshot and one thing to try; Keystroke's **Learn
Keystroke** row opens it). They share `style.css` and `script.js`.

Preview: `python3 -m http.server 8765 --directory site` from the repository root.
Preflight: `python3 site/check.py` and `node --check site/script.js`.

`.github/workflows/pages.yml` publishes on changes to `site/` on `main`, or a
manual workflow dispatch. It uploads only index.html, style.css, script.js,
guide/ and assets. Python checks, these notes, and capture tooling are not deployed.
The official Pages actions are pinned to exact commits.

Screenshots are the real QML interface with controlled sample content, rendered
offscreen by `../tools/showcase/offscreen.py` (see `../tools/showcase/README.md`). The app's
rendering and theme are preserved. Conversations, file paths, application lists,
clipboard and voice state are demo fixtures, not access to personal user data.

The separate social images are composed by `../tools/showcase/social.html` from
those screenshots. The only social image shipped on the site is social-card.png.
