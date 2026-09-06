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
page = Page()
source = (root/'index.html').read_text()
page.feed(source)
for ref in page.refs:
    url = urlsplit(ref)
    if url.scheme or url.netloc: continue
    if url.path and not (root/url.path).is_file(): errors.append('Missing asset: '+url.path)
    if not url.path and url.fragment and url.fragment not in page.ids: errors.append('Missing anchor: '+url.fragment)
for file in root.rglob('*'):
    if file.is_symlink(): errors.append('Symlink in public source: '+str(file))
    if file.is_file() and file.suffix in ('.html','.css','.js','.svg'):
        content = file.read_text()
        if re.search(r'/home/|/tmp/|sk-[a-zA-Z0-9]{20}|ghp_[a-zA-Z0-9]+|BEGIN .*PRIVATE KEY',content): errors.append('Private-looking value: '+str(file))
for image in (root/'assets/screenshots').glob('*.png'):
    content = image.read_bytes()
    assert content[:8] == b'\x89PNG\r\n\x1a\n'
    width,height = struct.unpack('>II',content[16:24])
    if (width,height) != (2560,2160): errors.append('Unexpected screenshot dimensions: '+image.name)
if not (root/'assets/social-card.png').is_file(): errors.append('Missing social card')
if errors: raise SystemExit('\n'.join(errors))
print(f'PASS: {len(page.ids)} unique ids, {len(page.refs)} asset/link references, {len(list((root/"assets/screenshots").glob("*.png")))} screenshots, no external resources or private paths')
