import os,sys,json,time,hashlib
from pathlib import Path
sys.path.insert(0,'/home/o/ITLR--RAG')
for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(k,None)
os.environ.update(ITLR_ARTIFACTS_DIR='/tmp/itlr-system-audit/staging',HF_HOME='/home/o/ITLR--RAG/var/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='0',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
from itlr.engine import load_engine
from eval.eval_release_retrieval import metrics
import numpy as np
root=Path('/home/o/ITLR--RAG');path=root/'eval/release_queries.jsonl';cases=[json.loads(line) for line in path.read_text().splitlines()];ret=load_engine().search_index['retrieval'];results={}
for floor in (.9,.84):
 rows=[]
 for c in cases:
  start=time.perf_counter();hits=ret.search(c['query'],top_k=10,min_relevance=floor,unique_items=True);ids=[int(h['item_id']) for h in hits];expected={j['item_id'] for j in c['judgments']}
  rows.append({'id':c['id'],'expected':sorted(expected),'ranked':ids,'ms':(time.perf_counter()-start)*1000,'metrics':{str(k):metrics(ids,expected,k) for k in (1,5,10)}})
 pos=[r for r in rows if r['expected']];neg=[r for r in rows if not r['expected']]
 results[str(floor)]={'metrics':{str(k):{key:float(np.mean([r['metrics'][str(k)][key] for r in pos])) for key in ('recall','precision_judged','mrr','ndcg')} for k in (1,5,10)},'negative_empty_rate':float(np.mean([not r['ranked'] for r in neg])),'latency_ms':{f'p{p}':float(np.percentile([r['ms'] for r in rows],p)) for p in (50,95,99)},'cases':rows}
 print(floor,results[str(floor)]['metrics']['5'],flush=True)
Path('/tmp/itlr-engineering/raw-release.json').write_text(json.dumps({'query_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'model':'intfloat/multilingual-e5-base','scope':'raw shared chunk retrieval, not rewritten engine search','results':results},indent=2))
