import os,signal,subprocess,socket,json,time
from pathlib import Path
base=Path('/tmp/itlr-blockers');old=Path('/tmp/itlr-release');pids=json.loads((base/'cancel-service-pids.json').read_text())
for name,pid in pids.items():
 try:
  command=Path(f'/proc/{pid}/cmdline').read_bytes()
  expected={'proxy':b'cancellation_proxy.py','api':b'uvicorn','web':b'dist/server.js'}[name]
  assert expected in command,f'{name} PID no longer matches; refusing signal'
  os.killpg(pid,signal.SIGTERM)
 except FileNotFoundError:pass
env=dict(os.environ,LD_LIBRARY_PATH=str(old/'pg-root/usr/lib/x86_64-linux-gnu'))
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):env.pop(key,None)
r=subprocess.run([str(old/'pg-root/usr/lib/postgresql/18/bin/pg_ctl'),'-D',str(old/'pg-data'),'-m','fast','-w','stop'],env=env,text=True,capture_output=True)
(base/'cancel-pg-stop.log').write_text(r.stdout+r.stderr);assert r.returncode==0,'Fixture PostgreSQL stop failed'
ports={}
for port in (15432,18030,18080,18435):
 for _ in range(100):
  with socket.socket() as s:s.settimeout(.2);listening=s.connect_ex(('127.0.0.1',port))==0
  if not listening:break
  time.sleep(.1)
 ports[str(port)]=listening
assert not any(ports.values()),ports
(base/'cancel-cleanup.json').write_text(json.dumps({'own_services_stopped':True,'ports_listening':ports,'fixture_data_preserved':True,'no_migration_or_seed':True},indent=2));print('Own temporary services stopped; fixture database and evidence retained.')
