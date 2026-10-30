import os,sys,time,json,urllib.request,concurrent.futures
from pathlib import Path
for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(k,None)
rows=[]
for streaming in (False,True):
 start=time.perf_counter();payload={'model':'qwen2.5:3b','messages':[{'role':'user','content':'Reply only OK.'}],'stream':streaming,'options':{'num_predict':64,'temperature':.3}}
 try:
  req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=120) as r:
   if streaming:
    events=[json.loads(line) for line in r if line.strip()];result={'events':events}
   else:result=json.load(r)
  rows.append({'stream':streaming,'seconds':time.perf_counter()-start,'result':result})
 except Exception as e:rows.append({'stream':streaming,'seconds':time.perf_counter()-start,'error':str(e)})
 Path('/tmp/itlr-release/direct-generation.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 print(rows[-1],flush=True)
