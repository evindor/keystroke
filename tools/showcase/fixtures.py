"""Public sample data only. Rendered by Keystroke's actual QML components."""
import json
import os
import subprocess
import sys
from pathlib import Path

def row(title, subtitle='', icon='⌘', section='', **kw):
    return dict(title=title, subtitle=subtitle, icon=icon, section=section, verb='Open', **kw)

def fallback(q):
    return [row('Ask Codex here',q,'✳','Continue with',verb_override='Ask'),row('Search Google',q,'G','Continue with'),row('Copy to Clipboard','Enter copies · Ctrl+Enter copies and pastes','󰅌','Continue with')]

apps = [row('Chromium','Web browser','󰊯','Applications'), row('Alacritty','Terminal emulator','󰆍','Applications'),row('Files','File manager','󰉋','Applications'),row('Neovim','Text editor','','Applications'),row('Blender','3D creation suite','󰂫','Applications'),row('OBS Studio','Streaming and recording','󰑋','Applications')]
for app in apps: app['verb']='Launch'
F = {
'root': dict(rows=[row('Applications','Every app, one shortcut away','󰀻','Applications'),row('Clipboard History','Text & images, ready to use again','󰅌','Clipboard'),row('Codex','Quick questions, recent conversations and tasks','✳','Codex'),row('Calculator','Try 128 * 1.24 or 15% of 80','󰃬','Calculator'),row('Convert Anything','Units, temperatures & time zones','󰯍','Converter'),row('Search Files','Find files and folders in your home','󰈞','Files'),row('Extensions','1 of 2 on','󰏗','Extensions')]),
'apps':dict(scope='applications', title='Applications',provider='applications', rows=apps),
'calculator':dict(query='sqrt(144) + 15% of 80',compute='calculator',provider='calculator',providerName='Calculator',rows=fallback('sqrt(144) + 15% of 80')),
'converter':dict(query='72 F to C',compute='converter',provider='converter',providerName='Converter',rows=fallback('72 F to C')),
'units':dict(query='5 miles in km',compute='converter',provider='converter',providerName='Converter',rows=fallback('5 miles in km')),
'colors':dict(query='#ff6644',compute='colors',provider='colors',providerName='Colors'),
'clipboard':dict(scope='clipboard',title='Clipboard',provider='clipboard',rows=[row('Build something worth sharing.','31 characters','󰅌','Clipboard',preview='Build something worth sharing.',previewLabel='CLIPBOARD',previewDetail='Copied locally · never included in global search'),row('https://omarchy.org','19 characters','󰅌','Clipboard'),row('omarchy plugin list','19 characters','󰅌','Clipboard'),row('#ff6644','7 characters','󰅌','Clipboard'),row('Remember to take a break.','25 characters','󰅌','Clipboard')]),
'files':dict(scope='files',title='Files',query='readme',provider='files',rows=[row('README.md','~/Projects/keystroke/README.md','󰈙','Files',hint='Ctrl+Enter terminal'),row('README.md','~/Projects/weekend-app/README.md','󰈙','Files',hint='Ctrl+Enter terminal'),row('README.md','~/Documents/notes/README.md','󰈙','Files',hint='Ctrl+Enter terminal'),row('README.md','~/Projects/dotfiles/README.md','󰈙','Files',hint='Ctrl+Enter terminal')]),
'extensions':dict(scope='extensions',title='Extensions',provider='extensions',rows=[row('Timer','v1.1.0 · On · ships with Keystroke','󱎫','On',accessory='On',badge='extension'),row('Translate','v1.0.0 · Off · ships with Keystroke','󰗊','Available',accessory='Off',badge='extension'),row('Write your own','A folder in ~/.local/share/keystroke/extensions runs at once; a pull request ships it to everyone','','Extend')]),
'extension-detail':dict(scope='extensions/timer',title='Timer',provider='extensions',rows=[row('Enabled','Answering queries','󰨚','Timer',accessory='On'),row('Settings','Keystroke Settings › Timer','󰒓','Timer'),row('Open source','github.com/evindor/keystroke/tree/main/extensions/timer','󰊤','Timer'),row('Timer v1.1.0','Arseniy Zarechnev · Countdown timers with a notification when they end','󱎫','About',badge='extension')]),
 'timer':dict(query='timer 25m focus',provider='timer',providerName='Timer',rows=[row('Start 25m timer','focus','󱎫','Timer',tier='answer',badge='extension',preview='25m',previewLabel='TIMER',previewDetail='focus')]+fallback('timer 25m focus')),
'settings':dict(scope='settings',title='Keystroke Settings',provider='settings',rows=[row('Appearance','Density, accent and result previews','󰏘','Settings'),row('Providers','Enable and configure every capability','󰒓','Settings'),row('Voice','Dictation and hold-to-talk bindings','󰍬','Settings'),row('Open config file','Edit keystroke.json','󰈙','Settings')]),
'fuzzy':dict(query='prefcla',provider='settings',providerName='Settings',rows=[row('Claude','Keystroke Settings › AI & Web Search › Preferred assistant','󰒓','Settings',accessory='Choice')]+fallback('prefcla')),
'voice':dict(query='Open the display settings',voice=True,provider='omarchy',providerName='Omarchy',rows=[row('Displays','Setup › Displays','󰍹','Omarchy'),row('Ask Codex here','Open the display settings','✳','Continue with'),row('Copy to Clipboard','Enter copies · Ctrl+Enter copies and pastes','󰅌','Continue with')]),
'dictation':dict(query='Build something worth sharing.',scope='dictation',title='Dictate to Clipboard',provider='dictation',rows=[row('Copy to Clipboard','Enter copies · Ctrl+Enter copies and pastes','󰅌','Dictation',preview='Build something worth sharing.',previewLabel='DICTATION',previewDetail='Your words, ready to paste')]),
'codex':dict(conversation=[dict(id='demo-user',role='user',text='How do I find the biggest folders in this directory?'),dict(id='demo-answer',role='assistant',text='Run this in your terminal:\n\n```sh\ndu -h --max-depth=1 | sort -hr\n```\n\n`du` measures each folder. `sort -hr` puts the largest first.\n\nUse `ncdu .` for an interactive view you can explore with the arrow keys.')],draft='Can I exclude the .git folder?'),
'omarchy':dict(scope='omarchy/system',title='System',provider='omarchy',rows=[row('Lock','Lock your session','󰌾','System'),row('Suspend','Put your computer to sleep','󰒲','System'),row('Restart','Restart your computer','󰜉','System'),row('Shutdown','Shut down your computer','󰐥','System')]),
'emoji':dict(query=':rocket',provider='emoji',providerName='Emoji',rows=[row('rocket','rocket · space · launch','🚀','Emoji',preview='🚀',previewLabel='EMOJI',emoji=True,tier='answer')]+fallback(':rocket')),
}
query = '10 am in London on 2026-09-06'
helper = Path(__file__).resolve().parents[2]/'helpers/timezone.py'
tz = json.loads(subprocess.check_output([sys.executable,str(helper),query,'Europe/Tallinn'],text=True))
F['timezone'] = dict(query=query,provider='converter',providerName='Converter',rows=[row(tz['result'],tz['detail'],'󰯍','Converter',tier='answer',preview=tz['result'],previewLabel='CONVERSION',previewDetail=tz['detail'])]+fallback(query))
for r in F['clipboard']['rows']:
    r['subtitle'] = str(len(r['title'])) + ' characters'
    r['verb'] = 'Copy'
F['dictation']['rows'][0]['verb'] = 'Copy'
F['timer']['rows'][0]['verb'] = 'Start timer'
F['emoji']['rows'][0]['verb'] = 'Copy emoji'
for fixture in F.values():
    for r in fixture.get('rows',[]):
        if 'verb_override' in r: r['verb']=r.pop('verb_override')
Path(os.environ.get('KEYSTROKE_SHOWCASE_FIXTURES', '/tmp/keystroke-showcase-fixtures.json')).write_text(json.dumps(F,ensure_ascii=False,indent=2))
print(f'{len(F)} public fixtures')
