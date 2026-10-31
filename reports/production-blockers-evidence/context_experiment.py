import os,json,time,asyncio,uuid
from pathlib import Path
for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(k,None)
import httpx
out=Path('/tmp/itlr-blockers');prepared=json.loads((out/'dev-context-prepared.json').read_text());base=prepared['system_base'];sources=prepared['sources'];results=[]
compact=[]
for source in sources:
 s=dict(source);text=s['excerpt'];positions=[text.find(key) for key in ('__enter__()','__exit__()')]
 if min(positions)>=0:
  lo=max(0,min(positions)-90);hi=min(len(text),max(positions)+130);window=text[lo:hi]
 else:window=text[:220]
 assert window in text
 s['excerpt']=window;compact.append(s)
assert all(any(key in s['excerpt'] for s in compact) for key in ('__enter__()','__exit__()'))
assert [(s['item_id'],s['chunk_id'],s['title'],s['url']) for s in compact]==[(s['item_id'],s['chunk_id'],s['title'],s['url']) for s in sources]
compact_ctx='\n\n'.join(f"[item_id:{s['item_id']}] [chunk_id:{s['chunk_id']}] {s['title']}\nURL: {s['url']}\nĐoạn trích ({s['chunk_id']}):\n{s['excerpt']}" for s in compact)
compact_system=base+'\nCite both [item_id:ID] and the exact [chunk_id:ID:INDEX] from the evidence.\n\n## Đoạn trích nguồn\n'+compact_ctx
async def call(label,system,excerpts):
 nonce=uuid.uuid4().hex;system=f'[Diagnostic request ID: {nonce}]\n'+system
 assert base in system
 messages=[{'role':'system','content':system},{'role':'user','content':prepared['message']}]
 start=time.perf_counter();pieces=[];first=None;terminal=None;error=None
 try:
  async with asyncio.timeout(45):
   async with httpx.AsyncClient(trust_env=False,timeout=45) as client:
    async with client.stream('POST','http://127.0.0.1:11434/api/chat',json={'model':'qwen2.5:3b','messages':messages,'stream':True,'keep_alive':'2h','options':{'temperature':.3,'num_predict':2000}}) as r:
     r.raise_for_status()
     async for line in r.aiter_lines():
      if not line.strip():continue
      d=json.loads(line);text=d.get('message',{}).get('content','')
      if text:
       if first is None:first=time.perf_counter()-start
       pieces.append(text)
      if d.get('done'):terminal={k:v for k,v in d.items() if k!='message'}
 except Exception as e:error=type(e).__name__+': '+str(e)
 result={'label':label,'nonce':nonce,'prompt_chars':sum(len(m['content']) for m in messages),'system_prompt':system,'user_message':prepared['message'],'source_windows':excerpts,'max_tokens':2000,'temperature':.3,'wall_s':time.perf_counter()-start,'ttft_s':first,'answer':''.join(pieces),'delta_count':len(pieces),'terminal':terminal,'error':error,'completed':bool(terminal and terminal.get('done_reason')=='stop')}
 if terminal:result['decode_tokens_per_s']=terminal['eval_count']/(terminal['eval_duration']/1e9)
 results.append(result);(out/'context-experiment.json').write_text(json.dumps({'scope':'DEV5061-only diagnostic; nonce forces earlyprefixvariation but cachecounters decideactualreuse; not production configuration','quality_scope':'extractivewindowspreserveDEVmethodfacts,IDs,names,URLs,injectionguard; generalcoverage notverified','budget_s':45,'human_validation':None,'checks':results},ensure_ascii=False,indent=2))
 print(label,result['prompt_chars'],result['wall_s'],result['ttft_s'],result['completed'],result['error'],flush=True)
async def main():
 await call('full-five-sources-nonce',prepared['system_prompt'],sources)
 await call('same-five-IDs-extractive-windows-nonce',compact_system,compact)
asyncio.run(main())
