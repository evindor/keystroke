#!/usr/bin/env python3
"""Benchmark a resident Codex app-server using its managed ChatGPT sign-in."""
import argparse, json, queue, subprocess, tempfile, threading, time
from collections import deque
from pathlib import Path

class Server:
    def __init__(self, log):
        self.log=log
        self.proc=subprocess.Popen(['codex','app-server','--stdio','-c','features.fast_mode=true'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,bufsize=1)
        self.queue=queue.Queue(); self.pending=deque(); self.next_id=0
        def read():
            for line in self.proc.stdout:
                try: self.queue.put((time.perf_counter(),json.loads(line)))
                except ValueError: pass
            self.queue.put((time.perf_counter(),None))
        threading.Thread(target=read,daemon=True).start()
    def send(self, value):
        self.proc.stdin.write(json.dumps(value)+'\n');self.proc.stdin.flush()
    def receive(self, deadline):
        try: stamp,value=self.pending.popleft() if self.pending else self.queue.get(timeout=max(.01,deadline-time.perf_counter()))
        except queue.Empty: raise TimeoutError('Codex app-server deadline exceeded')
        if value is None: raise RuntimeError('Codex app-server exited')
        # Never allow a benchmark to approve a tool action.
        if 'method' in value and 'id' in value:
            self.send({'id':value['id'],'error':{'code':-32601,'message':'Benchmark does not execute tools'}})
        return stamp,value
    def call(self, method, params, timeout=60):
        self.next_id+=1; ident=self.next_id
        self.send({'id':ident,'method':method,'params':params})
        deadline=time.perf_counter()+timeout
        deferred=[]
        try:
            while True:
                stamp,value=self.receive(deadline)
                if value.get('id')==ident and 'method' not in value:
                    if 'error' in value: raise RuntimeError(json.dumps(value['error']))
                    return value['result']
                if 'id' not in value:
                    deferred.append((stamp,value))
        finally:
            # Streaming notifications can precede the RPC response. Preserve
            # their original timestamps so TTFT and tool events remain accurate.
            self.pending.extendleft(reversed(deferred))
    def close(self):
        self.proc.terminate()
        try: self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired: self.proc.kill();self.proc.wait()

SCHEMA={'type':'object','properties':{
    'route':{'type':'string','enum':['browser','terminal','clipboard','agent','none']},
    'summary':{'type':'string'}},'required':['route','summary'],'additionalProperties':False}
INSTRUCTIONS=('Classify the supplied spoken request. Return only the requested JSON. '
    'Use browser for opening a browser, terminal for opening a terminal, clipboard for copying dictation, '
    'agent for requests that need an agent to inspect or modify the computer, and none if unclear. '
    'Keep summary under eight words. Do not use tools, read files, or perform the request.')
CASES=[('Open my browser please.','browser'),
       ('Make my window corners more rounded.','agent'),
       ('Copy what I just dictated to the clipboard.','clipboard')]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--tiers',nargs='+',default=['fast','default'])
    parser.add_argument('--repeats',type=int,default=1)
    args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    results=[]
    with tempfile.TemporaryDirectory(prefix='keystroke-cloud-') as work, args.output.with_suffix('.stderr.log').open('w') as log:
        startup=time.perf_counter();server=Server(log)
        try:
            server.call('initialize',{'clientInfo':{'name':'keystroke_voice_benchmark','version':'0.1'},
                                      'capabilities':{'experimentalApi':True}})
            server.send({'method':'initialized'})
            models=server.call('model/list',{})
            luna=next((m for m in models.get('data',[]) if m.get('id')=='gpt-5.6-luna' or m.get('model')=='gpt-5.6-luna'),None)
            if not luna: raise RuntimeError('GPT-5.6 Luna is unavailable through this Codex account')
            print(json.dumps({'model':luna.get('id'), 'startup_ms':round((time.perf_counter()-startup)*1000,2)}),flush=True)
            for tier in args.tiers:
                for repeat in range(args.repeats):
                    for phrase,expected in CASES:
                        begin=time.perf_counter()
                        thread=server.call('thread/start',{'cwd':work,'model':'gpt-5.6-luna',
                            'serviceTier':tier,'ephemeral':True,'sandbox':'read-only','approvalPolicy':'never',
                            'baseInstructions':INSTRUCTIONS,
                            'config':{'model_reasoning_effort':'low','web_search':'disabled',
                                      'features.shell_tool':False}})
                        ident=thread['thread']['id'];ready=time.perf_counter()
                        server.call('turn/start',{'threadId':ident,'input':[{'type':'text','text':phrase}],
                            'model':'gpt-5.6-luna','serviceTier':tier,'effort':'low','outputSchema':SCHEMA})
                        first=None;output='';tool=False;status=None;usage=None;error=None
                        deadline=time.perf_counter()+90
                        while True:
                            stamp,event=server.receive(deadline)
                            method=event.get('method','');params=event.get('params',{})
                            if params.get('threadId') not in (None,ident):continue
                            if method=='item/agentMessage/delta':
                                if first is None:first=stamp
                                output+=params.get('delta','')
                            if method=='item/completed':
                                item=params.get('item',{})
                                if item.get('type')=='agentMessage':output=item.get('text',output)
                                elif item.get('type') in ('commandExecution','fileChange','mcpToolCall','dynamicToolCall'):tool=True
                            if method=='thread/tokenUsage/updated':usage=params.get('tokenUsage')
                            if method=='turn/completed':
                                status=params.get('turn',{}).get('status');error=params.get('turn',{}).get('error');break
                        end=time.perf_counter()
                        try:parsed=json.loads(output)
                        except ValueError:parsed=None
                        row={'model':'gpt-5.6-luna','requested_tier':tier,
                             'thread_tier':thread.get('serviceTier'), 'effort':'low','phrase':phrase,'repeat':repeat,
                             'thread_setup_ms':round((ready-begin)*1000,2),
                             'ttft_ms':None if first is None else round((first-ready)*1000,2),
                             'turn_ms':round((end-ready)*1000,2),'total_ms':round((end-begin)*1000,2),
                             'status':status,'error':error,'output':parsed or output,'tool_observed':tool,
                             'correct':isinstance(parsed,dict) and parsed.get('route')==expected,
                             'usage':usage}
                        results.append(row);args.output.write_text(json.dumps(results,indent=2)+'\n')
                        print(json.dumps(row),flush=True)
                        if tool:raise RuntimeError('Unexpected tool activity; benchmark stopped')
        finally:server.close()

if __name__=='__main__':main()
