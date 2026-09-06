#!/usr/bin/env python3
"""Opt-in live quick-question latency check using the production permission policy."""
import argparse,json,pathlib,subprocess,time,statistics,re
from benchmark import Server
ROOT=pathlib.Path(__file__).resolve().parents[2]
PROMPTS=[
 'Why does Bluetooth sometimes interfere with Wi-Fi? Answer in two sentences.',
 'What is the difference between RAM and disk storage? Two sentences.',
 'Translate into Italian: I will arrive ten minutes late.',
 'Explain DNS in one short paragraph.',
 'What is 17 percent of 240? Give only the result.',
 'Give me a clearer version: This meeting could have been an email.',
 'What does a Linux symlink do? Two sentences.',
 'Why is the sky blue? Two sentences.',
 'Give three concise names for a keyboard launcher.',
 'Convert 3.5 kilometers to miles, approximately.',
 'Explain latency versus throughput in two sentences.',
 'Make this polite: Send me the report now.',
 'What is a prime number? One sentence and an example.',
 'Explain the difference between weather and climate briefly.',
 'Write a two-line reminder to take a break and drink water.'
]
def main():
 a=argparse.ArgumentParser();a.add_argument('--output',type=pathlib.Path,required=True);args=a.parse_args()
 args.output.parent.mkdir(parents=True,exist_ok=True)
 code=(ROOT/'codex/Policy.js').read_text().replace('.pragma library','')
 rows=[];begin=time.perf_counter();s=Server(args.output.with_suffix('.stderr.log').open('w'))
 try:
  s.call('initialize',{'clientInfo':{'name':'keystroke_questions_benchmark','version':'0.2'},'capabilities':{'experimentalApi':True}});s.send({'method':'initialized'})
  config=s.call('config/read',{'includeLayers':False})['config']
  policy=json.loads(subprocess.check_output(['node','-e',code+'\nconsole.log(JSON.stringify(start(process.argv[1],{},JSON.parse(process.argv[2]))))',str(pathlib.Path.home()),json.dumps(config)]))
  startup=round((time.perf_counter()-begin)*1000)
  for index,prompt in enumerate(PROMPTS):
   for tier in (['fast','default'] if index%2==0 else ['default','fast']):
    p=dict(policy);p['ephemeral']=True;p['serviceTier']=tier
    t0=time.perf_counter();t=s.call('thread/start',p);ident=t['thread']['id'];t1=time.perf_counter()
    s.call('turn/start',{'threadId':ident,'input':[{'type':'text','text':prompt}],'environments':[],'effort':'low','serviceTier':tier})
    first=sentence=None;out='';tools=[];usage=None;deadline=time.perf_counter()+90
    while True:
     stamp,e=s.receive(deadline);m=e.get('method');v=e.get('params',{})
     if v.get('threadId') not in (None,ident):continue
     if m=='item/agentMessage/delta':
      first=first or stamp;out+=v.get('delta','')
      if sentence is None and re.search(r'[.!?](?:\s|$)',out):sentence=stamp
     if m=='item/completed':
      item=v.get('item',{})
      if item.get('type')=='agentMessage':out=item.get('text',out)
      elif item.get('type') not in ('userMessage','reasoning'):tools.append(item.get('type'))
     if m=='thread/tokenUsage/updated':usage=v.get('tokenUsage',{}).get('last')
     if m=='turn/completed':break
    end=time.perf_counter()
    row={'prompt':prompt,'tier':tier,'thread_ms':round((t1-t0)*1000),'ttft_ms':round((first-t1)*1000) if first else None,'sentence_ms':round((sentence-t1)*1000) if sentence else None,'complete_ms':round((end-t1)*1000),'status':v['turn']['status'],'output':out,'tools':tools,'usage':usage}
    rows.append(row);args.output.write_text(json.dumps({'startup_ms':startup,'rows':rows},indent=2)+'\n');print(len(rows),tier,row['ttft_ms'],row['status'],flush=True)
    if tools:raise RuntimeError('Unexpected tools in static question benchmark')
  rss={}
  for line in pathlib.Path(f'/proc/{s.proc.pid}/smaps_rollup').read_text().splitlines():
   if line.startswith(('Pss:','Private_Clean:','Private_Dirty:','Rss:')):rss[line.split(':')[0]]=int(line.split()[1])
  args.output.write_text(json.dumps({'startup_ms':startup,'process_memory_kib':rss,'rows':rows},indent=2)+'\n')
 finally:s.close()
if __name__=='__main__':main()
