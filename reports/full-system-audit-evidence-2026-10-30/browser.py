import base64
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from websockets.sync.client import connect

root=Path('/tmp/itlr-system-audit')
profile=Path(tempfile.mkdtemp(prefix='chrome-cdp-',dir=root))
log=(root/'chrome-cdp.log').open('w')
proc=subprocess.Popen(['google-chrome','--headless=new','--remote-debugging-port=0',
    f'--user-data-dir={profile}','--no-first-run','--no-default-browser-check','about:blank'],stdout=log,stderr=log)
events=[]
checks=[]
try:
    for _ in range(100):
        if (profile/'DevToolsActivePort').exists(): break
        if proc.poll() is not None: raise RuntimeError('Chrome exited')
        time.sleep(.1)
    port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
    req=urllib.request.Request(f'http://127.0.0.1:{port}/json/new?about:blank',method='PUT')
    with urllib.request.urlopen(req) as response:
        tab=json.load(response)
    with connect(tab['webSocketDebuggerUrl']) as ws:
        sequence=0
        def command(method,params=None):
            global sequence
            sequence+=1
            ws.send(json.dumps({'id':sequence,'method':method,'params':params or {}}))
            while True:
                obj=json.loads(ws.recv(timeout=20))
                if obj.get('id')==sequence:
                    if 'error' in obj: raise RuntimeError(obj['error'])
                    return obj.get('result',{})
                events.append(obj)
        for method in ('Page.enable','Runtime.enable','Log.enable','Network.enable'):
            command(method)
        for width,height in ((390,844),(1280,900)):
            command('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<500})
            for page in ('login','register'):
                nav=command('Page.navigate',{'url':f'http://127.0.0.1:18030/{page}'})
                print('navigation',nav,flush=True)
                expression='JSON.stringify({width:innerWidth,scroll:document.documentElement?.scrollWidth,password:!!document.querySelector("input[type=password]"),claim:(document.body?.textContent||"").includes("50.000"),title:document.title})'
                for _ in range(100):
                    result=json.loads(command('Runtime.evaluate',{'expression':expression,'returnByValue':True})['result']['value'])
                    if result['password']: break
                    time.sleep(.1)
                result.update(page=page,viewport=width)
                assert result['password'] and not result['claim'],result
                assert result['scroll']<=result['width'],result
                checks.append(result)
                shot=command('Page.captureScreenshot',{'format':'png'})
                (root/f'{page}-{width}.png').write_bytes(base64.b64decode(shot['data']))
        errors=[event for event in events if event.get('method')=='Runtime.exceptionThrown' or
                (event.get('method')=='Log.entryAdded' and event['params']['entry']['level']=='error')]
        assert not errors, errors
    for path,method,expected in [('/health','GET',200),('/ready','GET',503),('/api/chat','GET',401),('/api/chat','POST',403)]:
        req=urllib.request.Request('http://127.0.0.1:18030'+path,method=method)
        try:
            response=urllib.request.urlopen(req,timeout=10)
        except urllib.error.HTTPError as exc:
            response=exc
        with response:
            assert response.status==expected,(path,response.status)
            assert response.headers['X-Content-Type-Options']=='nosniff'
            checks.append({'path':path,'method':method,'status':response.status})
    (root/'browser.json').write_text(json.dumps({'checks':checks,'console_errors':errors,'scope':'public forms and denial only; PostgreSQL unavailable'},indent=2))
    print('PASS',json.dumps(checks))
finally:
    (root/'browser-events.json').write_text(json.dumps(events,indent=2))
    proc.terminate()
    try: proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    log.close()
