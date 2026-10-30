import json,os,subprocess
from pathlib import Path
base=Path('/tmp/itlr-release')
env=json.loads((base/'private-env.json').read_text())
pids={}
for name,args,cwd in [
 ('fixture',['node',str(base/'upstream_fixture.cjs')],str(base)),
 ('web',['/home/o/ITLR--RAG/web/node_modules/.bin/tsx','src/server.ts'],'/home/o/ITLR--RAG/web')]:
 with (base/(name+'.log')).open('w') as log:
  p=subprocess.Popen(args,cwd=cwd,env=env,stdout=log,stderr=log,start_new_session=True)
  pids[name]=p.pid
(base/'service-pids.json').write_text(json.dumps(pids))
print('Started private fixture and web services; PID file written.')
