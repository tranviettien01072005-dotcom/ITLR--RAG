"""Real UI cancellation through Express/API and observation proxy to real Ollama."""
import json,subprocess,time,urllib.request,tempfile,os
from pathlib import Path
from websockets.sync.client import connect
base=Path('/tmp/itlr-blockers');old=Path('/tmp/itlr-release')
state=json.loads((old/'private-journey-state.json').read_text())
profile=Path(tempfile.mkdtemp(prefix='chrome-cancel-',dir=base));origin='http://127.0.0.1:18030'
log=(base/'cancel-chrome.log').open('w');chrome=subprocess.Popen(['/opt/google/chrome/chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-port=0',f'--user-data-dir={profile}','--no-first-run','--no-default-browser-check','about:blank'],stdout=log,stderr=log)
sequence=0;responses={};errors=[];cases=[]
def save():
 (base/'browser-cancellation.json').write_text(json.dumps({'scope':'Real Chrome UI -> Express18030 -> API18080 -> observationproxy18435 -> actualOllama11434, E5 real768d staging; private existing fixture database. Proxy closes actual socket, modelinternal cancellation ACK is not directlyobservable.','model':'qwen2.5:3b','ollama_timeout_s':45,'cases':cases,'browser_exceptions':errors},ensure_ascii=False,indent=2))
def counts():
 r=subprocess.run(['node',str(old/'db_query.cjs')],input=json.dumps({'sql':"SELECT role,count(*)::int AS count FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=$1) GROUP BY role ORDER BY role",'params':[state['uid']]}),text=True,capture_output=True,check=True)
 return json.loads(r.stdout)
def proxy_rows():return json.loads((base/'cancellation-proxy.json').read_text())['records']
def cpu_ticks():
 result={}
 for path in Path('/proc').glob('[0-9]*'):
  try:
   if (path/'comm').read_text().strip()!='llama-server':continue
   fields=(path/'stat').read_text().split();result[path.name]=int(fields[13])+int(fields[14])
  except (OSError,ValueError):pass
 return result

def tiny_probe():
 start=time.monotonic();payload={'model':'qwen2.5:3b','stream':False,'messages':[{'role':'user','content':'Reply only OK.'}],'options':{'num_predict':16,'temperature':.3}}
 try:
  req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=10) as r:result=json.load(r)
  return {'elapsed_s':time.monotonic()-start,'done':result.get('done'),'done_reason':result.get('done_reason'),'response':result.get('message',{}).get('content'),'prompt_eval_count':result.get('prompt_eval_count'),'prompt_eval_duration_ns':result.get('prompt_eval_duration'),'eval_count':result.get('eval_count'),'eval_duration_ns':result.get('eval_duration'),'total_duration_ns':result.get('total_duration')}
 except Exception as exc:return {'elapsed_s':time.monotonic()-start,'error_type':type(exc).__name__}
