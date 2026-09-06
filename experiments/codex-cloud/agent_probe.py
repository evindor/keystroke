#!/usr/bin/env python3
"""Measure first useful read-only agent action; does not modify desktop settings."""
import json, tempfile, time
from pathlib import Path
from benchmark import Server

output=Path('/tmp/keystroke-luna-agent-probe.json')
with tempfile.TemporaryDirectory(prefix='keystroke-agent-probe-') as work, output.with_suffix('.stderr.log').open('w') as log:
    server=Server(log)
    try:
        server.call('initialize',{'clientInfo':{'name':'keystroke_agent_probe','version':'0.1'},'capabilities':{'experimentalApi':True}})
        server.send({'method':'initialized'})
        thread=server.call('thread/start',{'cwd':work,'model':'gpt-5.6-luna','serviceTier':'fast',
            'ephemeral':True,'sandbox':'read-only','approvalPolicy':'never',
            'developerInstructions':'This is a read-only latency probe. Read only /etc/os-release. Do not write files, run network commands, or inspect any other path.',
            'config':{'model_reasoning_effort':'low','web_search':'disabled'}})
        ident=thread['thread']['id'];start=time.perf_counter()
        server.call('turn/start',{'threadId':ident,'input':[{'type':'text','text':'Read /etc/os-release and tell me the operating system name in one sentence.'}],
                                 'effort':'low','serviceTier':'fast'})
        first_text=None;first_action=None;actions=[];answer='';status=None;error=None
        deadline=time.perf_counter()+90
        while True:
            stamp,event=server.receive(deadline);method=event.get('method','');params=event.get('params',{})
            if params.get('threadId') not in (None,ident):continue
            if method=='item/agentMessage/delta':
                if first_text is None:first_text=stamp
            if method=='item/started' and params.get('item',{}).get('type') in ('commandExecution','dynamicToolCall'):
                if first_action is None:first_action=stamp
                actions.append(params['item'].get('command',params['item'].get('tool')))
            if method=='item/completed' and params.get('item',{}).get('type')=='agentMessage':answer=params['item'].get('text','')
            if method=='turn/completed':status=params.get('turn',{}).get('status');error=params.get('turn',{}).get('error');break
        result={'model':'gpt-5.6-luna','requested_tier':'fast','thread_tier':thread.get('serviceTier'),
                'first_text_ms':None if first_text is None else round((first_text-start)*1000,2),
                'first_action_ms':None if first_action is None else round((first_action-start)*1000,2),
                'total_ms':round((time.perf_counter()-start)*1000,2),'actions':actions,'answer':answer,'status':status,'error':error}
        output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:server.close()
