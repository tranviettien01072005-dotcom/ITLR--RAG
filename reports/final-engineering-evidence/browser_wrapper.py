import os,sys,time,subprocess,urllib.request
from pathlib import Path
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(key,None)
env={**os.environ,'JWT_SECRET':'fixture-only-jwt-secret-for-isolated-browser','ADMIN_PASSCODE':'fixture-only-admin-passcode','DATABASE_URL':'postgresql://fixture:fixture-only-password@127.0.0.1:1/itlr_test','APP_ORIGIN':'http://127.0.0.1:18030'}
web_log=Path('/tmp/itlr-engineering/web-runtime.log').open('w')
web_process=subprocess.Popen(['node','-e',"const {app}=require('./dist/app');const {pool}=require('./dist/db/pool');const s=app.listen(18030,'127.0.0.1');process.once('SIGTERM',()=>s.close(()=>pool.end()));"],cwd='/home/o/ITLR--RAG/web',env=env,stdout=web_log,stderr=web_log)
try:
 for _ in range(50):
  try:
   with urllib.request.urlopen('http://127.0.0.1:18030/health',timeout=2):break
  except OSError:time.sleep(.1)
 else:raise RuntimeError('Web readiness failed')
 exec(compile(Path('/tmp/itlr-engineering/browser.py').read_text(),'browser.py','exec'))
finally:
 web_process.terminate()
 try:web_process.wait(timeout=10)
 except subprocess.TimeoutExpired:web_process.kill();web_process.wait()
 web_log.close()