try:
 for _ in range(100):
  if (profile/'DevToolsActivePort').exists():break
  if chrome.poll() is not None:raise RuntimeError('Dedicated Chrome exited')
  time.sleep(.1)
 port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
 req=urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank',method='PUT')
 with urllib.request.urlopen(req) as r:tab=json.load(r)
 with connect(tab['webSocketDebuggerUrl']) as ws:
  def command(method,params=None):
   global sequence
   sequence+=1;current=sequence;ws.send(json.dumps({'id':current,'method':method,'params':params or {}}))
   while current not in responses:
    obj=json.loads(ws.recv(timeout=30))
    if obj.get('method')=='Runtime.exceptionThrown':errors.append(obj['params']['exceptionDetails'].get('text','exception'))
    elif 'id' in obj:responses[obj['id']]=obj
   obj=responses.pop(current)
   if 'error'in obj:raise RuntimeError(obj['error'])
   return obj.get('result',{})
  def evaluate(expression):
   r=command('Runtime.evaluate',{'expression':expression,'returnByValue':True})
   if 'exceptionDetails'in r:raise RuntimeError('Browser expression failed')
   return r['result'].get('value')
  def wait(expression,budget=15):
   until=time.monotonic()+budget
   while time.monotonic()<until:
    if evaluate(expression):return
    time.sleep(.03)
   raise AssertionError('Browser wait timed out: '+expression)
  def navigate(path,selector):
   command('Page.navigate',{'url':origin+path});wait(f'location.pathname==={json.dumps(path.split("?")[0])} && document.readyState==="complete" && !!document.querySelector({json.dumps(selector)})')
   time.sleep(.1)
  def node(selector):
   for _ in range(4):
    try:
     root=command('DOM.getDocument')['root']['nodeId'];target=command('DOM.querySelector',{'nodeId':root,'selector':selector})['nodeId']
     if target:return target
    except RuntimeError:pass
    time.sleep(.1)
   raise RuntimeError('Stable DOM node not found: '+selector)
  def fill(selector,text):
   command('DOM.focus',{'nodeId':node(selector)});command('Input.insertText',{'text':text})
  def click(selector):
   command('DOM.scrollIntoViewIfNeeded',{'nodeId':node(selector)})
   box=command('DOM.getBoxModel',{'nodeId':node(selector)})['model']['content'];x=(box[0]+box[2])/2;y=(box[1]+box[5])/2
   for kind in ('mousePressed','mouseReleased'):command('Input.dispatchMouseEvent',{'type':kind,'x':x,'y':y,'button':'left','clickCount':1})
  for method in ('Page.enable','Runtime.enable','DOM.enable'):command(method)
  command('Emulation.setDeviceMetricsOverride',{'width':1280,'height':900,'deviceScaleFactor':1,'mobile':False})
  navigate('/login','input[name=email]');fill('input[name=email]',state['email']);fill('input[name=password]',state['password']);click('form[action="/login"] button[type=submit]');wait('location.pathname==="/dashboard"')
  query='HTTP 404 Not Found cho biết điều gì về tài nguyên được yêu cầu?'
  for scenario in ('before-first-delta','after-first-delta'):
   row={'scenario':scenario,'db_before':counts()};cases.append(row);save()
   navigate('/chat','#chatinput');fill('#chatinput',query);start=time.monotonic();click('#chatform button[type=submit]')
   record=None
   until=time.monotonic()+10
   while time.monotonic()<until:
    candidates=[r for r in proxy_rows() if r.get('stream') is True and r.get('started_monotonic',0)>start]
    if candidates:record=candidates[-1];break
    time.sleep(.03)
   if not record:row['error']='No actual Ollama stream request started';save();continue
   row['provider_request_id']=record['id'];row['provider_started_s']=record['started_monotonic']-start
   if scenario=='after-first-delta':
    try:wait('document.querySelector("#chatform button[type=submit]").disabled && document.querySelector(".chat-answer")?.textContent.length>0',48)
    except AssertionError:row['error']='No provisional real model delta before stream ended';row['provider_record']=next(r for r in proxy_rows() if r['id']==record['id']);row['db_after']=counts();save();continue
   row['draft_chars_at_stop']=evaluate('document.querySelector(".chat-answer")?.textContent.length||0')
   stopped=time.monotonic();click('#chatstop');row['stop_clicked_monotonic']=stopped;row['stop_after_submit_s']=stopped-start;save()
   wait('!document.querySelector("#chatform button[type=submit]").disabled',3)
   row['ui_ready_after_stop_s']=time.monotonic()-stopped
   row['ui']=evaluate('({status:Array.from(document.querySelectorAll("[role=status]")).at(-1)?.textContent,url:location.pathname+location.search,conversation:document.querySelector("#chatlog")?.dataset.conv||"",answerChars:document.querySelector(".chat-answer")?.textContent.length||0})')
   until=time.monotonic()+3
   while time.monotonic()<until:
    record=next(r for r in proxy_rows() if r['id']==record['id'])
    if 'upstream_socket_closed_monotonic'in record:break
    time.sleep(.03)
   row['provider_record']=record
   if record.get('client_closed_monotonic'):row['api_provider_close_after_stop_s']=record['client_closed_monotonic']-stopped
   if record.get('upstream_socket_closed_monotonic'):row['actual_ollama_socket_close_after_stop_s']=record['upstream_socket_closed_monotonic']-stopped
   ticks=cpu_ticks();idle_started=time.monotonic();time.sleep(1);after=cpu_ticks();elapsed=time.monotonic()-idle_started
   row['runner_cpu_idle_window']={'elapsed_s':elapsed,'aggregate_cpu_percent':sum(after.get(pid,value)-value for pid,value in ticks.items())/os.sysconf('SC_CLK_TCK')/elapsed*100,'scope':'shared daemon process CPU, not per-request proof'}
   row['db_after']=counts();row['partial_persisted']=row['db_after']!=row['db_before'];save()
   row['tiny_real_model_probe_after_abort']=tiny_probe();save()
   print(scenario,'draft',row['draft_chars_at_stop'],'socketclose_s',row.get('actual_ollama_socket_close_after_stop_s'),'dbunchanged',not row['partial_persisted'],'probe_s',row['tiny_real_model_probe_after_abort']['elapsed_s'],flush=True)
  save()
finally:
 save()
 chrome.terminate()
 try:chrome.wait(timeout=10)
 except subprocess.TimeoutExpired:chrome.kill();chrome.wait()
 log.close()
