import os,sys,json,time,asyncio,threading,resource,subprocess
from pathlib import Path
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(key,None)
root=Path('/home/o/ITLR--RAG');out=Path('/tmp/itlr-blockers');sys.path.insert(0,str(root))
os.environ.update(ITLR_ARTIFACTS_DIR='/tmp/itlr-system-audit/staging',HF_HOME=str(root/'var/hf'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='1',OLLAMA_MODEL='qwen2.5:3b',OLLAMA_BASE_URL='http://127.0.0.1:11434',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
import httpx
from itlr.engine import load_engine
from itlr.chatbot.citations import validate_citations
from itlr.chatbot.llm_client import trim_messages
stop=threading.Event();samples=[];previous={}
def monitor():
 while not stop.wait(.25):
  now=time.monotonic();entries=[]
  for path in Path('/proc').iterdir():
   if not path.name.isdigit():continue
   try:
    pid=int(path.name);name=(path/'comm').read_text().strip()
    if pid!=os.getpid() and name not in ('ollama','llama-server'):continue
    stat=(path/'stat').read_text();fields=stat[stat.rfind(')')+2:].split();cpu=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK');prior=previous.get(pid);percent=None if prior is None else 100*(cpu-prior[1])/(now-prior[0]);previous[pid]=(now,cpu)
    rss=int((path/'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')/2**20
    entries.append({'pid':pid,'name':name,'rss_mib':rss,'interval_cpu_pct':percent})
   except (FileNotFoundError,PermissionError,ProcessLookupError):pass
  samples.append({'monotonic_s':now,'processes':entries})
thread=threading.Thread(target=monitor,daemon=True);thread.start()
started=time.perf_counter();engine=load_engine();engine_load_s=time.perf_counter()-started
cases=[json.loads(line) for line in (root/'eval/engineering_queries.jsonl').read_text().splitlines() if json.loads(line).get('split')=='dev' and json.loads(line).get('judgments')]
prepared=[]
for case in cases:
 t=time.perf_counter();kind,p=engine.chatbot._prepare(case['query'],[]);latency=time.perf_counter()-t
 if kind!='generate':continue
 messages=trim_messages([{'role':'system','content':p['sys_prompt']},{'role':'user','content':p['llm_message']}])
 prepared.append({'id':case['id'],'query':case['query'],'retrieval_s':latency,'messages':messages,'prompt_chars':sum(len(m['content']) for m in messages),'sources':engine.chatbot._public_sources(p['sources'])})
short=next(p for p in prepared if p['id']=='dev-vi-5025');long=max(prepared,key=lambda p:p['prompt_chars'])
results=[]
async def infer(label,messages,sources=None,max_tokens=2000):
 start=time.perf_counter();pieces=[];first=None;last=None;terminal=None;error=None
 try:
  async with asyncio.timeout(45):
   async with httpx.AsyncClient(timeout=45,trust_env=False) as client:
    async with client.stream('POST','http://127.0.0.1:11434/api/chat',json={'model':'qwen2.5:3b','messages':messages,'stream':True,'options':{'temperature':.3,'num_predict':max_tokens},'keep_alive':'2h'}) as response:
     response.raise_for_status()
     async for line in response.aiter_lines():
      if not line.strip():continue
      event=json.loads(line);text=event.get('message',{}).get('content','')
      if text:
       now=time.perf_counter();first=first or now-start;last=now-start;pieces.append(text)
      if event.get('done'):terminal={k:v for k,v in event.items() if k!='message'}
 except Exception as exc:error=type(exc).__name__+': '+str(exc)
 answer=''.join(pieces);row={'label':label,'prompt_chars':sum(len(m['content']) for m in messages),'max_tokens':max_tokens,'wall_s':time.perf_counter()-start,'ttft_s':first,'last_delta_s':last,'delta_count':len(pieces),'answer':answer,'terminal':terminal,'error':error,'completed':bool(terminal and terminal.get('done_reason')=='stop'),'citation':validate_citations(answer,sources,require_chunks=True) if sources else None}
 if terminal:
  row['decode_tokens_per_s']=terminal.get('eval_count',0)/(terminal.get('eval_duration',1)/1e9)
  row['unattributed_duration_s']=(terminal.get('total_duration',0)-terminal.get('load_duration',0)-terminal.get('prompt_eval_duration',0)-terminal.get('eval_duration',0))/1e9
 results.append(row);save();print(label,row['wall_s'],row['ttft_s'],row['completed'],row['error'],flush=True)
 return row

def save():
 (out/'profile-local.json').write_text(json.dumps({'model':'qwen2.5:3b','source':'current frozen DEV queries only; no confirmation labels used','budget_s':45,'cold_start':'NOT MEASURED: shared daemon/model not unloaded','host':'shared; no inference-load isolation claim','engine_load_s':engine_load_s,'prepared':[{'id':p['id'],'prompt_chars':p['prompt_chars'],'retrieval_s':p['retrieval_s']} for p in prepared],'checks':results,'resource_samples':samples},ensure_ascii=False,indent=2))
async def main():
 async with httpx.AsyncClient(trust_env=False) as client:
  for endpoint in ('tags','ps'):
   (out/('profile-ollama-'+endpoint+'.json')).write_text(json.dumps((await client.get('http://127.0.0.1:11434/api/'+endpoint)).json(),indent=2))
 await infer('warm-smoke-before',[{'role':'user','content':'Reply only OK.'}],max_tokens=64)
 await infer(short['id']+'-production-prompt',short['messages'],short['sources'])
 await infer(long['id']+'-longest-dev-production-prompt',long['messages'],long['sources'])
 await asyncio.gather(infer('concurrent-1',short['messages'],short['sources']),infer('concurrent-2',long['messages'],long['sources']))
asyncio.run(main());stop.set();thread.join(timeout=2);save()
