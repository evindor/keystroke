#!/usr/bin/env python3
"""Isolated Python/XPU prerequisites; never changes system packages or services."""
import hashlib, json, os, subprocess, tarfile, urllib.request, urllib.error
from pathlib import Path

root = Path(os.environ.get('KEYSTROKE_AUDIO_ENV', Path.home()/'.local/share/keystroke/experiments/gemma-audio'))
root.mkdir(parents=True, exist_ok=True)

def fetch(url, path, expected=None):
    if not path.exists():
        with urllib.request.urlopen(url, timeout=60) as response, path.with_suffix('.part').open('wb') as out:
            import shutil
            shutil.copyfileobj(response, out)
        path.with_suffix('.part').replace(path)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if expected and digest != expected:
        raise RuntimeError(f'Checksum mismatch for {path.name}')
    return digest

# Read package hashes from the machine's existing signed-repository database.
checksums={}
with tarfile.open('/var/lib/pacman/sync/extra.db') as db:
    for entry in db:
        if entry.name.endswith('/desc'):
            fields=db.extractfile(entry).read().decode().split('\n\n')
            values={part.split('\n')[0]:part.split('\n')[1:] for part in fields if '\n' in part}
            if '%FILENAME%' in values and '%SHA256SUM%' in values:
                checksums[values['%FILENAME%'][0]]=values['%SHA256SUM%'][0]
manifest=[]
packages=subprocess.check_output(['pacman','-Sp','--print-format','%n\t%l','intel-compute-runtime','level-zero-headers'],text=True).splitlines()
for package_line in packages:
    name,url=package_line.split('\t',1)
    filename=url.rsplit('/',1)[-1]
    package=root/filename
    try:
        sha=fetch(url,package,checksums[filename])
    except urllib.error.HTTPError:
        # Omarchy's curated mirror may require its package-manager client.
        # The Arch archive serves the identical repository-hashed package.
        url='https://archive.archlinux.org/packages/'+name[0]+'/'+name+'/'+filename
        sha=fetch(url,package,checksums[filename])
    destination=root/'driver'
    destination.mkdir(exist_ok=True)
    subtree='usr/include' if name=='level-zero-headers' else 'usr/lib'
    subprocess.run(['tar','--zstd','-xf',str(package),'-C',str(destination),subtree],check=True)
    manifest.append({'url':url,'sha256':sha})

metadata=json.load(urllib.request.urlopen('https://api.github.com/repos/astral-sh/uv/releases/latest',timeout=30))
asset=next(a for a in metadata['assets'] if a['name']=='uv-x86_64-unknown-linux-gnu.tar.gz')
# Versioned filename prevents accidentally retaining a different release.
archive=root/(metadata['tag_name']+'-'+asset['name'])
expected=asset.get('digest','').removeprefix('sha256:') or None
sha=fetch(asset['browser_download_url'],archive,expected)
subprocess.run(['tar','-xzf',str(archive),'-C',str(root)],check=True)
uv=root/'uv-x86_64-unknown-linux-gnu/uv'
if not (root/'venv/bin/python').exists():
    subprocess.run([str(uv),'venv','--python','3.12','--managed-python',str(root/'venv')],check=True)
manifest.append({'url':asset['browser_download_url'],'sha256':sha,'version':metadata['tag_name']})
(root/'bootstrap.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(root)
