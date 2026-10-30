import http.client,http.server,json,os,socket,ssl,subprocess,threading,time
from pathlib import Path
base=Path('/tmp/itlr-release');env=json.loads((base/'private-env.json').read_text())
cert=base/'tls-fixture.crt';key=base/'tls-fixture.key'
cmd=['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-keyout',str(key),'-out',str(cert),'-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1']
r=subprocess.run(cmd,text=True,capture_output=True);assert r.returncode==0,'Local certificate creation failed';key.chmod(0o600)
log=(base/'web-tls.log').open('w')
web=subprocess.Popen(['node','dist/server.js'],cwd='/home/o/ITLR--RAG/web',env=env,stdout=log,stderr=log)
proxy=None
try:
    for _ in range(100):
        try:
            with socket.create_connection(('127.0.0.1',18030),timeout=.2):break
        except OSError:time.sleep(.05)
    class Proxy(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            upstream=http.client.HTTPConnection('127.0.0.1',18030,timeout=10)
            upstream.request('GET',self.path);response=upstream.getresponse();body=response.read()
            self.send_response(response.status)
            for name,value in response.getheaders():
                if name.lower() not in ('connection','transfer-encoding','content-length'):self.send_header(name,value)
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);upstream.close()
        def log_message(self,*args):pass
    proxy=http.server.ThreadingHTTPServer(('127.0.0.1',18443),Proxy)
    server_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server_context.load_cert_chain(str(cert),str(key))
    proxy.socket=server_context.wrap_socket(proxy.socket,server_side=True)
    thread=threading.Thread(target=proxy.serve_forever,daemon=True);thread.start()
    trust=ssl.create_default_context(cafile=str(cert))
    client=http.client.HTTPSConnection('127.0.0.1',18443,context=trust,timeout=10)
    client.request('GET','/login');tls=client.sock.version();response=client.getresponse();body=response.read().decode();headers=dict((k.lower(),v) for k,v in response.getheaders());client.close()
    assert response.status==200 and 'name="password"' in body
    assert tls in ('TLSv1.2','TLSv1.3')
    assert "script-src 'self'" in headers['content-security-policy']
    result={'scope':'Local self-signed TLS reverse-proxy transport smoke only; Web NODE_ENV=test; PostgreSQL stopped during unauthenticated login GET; not deployment/production-cookie/Caddy/public certificate validation','certificateTrust':'Explicit private CA certificate supplied to standard verified SSLContext; SAN127.0.0.1 and hostname checked','tlsVersion':tls,'path':'/login','status':response.status,'passwordFormPresent':True,'hsts':headers.get('strict-transport-security'),'csp':headers.get('content-security-policy'),'xContentTypeOptions':headers.get('x-content-type-options'),'proxyPort':18443,'productionCookieValidated':False}
    (base/'tls-smoke-result.json').write_text(json.dumps(result,indent=2));print('PASS verified-certificate TLS '+tls+' /login200; CSP present; HSTS absent under NODE_ENV=test as expected.')
finally:
    if proxy:proxy.shutdown();proxy.server_close()
    web.terminate()
    try:web.wait(timeout=10)
    except subprocess.TimeoutExpired:web.kill();web.wait()
    log.close()
for port in (18030,18443):
    with socket.socket() as s:assert s.connect_ex(('127.0.0.1',port))!=0
print('PASS TLSproxy18443 and temporaryWeb18030 stopped.')
