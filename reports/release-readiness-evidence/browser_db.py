import base64,json,subprocess,time,urllib.request
from pathlib import Path
from websockets.sync.client import connect

base=Path('/tmp/itlr-release'); profile=base/'chrome-db-profile';profile.mkdir(exist_ok=True)
state=json.loads((base/'private-journey-state.json').read_text())
origin='http://127.0.0.1:18030'
log=(base/'chrome-db.log').open('w')
chrome=subprocess.Popen(['/opt/google/chrome/chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-port=0',f'--user-data-dir={profile}','--no-first-run','--no-default-browser-check','about:blank'],stdout=log,stderr=log)
checks=[];errors=[];mode=None;sequence=0;responses={};intercepts=0
try:
    for _ in range(100):
        if (profile/'DevToolsActivePort').exists():break
        if chrome.poll() is not None:raise RuntimeError('Chrome exited')
        time.sleep(.1)
    port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
    request=urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank',method='PUT')
    tab=json.load(urllib.request.urlopen(request))
    with connect(tab['webSocketDebuggerUrl']) as ws:
        def command(method,params=None):
            global sequence,intercepts
            sequence+=1;current=sequence
            ws.send(json.dumps({'id':current,'method':method,'params':params or {}}))
            while current not in responses:
                obj=json.loads(ws.recv(timeout=30))
                if obj.get('method')=='Runtime.exceptionThrown':errors.append(obj['params']['exceptionDetails'].get('text','exception'))
                if obj.get('method')=='Fetch.requestPaused':
                    intercepts+=1;sequence+=1
                    final={'type':'final','response':'Browser fixture final answer [item_id:700001]','sources':[{'item_id':700001,'title':'Python introduction fixture'}],'recommendations':[],'conversation_id':987001}
                    payload=('data: '+json.dumps(final)+'\n\n').encode()
                    if mode=='valid':payload+=b'data: {"type":"done"}\n\n'
                    elif mode=='invalid-utf8':payload+=b'\xff\xfe'
                    ws.send(json.dumps({'id':sequence,'method':'Fetch.fulfillRequest','params':{'requestId':obj['params']['requestId'],'responseCode':200,'responseHeaders':[{'name':'Content-Type','value':'text/event-stream; charset=utf-8'}],'body':base64.b64encode(payload).decode()}}))
                elif 'id' in obj:responses[obj['id']]=obj
            obj=responses.pop(current)
            if 'error' in obj:raise RuntimeError(obj['error'])
            return obj.get('result',{})
        def evaluate(expression):
            r=command('Runtime.evaluate',{'expression':expression,'returnByValue':True})
            if 'exceptionDetails' in r:raise RuntimeError('Browser expression failed')
            return r['result'].get('value')
        def wait(expression):
            for _ in range(150):
                if evaluate(expression):return
                time.sleep(.1)
            raise AssertionError('Browser wait timed out: '+expression)
        def navigate(path,selector):
            command('Page.navigate',{'url':origin+path});wait(f'location.pathname==={json.dumps(path.split("?")[0])} && !!document.querySelector({json.dumps(selector)})')
        def node(selector):
            root=command('DOM.getDocument')['root']['nodeId']
            return command('DOM.querySelector',{'nodeId':root,'selector':selector})['nodeId']
        def fill(selector,text):
            command('DOM.focus',{'nodeId':node(selector)})
            command('Input.insertText',{'text':text})
        def click(selector):
            box=command('DOM.getBoxModel',{'nodeId':node(selector)})['model']['content']
            x=(box[0]+box[2])/2;y=(box[1]+box[5])/2
            for kind in ('mousePressed','mouseReleased'):
                command('Input.dispatchMouseEvent',{'type':kind,'x':x,'y':y,'button':'left','clickCount':1})
        def check(name,condition):
            assert condition,name
            checks.append(name);print('PASS',name,flush=True)
        for method in ('Page.enable','Runtime.enable','DOM.enable'):command(method)
        command('Emulation.setDeviceMetricsOverride',{'width':1280,'height':900,'deviceScaleFactor':1,'mobile':False})
        navigate('/login','input[name=email]')
        fill('input[name=email]',state['email']);fill('input[name=password]',state['password']);click('form[action="/login"] button[type=submit]')
        wait('location.pathname==="/dashboard"')
        check('real-browser-login-after-postgres-restart',True)
        navigate('/learning','.learning-progress-form')
        check('learning-progress-survives-db-restart',evaluate('document.querySelector(".learning-progress-form [name=progress]").value')=='40')
        navigate('/chat?c='+str(state['conversation_id']),'#chatinput')
        check('persisted-chat-renders-in-browser',evaluate('document.body.textContent.includes("Fixture answer")'))
        navigate('/chat','#chatinput')
        fill('#chatinput','Browser real HTTP fixture persistence');click('#chatform button[type=submit]')
        wait('!document.querySelector("#chatform button[type=submit]").disabled && location.search.includes("c=")')
        check('real-browser-sse-persists-and-completes',evaluate('Array.from(document.querySelectorAll("[role=status]")).some(e=>e.textContent.includes("Hoàn tất"))'))
        persisted_url=evaluate('location.pathname+location.search')
        navigate(persisted_url,'#chatinput')
        check('browser-reload-confirms-persisted-chat',evaluate('document.body.textContent.includes("Fixture answer")'))
        for scenario in ('missing-done','invalid-utf8','valid'):
            mode=scenario
            navigate('/chat','#chatinput')
            command('Fetch.enable',{'patterns':[{'urlPattern':'*/api/chat/stream','requestStage':'Request'}]})
            fill('#chatinput','Browser completion boundary '+scenario);click('#chatform button[type=submit]')
            wait('!document.querySelector("#chatform button[type=submit]").disabled && !!document.querySelector("[role=status]")')
            observed=evaluate('JSON.stringify({url:location.pathname+location.search,status:Array.from(document.querySelectorAll("[role=status]")).map(e=>e.textContent).at(-1),conversation:document.querySelector("#chatlog")?.dataset.conv||"",text:document.querySelector("#chatlog")?.textContent||""})')
            result=json.loads(observed)
            if scenario=='valid':
                check('final-done-browser-completes',result['status'].startswith('Hoàn tất') and result['url']=='/chat?c=987001')
            else:
                check('final-'+scenario+'-browser-never-completes',not result['status'].startswith('Hoàn tất') and result['url']=='/chat' and result['conversation']=='')
            command('Fetch.disable')
        screenshot=command('Page.captureScreenshot',{'format':'png'})
        (base/'browser-chat.png').write_bytes(base64.b64decode(screenshot['data']))
        check('browser-no-uncaught-exceptions',errors==[])
        (base/'browser-db-result.json').write_text(json.dumps({'scope':'Real Chrome CDP -> rebuilt Express -> isolated PostgreSQL; deterministic upstream fixture. Completion boundary cases intercept browser HTTP responses, not real model output.','checks':checks,'passed':len(checks),'interceptedResponses':intercepts,'runtimeExceptions':errors},indent=2))
finally:
    chrome.terminate()
    try:chrome.wait(timeout=10)
    except subprocess.TimeoutExpired:chrome.kill();chrome.wait()
    log.close()
