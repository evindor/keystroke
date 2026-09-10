#!/usr/bin/env python3
"""Dependency-free publish preflight for this static GitHub Pages site."""
from html.parser import HTMLParser
from pathlib import Path
import re
import struct
from urllib.parse import urlsplit

root = Path(__file__).resolve().parent
errors = []
class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.refs = []
        self.images = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            if a['id'] in self.ids: errors.append('Duplicate id: '+a['id'])
            self.ids.add(a['id'])
        for key in ('src','href'):
            if key in a: self.refs.append(a[key])
        if tag == 'img':
            self.images.append(a.get('src',''))
            if not a.get('alt') and a.get('id') != 'lightbox-image': errors.append('Missing image alt')
            if a.get('src') and not all(k in a for k in ('width','height')): errors.append('Missing image dimensions')
        if 'data-image' in a: self.refs.append('assets/screenshots/'+a['data-image']+'.png')
        if tag in ('script','img','link'):
            resource = a.get('src') or (a.get('href') if a.get('rel') == 'stylesheet' else '')
            if resource and urlsplit(resource).scheme: errors.append('Third-party resource: '+resource)
pages = {}
for html in sorted(root.rglob('*.html')):
    page = Page()
    page.feed(html.read_text())
    pages[html] = page
for html, page in pages.items():
    for ref in page.refs:
        url = urlsplit(ref)
        if url.scheme or url.netloc: continue
        if ref.startswith('assets/screenshots/'): target = root/ref              # data-image names resolve against the site root
        else: target = (html.parent/url.path) if url.path else html
        if target.is_dir(): target = target/'index.html'                          # "guide/" and "../" are pages too
        if url.path and not target.is_file(): errors.append(f'Missing asset in {html.relative_to(root)}: {url.path}')
        if url.fragment:
            ids = pages[target.resolve()].ids if target.resolve() in pages else page.ids
            if url.fragment not in ids: errors.append(f'Missing anchor in {html.relative_to(root)}: {ref}')
for file in root.rglob('*'):
    if file.is_symlink(): errors.append('Symlink in public source: '+str(file))
    if file.is_file() and file.suffix in ('.html','.css','.js','.svg'):
        content = file.read_text()
        if re.search(r'/home/|/tmp/|sk-[a-zA-Z0-9]{20}|ghp_[a-zA-Z0-9]+|BEGIN .*PRIVATE KEY',content): errors.append('Private-looking value: '+str(file))
for image in (root/'assets/screenshots').glob('*.png'):
    content = image.read_bytes()
    assert content[:8] == b'\x89PNG\r\n\x1a\n'
    width,height = struct.unpack('>II',content[16:24])
    if image.name.startswith('bar-'):
        if height < 64 or width < 4 * height: errors.append('Unexpected bar strip dimensions: '+image.name)
    elif (width,height) != (2560,2160): errors.append('Unexpected screenshot dimensions: '+image.name)
if not (root/'assets/social-card.png').is_file(): errors.append('Missing social card')
if errors: raise SystemExit('\n'.join(errors))
print(f'PASS: {len(pages)} pages, {sum(len(p.ids) for p in pages.values())} unique ids, {sum(len(p.refs) for p in pages.values())} asset/link references, {len(list((root/"assets/screenshots").glob("*.png")))} screenshots, no external resources or private paths')
