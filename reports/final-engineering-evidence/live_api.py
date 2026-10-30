import json,os,sys,time,subprocess,urllib.request,urllib.error
from pathlib import Path
root=Path('/home/o/ITLR--RAG');out=Path('/tmp/itlr-engineering')
for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(k,None)
env={**os.environ,'ITLR_ARTIFACTS_DIR':'/tmp/itlr-system-audit/staging','HF_HOME':str(root/'var/hf'),'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','USE_OLLAMA':'1','OLLAMA_MODEL':'qwen2.5:3b','OLLAMA_BASE_URL':'http://127.0.0.1:11434','OLLAMA_TIMEOUT':'60','DISABLE_RERANKER':'1','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'1','ITLR_REQUIRE_ARTIFACT_MANIFEST':'1'}
log=(out/'live-api-server.log').open('w');p=subprocess.Popen([sys.executable,'-m','uvicorn','itlr.api.server:app','--host','127.0.0.1','--port','18080','--workers','1','--no-proxy-headers'],cwd=root,env=env,stdout=log,stderr=log)
records=[]
def request(path,body=None):
 req=urllib.request.Request('http://127.0.0.1:18080'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 try:r=urllib.request.urlopen(req,timeout=100)
 except urllib.error.HTTPError as e:r=e
 with r:return r.status,r.read().decode()
try:
 for _ in range(100):
  if p.poll() is not None:raise RuntimeError('API exited')
  try:
   status,body=request('/health')
   if status==200:break
  except OSError:pass
  time.sleep(.2)
 else:raise RuntimeError('readiness timeout')
 records.append({'path':'/health','status':status,'body':json.loads(body)})
 for path,body,expected in [('/api/search',{'query':'Which Python module represents filesystem paths as objects?'},200),('/api/personas',None,503),('/admin/reload',{},403)]:
  status,text=request(path,body);assert status==expected,(status,text);records.append({'path':path,'status':status,'body':json.loads(text)})
 for streaming in (False,True):
  path='/api/chat/stream' if streaming else '/api/chat';start=time.perf_counter()
  status,text=request(path,{'message':'HTTP 404 Not Found cho biết điều gì về tài nguyên được yêu cầu?','history':[]});assert status==200
  if streaming:
   events=[json.loads(line[6:]) for line in text.splitlines() if line.startswith('data: ')]
   assert events[-1]['type']=='done'
   final=[e for e in events if e['type']=='final'];assert len(final)==1
   record={'path':path,'status':status,'seconds':time.perf_counter()-start,'event_count':len(events),'types':sorted({e['type'] for e in events}),'final':final[0]}
  else:record={'path':path,'status':status,'seconds':time.perf_counter()-start,'final':json.loads(text)}
  records.append(record);print(path,record['seconds'],record['final'].get('generation_mode'),flush=True)
 (out/'live-api.json').write_text(json.dumps({'ollama_timeout_s':60,'model':'qwen2.5:3b','scope':'isolated real E5 corpus; real Qwen, reranker disabled','checks':records},ensure_ascii=False,indent=2))
finally:
 p.terminate()
 try:p.wait(timeout=20)
 except subprocess.TimeoutExpired:p.kill();p.wait()
 log.close()
