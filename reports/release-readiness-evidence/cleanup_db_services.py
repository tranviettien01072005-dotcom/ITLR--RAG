import json,os,signal,socket,subprocess,time
from pathlib import Path
b=Path('/tmp/itlr-release');pids=json.loads((b/'service-pids.json').read_text())
for name,pid in pids.items():
    try:
        command=Path(f'/proc/{pid}/cmdline').read_bytes()
        expected=b'upstream_fixture.cjs' if name=='fixture' else b'dist/server.js'
        assert expected in command,(name,'PID no longer matches service')
        os.killpg(pid,signal.SIGTERM)
    except FileNotFoundError:pass
env=dict(os.environ,LD_LIBRARY_PATH=str(b/'pg-root/usr/lib/x86_64-linux-gnu'))
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):env.pop(key,None)
r=subprocess.run([str(b/'pg-root/usr/lib/postgresql/18/bin/pg_ctl'),'-D',str(b/'pg-data'),'-m','fast','-w','stop'],env=env,text=True,capture_output=True)
(b/'pg-shutdown.log').write_text(r.stdout+r.stderr)
assert r.returncode==0,'PostgreSQL stop failed'
ports={}
for port in (18030,18031,15432):
    for _ in range(50):
        with socket.socket() as s:
            s.settimeout(.2);closed=s.connect_ex(('127.0.0.1',port))!=0
        if closed:break
        time.sleep(.1)
    ports[str(port)]={'listening':not closed}
    assert closed,f'Own port {port} still listening'
(b/'db-cleanup-result.json').write_text(json.dumps({'ownServicesStopped':True,'ports':ports,'dataPreserved':True,'otherServicesUntouched':True},indent=2))
print('PASS own Web18030, upstreamfixture18031 and PostgreSQL15432 stopped; staging data preserved.')
