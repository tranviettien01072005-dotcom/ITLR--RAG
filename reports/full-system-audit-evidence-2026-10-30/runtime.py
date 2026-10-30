import hashlib
import json
import os
from pathlib import Path
import resource
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT=Path('/home/o/ITLR--RAG')
OUT=Path('/tmp/itlr-system-audit')
STAGE=OUT/'staging'
sys.path.insert(0,str(ROOT))
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'): os.environ.pop(key,None)
os.environ.update(ITLR_ARTIFACTS_DIR=str(STAGE),HF_HOME=str(ROOT/'var/hf'),
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='0',DISABLE_RERANKER='1',
    OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',
    ITLR_REQUIRE_ARTIFACT_MANIFEST='1')
from itlr.indexv2 import probe
ok,report=probe(STAGE)
(OUT/'probe.json').write_text(json.dumps({'ok':ok,'report':report},indent=2))
assert ok,report
print('PROBE PASS',flush=True)
from itlr.engine import load_engine
from eval.eval_release_retrieval import metrics
import numpy as np
engine=load_engine()
retrieval=engine.search_index['retrieval']
cases=[json.loads(line) for line in (ROOT/'eval/release_queries.jsonl').read_text().splitlines()]
results={}
for name,floor in [('default_cosine_090',.9),('diagnostic_no_floor',0.)]:
    records=[]
    latencies=[]
    for case in cases:
        ranked=[]
        for _ in range(2):
            start=time.perf_counter()
            hits=retrieval.search(case['query'],top_k=10,min_relevance=floor,unique_items=True)
            latencies.append((time.perf_counter()-start)*1000)
            ids=[int(hit['item_id']) for hit in hits]
            if ranked: assert ranked==ids,'nondeterministic ranking'
            ranked=ids
        expected={j['item_id'] for j in case['judgments']}
        records.append({'id':case['id'],'kind':case['kind'],'query':case['query'],
            'ranked':ranked,'expected':sorted(expected),
            'metrics':{str(k):metrics(ranked,expected,k) for k in (1,5,10)}})
    aggregate={}
    for k in (1,5,10):
        positive=[r['metrics'][str(k)] for r in records if r['expected']]
        aggregate[str(k)]={key:float(np.mean([r[key] for r in positive]))
                           for key in ('recall','precision_judged','mrr','ndcg')}
    negatives=[r for r in records if not r['expected']]
    results[name]={'floor':floor,'cases':records,'aggregate':aggregate,
        'latency_ms':{f'p{p}':float(np.percentile(latencies,p)) for p in (50,95,99)},
        'negative_empty_rate':float(np.mean([not r['ranked'] for r in negatives]))}
    print(name,aggregate['5'],flush=True)
manifest=json.loads((STAGE/'MANIFEST.json').read_text())
payload={'corpus_items':len(engine.items),'chunks':len(retrieval.index.rows),
    'model':'intfloat/multilingual-e5-base','dim':768,'prefixes':['query: ','passage: '],
    'normalization':'L2','reranker':False,'faiss':True,'bm25':True,'rrf':True,
    'labels':'frozen engineer-authored item judgments; incomplete, no independent human panel',
    'query_count':len(cases),'repeats':2,'results':results,
    'corpus_sha256':hashlib.sha256((ROOT/'data/curated_resources.jsonl').read_bytes()).hexdigest(),
    'queries_sha256':hashlib.sha256((ROOT/'eval/release_queries.jsonl').read_bytes()).hexdigest(),
    'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
    'memory_scope':'probe parent + engine + benchmark process high-water; excludes Ollama/API process',
    'faithfulness':None,'hallucination':None}
(OUT/'retrieval-neural.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
load_engine.cache_clear()
del engine,retrieval
import gc
gc.collect()

token=secrets.token_urlsafe(32)
env={**os.environ,'USE_OLLAMA':'1','OLLAMA_MODEL':'qwen2.5:3b',
     'OLLAMA_BASE_URL':'http://127.0.0.1:11434','OLLAMA_TIMEOUT':'240','ITLR_ADMIN_TOKEN':token}
log=(OUT/'api.log').open('w')
proc=subprocess.Popen([sys.executable,'-m','uvicorn','itlr.api.server:app','--host','127.0.0.1',
    '--port','18080','--workers','1','--no-proxy-headers'],env=env,cwd=ROOT,stdout=log,stderr=log)
api=[]
def request(path,body=None,headers=None):
    req=urllib.request.Request('http://127.0.0.1:18080'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json',**(headers or {})})
    try: response=urllib.request.urlopen(req,timeout=300)
    except urllib.error.HTTPError as exc: response=exc
    with response: return response.status,response.read().decode('utf-8')
try:
    for _ in range(120):
        if proc.poll() is not None: raise RuntimeError('API process exited')
        try:
            status,text=request('/health')
            if status==200: break
        except OSError: pass
        time.sleep(.5)
    else: raise RuntimeError('readiness timeout')
    health=json.loads(text)
    assert health['engine']=='ready',health
    api.append({'path':'/health','status':status,'body':health})
    for path,body,expected in [('/api/search',{'query':'Docker security','min_pct':70},200),
                              ('/api/search',{'query':'x'*501},422),
                              ('/api/personas',None,503),('/admin/reload',{},403),
                              ('/api/for-you',{'persona':1,'interested':[]},503)]:
        status,text=request(path,body)
        assert status==expected,(path,status,text)
        api.append({'path':path,'status':status,'body':json.loads(text)})
    for streaming in (False,True):
        path='/api/chat/stream' if streaming else '/api/chat'
        start=time.perf_counter()
        status,text=request(path,{'message':'How does Docker daemon access affect root privileges?','history':[]})
        assert status==200,(path,status,text)
        if streaming:
            events=[json.loads(line[6:]) for line in text.splitlines() if line.startswith('data: ')]
            assert events[-1]['type']=='done'
            assert sum(e['type']=='final' for e in events)==1
            final=next(e for e in events if e['type']=='final')
            record={'path':path,'status':status,'seconds':time.perf_counter()-start,
                    'event_count':len(events),'types':sorted({e['type'] for e in events}),'final':final}
        else:
            record={'path':path,'status':status,'seconds':time.perf_counter()-start,'body':json.loads(text)}
        api.append(record)
        print(path,record['seconds'],flush=True)
    status,text=request('/admin/reload',{}, {'X-Admin-Token':token})
    assert status==200,(status,text)
    api.append({'path':'/admin/reload','authenticated':True,'status':status,'body':json.loads(text)})
    (OUT/'api.json').write_text(json.dumps({'checks':api,'scope':'isolated real-snapshot staging, local Qwen'},ensure_ascii=False,indent=2))
finally:
    proc.terminate()
    try: proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    log.close()
