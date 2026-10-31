import os,json,subprocess,socket,time
from pathlib import Path
root=Path('/home/o/ITLR--RAG');out=Path('/tmp/itlr-blockers');old=Path('/tmp/itlr-release')
for port in (15432,18030,18080,18435):
 with socket.socket() as s:s.settimeout(.2);assert s.connect_ex(('127.0.0.1',port))!=0,f'Port{port} occupied; stop before touching existing services'
env=dict(os.environ,LD_LIBRARY_PATH=str(old/'pg-root/usr/lib/x86_64-linux-gnu'))
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):env.pop(key,None)
r=subprocess.run([str(old/'pg-root/usr/lib/postgresql/18/bin/pg_ctl'),'-D',str(old/'pg-data'),'-l',str(out/'cancel-pg.log'),'-w','start'],env=env,text=True,capture_output=True)
(out/'cancel-pg-start.log').write_text(r.stdout+r.stderr);assert r.returncode==0,'Isolated PostgreSQL start failed'
pids={};commands={
 'proxy':([str(root/'.venv/bin/python'),str(out/'cancellation_proxy.py')],str(root),env),
 'api':([str(root/'.venv/bin/python'),'-m','uvicorn','itlr.api.server:app','--host','127.0.0.1','--port','18080','--workers','1','--no-proxy-headers'],str(root),{**env,'ITLR_ARTIFACTS_DIR':'/tmp/itlr-system-audit/staging','ITLR_REQUIRE_ARTIFACT_MANIFEST':'1','HF_HOME':str(root/'var/hf'),'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','USE_OLLAMA':'1','OLLAMA_MODEL':'qwen2.5:3b','OLLAMA_BASE_URL':'http://127.0.0.1:18435','OLLAMA_TIMEOUT':'45','DISABLE_RERANKER':'1','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'1'}),
}
web_env=json.loads((old/'private-env.json').read_text());web_env.update(RECOMMENDER_URL='http://127.0.0.1:18080',PORT='18030')
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):web_env.pop(key,None)
commands['web']=(['node','dist/server.js'],str(root/'web'),web_env)
for name,(args,cwd,local_env) in commands.items():
 with (out/f'cancel-{name}.log').open('w') as log:
  p=subprocess.Popen(args,cwd=cwd,env=local_env,stdout=log,stderr=log,start_new_session=True)
 pids[name]=p.pid
 if name=='proxy':time.sleep(.2)
(out/'cancel-service-pids.json').write_text(json.dumps(pids));print('Started dedicated PostgreSQL/proxy/API/Web; no credentials printed.')
