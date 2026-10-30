import hashlib,json,secrets,subprocess,time
from pathlib import Path
import requests

base=Path('/tmp/itlr-release')
origin='http://127.0.0.1:18030'
checks=[]
def check(name, condition):
    assert condition,name
    checks.append(name)
    print('PASS',name,flush=True)
def sql(statement,params=None):
    p=subprocess.run(['node',str(base/'db_query.cjs')],input=json.dumps({'sql':statement,'params':params or []}),text=True,capture_output=True,check=True)
    return json.loads(p.stdout)
def req(session, method, path, **kw):
    headers=kw.pop('headers',{})
    if method!='GET':headers['x-csrf-token']=session.cookies.get('csrf','')
    return session.request(method,origin+path,headers=headers,timeout=30,allow_redirects=False,**kw)
def new_user(name):
    session=requests.Session();req(session,'GET','/register')
    password='Fixture!Aa'+secrets.token_hex(12)
    email=name+'-'+secrets.token_hex(4)+'@example.test'
    r=req(session,'POST','/register',data={'name':name,'email':email,'password':password})
    check('register-'+name,r.status_code==302 and r.headers['location']=='/dashboard')
    user=sql('SELECT id FROM users WHERE email=$1',[email])[0]['id']
    return session,email,password,user

anon=requests.Session()
check('database-ready',req(anon,'GET','/ready').json()=={'status':'ready'})
check('anonymous-api-denied',req(anon,'GET','/api/conversations').status_code==401)
a,email,password,uid=new_user('owner')
b,_,_,otherid=new_user('other')
r=req(b,'POST','/register',data={'name':'Duplicate','email':email.upper(),'password':'Fixture!Aa'+secrets.token_hex(12)})
check('citext-duplicate-email-rejected',r.status_code==409)
check('password-not-plaintext',sql('SELECT password_hash LIKE $1 AS bcrypt FROM users WHERE id=$2',['$2%',uid])[0]['bcrypt'])
check('dashboard-renders',req(a,'GET','/dashboard').status_code==200)
check('csrf-missing-denied',a.post(origin+'/api/learning/diagnostic',json={'track':'python','goal':'Learn Python','answers':[1,0,2]},timeout=20).status_code==403)
check('diagnostic-persists',req(a,'POST','/api/learning/diagnostic',json={'track':'python','goal':'Learn isolated fixture Python','answers':[1,0,2]}).json()['score']==3)
check('profile-db-row',sql('SELECT track,score,level FROM learning_profiles WHERE user_id=$1',[uid])==[{'track':'python','score':3,'level':'intermediate'}])
check('progress-persists',req(a,'POST','/api/learning/progress',json={'course_id':700001,'status':'in_progress','progress':40}).status_code==200)
check('progress-db-row',sql('SELECT progress,status FROM enrollments WHERE user_id=$1',[uid])==[{'progress':40,'status':'in_progress'}])
check('invalid-completed-progress-denied',req(a,'POST','/api/learning/progress',json={'course_id':700001,'status':'completed','progress':40}).status_code==400)
check('outside-roadmap-denied',req(a,'POST','/api/learning/progress',json={'course_id':999999,'status':'in_progress','progress':10}).status_code==404)
check('progress-per-user-isolated',sql('SELECT * FROM enrollments WHERE user_id=$1',[otherid])==[])
check('search-fixture-renders','Python introduction fixture' in req(a,'GET','/search?q=python').text)
check('admin-requires-passcode',req(a,'GET','/admin').headers.get('location')=='/admin/login')
r=req(a,'POST','/api/chat',json={'message':'Explain fixture Python'})
check('chat-http-persists',r.status_code==200 and r.json()['generation_mode']=='fixture')
cid=r.json()['conversation_id']
check('chat-db-metadata',sql("SELECT role,metadata->>'generation_mode' AS mode FROM messages WHERE conversation_id=$1 ORDER BY id",[cid])==[{'role':'user','mode':None},{'role':'assistant','mode':'fixture'}])
check('chat-history-renders','Fixture answer' in req(a,'GET',f'/chat?c={cid}').text)
check('cross-user-chat-denied',req(b,'POST','/api/chat',json={'message':'forbidden','conversation_id':cid}).status_code==404)
req(b,'DELETE',f'/api/conversations/{cid}')
check('cross-user-delete-does-not-delete',bool(sql('SELECT id FROM conversations WHERE id=$1',[cid])))
r=req(a,'POST','/api/chat/stream',json={'message':'Explain fixture Python streamed','conversation_id':cid})
events=[json.loads(frame[5:]) for frame in r.text.split('\n\n') if frame.startswith('data:')]
check('sse-completes-and-persists',r.status_code==200 and [e['type'] for e in events]==['sources','text','final','done'] and len(sql('SELECT id FROM messages WHERE conversation_id=$1',[cid]))==4)
r=req(a,'POST','/api/chat/stream',json={'message':'fixture-missing-done','conversation_id':cid})
events=[json.loads(frame[5:]) for frame in r.text.split('\n\n') if frame.startswith('data:')]
check('sse-incomplete-final-never-persists',events[-1]['type']=='error' and not any(e['type']=='final' for e in events) and len(sql('SELECT id FROM messages WHERE conversation_id=$1',[cid]))==4)

