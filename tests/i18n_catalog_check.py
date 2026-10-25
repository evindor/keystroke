#!/usr/bin/env python3
"""Keep English/German catalogs and literal UI calls in sync."""
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]

def catalog(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            assert key not in out, f"duplicate key {key} in {path}"
            out[key] = value
        return out
    return json.loads(path.read_text(), object_pairs_hook=unique)

def placeholders(value):
    return sorted(re.findall(r"%[1-9][0-9]*", value))

english = catalog(root / 'i18n/en.json')
german = catalog(root / 'i18n/de.json')
assert set(english) == set(german), 'catalog key coverage differs'
for key, source in english.items():
    translated = german[key]
    if isinstance(source, str):
        assert isinstance(translated, str) and translated.strip(), key
        assert placeholders(source) == placeholders(translated), key
    else:
        assert isinstance(source, dict) and isinstance(translated, dict), key
        assert 'one' in translated and 'other' in translated, key
        for form in translated.values():
            assert isinstance(form, str) and form.strip(), key
            assert placeholders(source['other']) == placeholders(form), key
for folder in ('providers', 'ui', 'codex', 'core'):
    for path in (root / folder).glob('*'):
        if path.suffix not in ('.qml', '.js'):
            continue
        for literal in re.findall(r'(?:root\.t|translate)\(("(?:[^"\\]|\\.)*")', path.read_text()):
            assert json.loads(literal) in english, (path, literal)
for literal in re.findall(r'root\.t\(("(?:[^"\\]|\\.)*")', (root / 'Keystroke.qml').read_text()):
    assert json.loads(literal) in english, literal
print(f'PASS catalogs: {len(english)} keys, German coverage, placeholders, plural forms and explicit UI calls')

# Older Omarchy must not resolve the optional newer APIs at the entry point.
for path in [root/'Keystroke.qml', *(root/'providers').glob('*.qml'), *(root/'ui').glob('*.qml'), *(root/'codex').glob('*.qml')]:
    source=path.read_text()
    assert 'Commons.Translations' not in source and 'Commons.I18n' not in source and 'Util.readingKey' not in source, path
