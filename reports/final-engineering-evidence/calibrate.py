import os,sys,json,time,hashlib,resource
from pathlib import Path
sys.path.insert(0,'/home/o/ITLR--RAG')
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(key,None)
os.environ.update(ITLR_ARTIFACTS_DIR='/tmp/itlr-system-audit/staging',HF_HOME='/home/o/ITLR--RAG/var/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='0',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
from itlr.engine import load_engine
from eval.eval_release_retrieval import metrics
import numpy as np
root=Path('/home/o/ITLR--RAG');out=Path('/tmp/itlr-engineering')
cases=[json.loads(line) for line in (root/'eval/engineering_queries.jsonl').read_text().splitlines()]
engine=load_engine();service=engine.search_index['retrieval']
outputs={};vectors={}
def run_case(case,floor,reranker=False):
    q=case['query']
    if q not in vectors:
        t=time.perf_counter();v=service.vector(q);vectors[q]=(v,(time.perf_counter()-t)*1000)
    v,encode_ms=vectors[q];start=time.perf_counter()
    hits=service.search(q,vector=v,min_relevance=floor,top_k=10,unique_items=True,use_reranker=reranker)
    ids=[int(h['item_id']) for h in hits];expected={j['item_id'] for j in case['judgments']}
    return dict(id=case['id'],kind=case['kind'],ranked=ids,expected=sorted(expected),max_cosine=service.relevance(q,vector=v),latency_ms=(time.perf_counter()-start)*1000+encode_ms,metrics={str(k):metrics(ids,expected,k) for k in (1,5,10)})
def summarize(rows):
    positive=[r for r in rows if r['expected']];negative=[r for r in rows if not r['expected']]
    return dict(metrics={str(k):{key:float(np.mean([r['metrics'][str(k)][key] for r in positive])) for key in ('recall','precision_judged','mrr','ndcg')} for k in (1,5,10)},negative_empty_rate=float(np.mean([not r['ranked'] for r in negative])),latency_ms={f'p{p}':float(np.percentile([r['latency_ms'] for r in rows],p)) for p in (50,95,99)},cases=rows)
dev=[c for c in cases if c['split']=='dev'];hold=[c for c in cases if c['split']=='holdout']
sweep={str(f):summarize([run_case(c,f) for c in dev]) for f in (.7,.74,.76,.78,.8,.82,.84,.86,.88,.9)}
base=sweep['0.9'];eligible=[(float(f),v) for f,v in sweep.items() if v['negative_empty_rate']>=base['negative_empty_rate'] and v['metrics']['5']['precision_judged']>=base['metrics']['5']['precision_judged'] and v['metrics']['5']['ndcg']>=base['metrics']['5']['ndcg']]
selected=max(eligible,key=lambda p:(p[1]['metrics']['5']['recall'],p[1]['metrics']['5']['ndcg'],p[0]))[0]
(out/'threshold-selection.json').write_text(json.dumps({'cases_sha256':hashlib.sha256((root/'eval/engineering_queries.jsonl').read_bytes()).hexdigest(),'selection_scope':'development only, source-item disjoint from holdout','selected_floor':selected,'sweep':sweep},ensure_ascii=False,indent=2))
print('SELECTED',selected,flush=True)
for split,group in [('dev',dev),('holdout',hold)]:
    for name,floor in [('baseline',.9),('selected',selected)]:outputs[f'{split}_{name}']=summarize([run_case(c,floor) for c in group])
(out/'calibration.json').write_text(json.dumps({'selected_floor':selected,'results':outputs},ensure_ascii=False,indent=2))
from sentence_transformers import CrossEncoder
reranker=CrossEncoder('BAAI/bge-reranker-base',max_length=512)
service.reranker=reranker
for split,group in [('dev',dev),('holdout',hold)]:
    rows=[]
    for i,c in enumerate(group):
        rows.append(run_case(c,selected,True));print('RERANK',split,i+1,flush=True)
    outputs[f'{split}_reranker']=summarize(rows)
    (out/'calibration.json').write_text(json.dumps({'selected_floor':selected,'embedding':'intfloat/multilingual-e5-base','reranker':'BAAI/bge-reranker-base','rerank_pool':32,'labels':'engineer-authored, source-disjoint split; no independent annotators','peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,'results':outputs},ensure_ascii=False,indent=2))
print({k:{'metrics5':v['metrics']['5'],'negative_empty':v['negative_empty_rate'],'latency':v['latency_ms']} for k,v in outputs.items()},flush=True)