# Use installed Ghostscript to avoid treating a handwritten PDF fixture as a parser oracle.
(base/'fixture.ps').write_text('%!PS\n/Helvetica findfont 12 scalefont setfont\n30 100 moveto (Isolated fixture Python resource) show\nshowpage\n')
subprocess.run(['ps2pdf',str(base/'fixture.ps'),str(base/'fixture.pdf')],check=True)
pdf=(base/'fixture.pdf').read_bytes()
check('forged-pdf-denied',req(a,'POST','/api/courses/700001/attachments',files={'file':('forged.pdf',b'not a PDF','application/pdf')}).status_code==415)
check('structurally-invalid-pdf-denied',req(a,'POST','/api/courses/700001/attachments',files={'file':('invalid.pdf',b'%PDF-1.4\n1 0 obj<</Type /Catalog>>endobj\n%%EOF','application/pdf')}).status_code==400)
r=req(a,'POST','/api/courses/700001/attachments',files={'file':('fixture.pdf',pdf,'application/pdf')})
check('valid-pdf-pending',r.status_code==200 and r.json()['pending'] is True)
attachment=sql('SELECT id,approved,size,extracted_text FROM attachments WHERE user_id=$1 ORDER BY id DESC LIMIT 1',[uid])[0]
aid=attachment['id']
check('pdf-bytea-and-extracted-text',attachment['approved'] is False and attachment['size']==len(pdf) and 'Isolated fixture Python' in attachment['extracted_text'])
r=req(a,'GET',f'/api/download/{aid}')
check('owner-pdf-download-identical',r.status_code==200 and r.content==pdf and 'sandbox' in r.headers['Content-Security-Policy'])
check('pending-pdf-other-user-hidden',req(b,'GET',f'/api/download/{aid}').status_code==404)
check('pending-pdf-other-user-cannot-delete',req(b,'DELETE',f'/api/attachments/{aid}').status_code==403)
check('logout',req(a,'POST','/logout').status_code==302)
check('logout-clears-auth',req(a,'GET','/api/conversations').status_code==401)
req(a,'GET','/login')
check('bad-password-denied',req(a,'POST','/login',data={'email':email,'password':'incorrect'}).status_code==401)
check('login-db-auth',req(a,'POST','/login',data={'email':email,'password':password}).headers.get('location')=='/dashboard')
check('conversation-owner-list',any(r['id']==cid for r in req(a,'GET','/api/conversations').json()))

state={'email':email,'password':password,'uid':uid,'conversation_id':cid,'attachment_id':aid}
state_path=base/'private-journey-state.json';state_path.write_text(json.dumps(state));state_path.chmod(0o600)
result={'scope':'Real HTTP Express -> isolated PostgreSQL18; upstream search/chat/SSE is explicit deterministic fixture, not neural/LLM', 'checks':checks,'passed':len(checks),'fixtureUsers':2,'fixtureCourses':3,'generationMeasured':False,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
(base/'http-db-result.json').write_text(json.dumps(result,indent=2))
print('PASS',len(checks),'real HTTP/DB checks; no credentials printed.')
