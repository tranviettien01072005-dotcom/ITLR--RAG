import os,sys,json,time,subprocess,urllib.request,urllib.error,concurrent.futures,resource
from pathlib import Path
root=Path('/home/o/ITLR--RAG');out=Path('/tmp/itlr-release');sys.path.insert(0,str(root))
for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(k,None)
os.environ.update(ITLR_ARTIFACTS_DIR='/tmp/itlr-system-audit/staging',HF_HOME=str(root/'var/hf'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='1',OLLAMA_MODEL='qwen2.5:3b',OLLAMA_BASE_URL='http://127.0.0.1:11434',OLLAMA_TIMEOUT='45',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',ITLR_REQUIRE_ARTIFACT_MANIFEST='1')
log=(out/'runtime-server.log').open('w');p=subprocess.Popen([sys.executable,'-m','uvicorn','itlr.api.server:app','--host','127.0.0.1','--port','18080','--workers','1','--no-proxy-headers'],cwd=root,env=os.environ.copy(),stdout=log,stderr=log)
results=[]
def call(path,body=None,stream=False,cancel=False):
 start=time.perf_counter();req=urllib.request.Request('http://127.0.0.1:18080'+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 try:r=urllib.request.urlopen(req,timeout=100)
 except urllib.error.HTTPError as e:r=e
 with r:
  if not stream:return {'path':path,'seconds':time.perf_counter()-start,'status':r.status,'body':json.loads(r.read())}
  events=[];first=None
  for line in r:
   if not line.startswith(b'data: '):continue
   event=json.loads(line[6:]);events.append(event)
   if event.get('type')=='text' and first is None:first=time.perf_counter()-start
   if cancel and event.get('type')=='text':break
  return {'path':path,'seconds':time.perf_counter()-start,'status':r.status,'first_token_s':first,'events':events,'client_cancelled':cancel}
def save():
 (out/'runtime.json').write_text(json.dumps({'model':'qwen2.5:3b','ollama_budget_s':45,'actual_inference':True,'human_faithfulness':None,'checks':results},ensure_ascii=False,indent=2))
try:
 for _ in range(200):
  if p.poll() is not None:raise RuntimeError('API exited')
  try:
   h=call('/health')
   if h['status']==200:break
  except OSError:pass
  time.sleep(.2)
 else:raise RuntimeError('API not ready')
 results.append(h);save()
 cases=[json.loads(x) for x in (out/'blind_cases.jsonl').read_text().splitlines()]
 for c in [cases[0],cases[6],cases[9],cases[12],cases[-1]]:
  r=call('/api/chat/stream',{'message':c['query'],'history':[]},True);r['case_id']=c['id'];r['query']=c['query'];results.append(r);save();print(c['id'],r['seconds'],[e.get('generation_mode') for e in r['events'] if e['type']=='final'],flush=True)
 # Real HTTP disconnect after a provider delta; observe /api/ps after rather than assuming upstream cleanup.
 r=call('/api/chat/stream',{'message':cases[0]['query'],'history':[]},True,True);results.append(r);save()
 # Concurrent non-stream API requests use actual local model at the normal application contract.
 with concurrent.futures.ThreadPoolExecutor(2) as executor:
  batch=list(executor.map(lambda c:call('/api/chat',{'message':c['query'],'history':[]}),[cases[1],cases[7]]))
 results.append({'concurrent_requests':2,'results':batch});save()
 # Context stress reaches the same provider trimming path; HTTP contract remains bounded.
 r=call('/api/chat',{'message':cases[0]['query'],'history':[{'role':'user' if i%2==0 else 'assistant','content':'Bối cảnh học Python. '*170} for i in range(16)]});r['context_stress']=True;results.append(r);save()
 print('runtime complete',flush=True)
finally:
 p.terminate()
 try:p.wait(timeout=20)
 except subprocess.TimeoutExpired:p.kill();p.wait()
 log.close()
