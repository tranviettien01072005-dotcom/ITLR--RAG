import os,sys,json,time,hashlib,resource
from pathlib import Path
from unittest.mock import patch
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(key,None)
os.environ.update(ITLR_ARTIFACTS_DIR='/tmp/itlr-system-audit/staging',HF_HOME='/home/o/ITLR--RAG/var/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='0',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false')
sys.path.insert(0,'/home/o/ITLR--RAG')
import numpy as np
from itlr.engine import load_engine
from eval.eval_release_retrieval import metrics
out=Path('/tmp/itlr-release'); cases_path=out/'blind_cases.jsonl'
assert hashlib.sha256(cases_path.read_bytes()).hexdigest()=='2a3a98e2d207b7c4932ced6ec87b3d7db9668c8b543730545e9a76d10abe6dd1'
engine=load_engine();ret=engine.search_index['retrieval'];index=ret.index
notes='AI-authored source-disjoint sample, not human evaluation. Qrels incomplete: unjudged items unknown, not automatically irrelevant. No tuning. Default floor84, reranker disabled as prior runtime-search baseline.'
def run_case(c):
    start=time.perf_counter()
    with patch.object(ret,'search',wraps=ret.search) as captured:
        result=engine.search(c['query'])
    ranked=[int(r['item_id']) for r in result['results']]
    expected=sorted({int(j['item_id']) for j in c['judgments']}) if 'judgments' in c else c['expected']
    return {'id':c['id'],'query':c['query'],'rewritten':captured.call_args.args[0], 'expected':expected,'ranked':ranked,'note':result['note'],'ms':(time.perf_counter()-start)*1000,'metrics':{str(k):metrics(ranked,set(expected),k) for k in (1,5,8)}}
blind=[run_case(json.loads(line)) for line in cases_path.read_text().splitlines() if line.strip()]
pos=[r for r in blind if r['expected']];neg=[r for r in blind if not r['expected']]
result={'protocol_limits':notes,'case_sha256':hashlib.sha256(cases_path.read_bytes()).hexdigest(),'model':'intfloat/multilingual-e5-base','default_floor':84,'reranker_enabled':False,'cases':blind,'metrics':{str(k):{key:float(np.mean([r['metrics'][str(k)][key] for r in pos])) for key in ('recall','precision_judged','mrr','ndcg')} for k in (1,5,8)},'negative_empty_rate':float(np.mean([not r['ranked'] for r in neg])),'counts':{'positive':len(pos),'negative':len(neg)}}
(out/'retrieval-independent.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('blind',result['metrics'], 'negative_empty_rate',result['negative_empty_rate'],flush=True)
prior=json.loads(Path('/tmp/itlr-engineering/runtime-search.json').read_text())
misses=[]
for group in ('release_after','holdout_after','confirmation_after'):
    assert group in prior,group
    for c in prior[group]['cases']:
        if c['expected'] and not set(c['expected']).issubset(c['ranked'][:5]):
            misses.append((group,c))
for c in blind:
    if c['expected'] and not set(c['expected']).issubset(c['ranked'][:5]):misses.append(('blind_current',c))
try:
    from sentence_transformers import CrossEncoder
    reranker=CrossEncoder('BAAI/bge-reranker-base',max_length=512)
    reranker_status='available offline; diagnostic only, same floor84 and existing RRF candidates'
except Exception as exc:
    reranker=None;reranker_status=f'{type(exc).__name__}: {exc}'
def unique_rank(indices,target):
    seen=[]
    for i in indices:
        item=int(index.rows[int(i)]['item_id'])
        if item not in seen:seen.append(item)
    return seen.index(target)+1 if target in seen else None

def diagnostics(query,targets):
    vector=ret.vector(query)
    normalized=np.asarray(vector,dtype='float32').reshape(1,-1).copy();normalized/=np.linalg.norm(normalized)
    scores,indices=index.ann.search(normalized,len(index.rows));dense=dict(zip(indices[0].tolist(),scores[0].tolist()))
    lexical=np.asarray(index.bm25.score_query(query));sparse=sorted((i for i,s in enumerate(lexical) if s>0),key=lambda i:(-lexical[i],i))
    ungated=ret.search(query,top_k=32,min_relevance=0,unique_items=True,vector=vector)
    gated=ret.search(query,top_k=32,min_relevance=.84,unique_items=True,vector=vector)
    reranked=index.search(query,vector,top_k=8,min_relevance=.84,unique_items=True,reranker=reranker) if reranker else None
    target_rows=[]
    for target in targets:
        owned=[i for i,row in enumerate(index.rows) if int(row['item_id'])==target]
        best=max(owned,key=lambda i:dense[i]);target_rows.append({'item_id':target,'best_dense_cosine':dense[best],'best_dense_chunk_id':f'{target}:{index.rows[best]["chunk_idx"]}','dense_item_rank':unique_rank(indices[0],target),'bm25_item_rank':unique_rank(sparse,target),'best_bm25_score':float(max(lexical[i] for i in owned)),'passes_dense_floor84':dense[best]+1e-6>=.84})
    for target in target_rows:
        for name,hits in [('ungated_rrf_rank',ungated),('gated84_rrf_rank',gated),('reranked84_rank',reranked)]:
            ranked_ids=[int(h['item_id']) for h in hits] if hits is not None else []
            target[name]=ranked_ids.index(target['item_id'])+1 if target['item_id'] in ranked_ids else None
    return {'query':query,'targets':target_rows,'ungated_rrf_top32':[int(h['item_id']) for h in ungated],'gated84_rrf_top32':[int(h['item_id']) for h in gated],'reranked84_top8':[int(h['item_id']) for h in reranked] if reranked is not None else None}
records=[]
for group,c in misses:
    current=run_case(c)
    raw=diagnostics(c['query'],c['expected'])
    rewritten=raw if current['rewritten']==c['query'] else diagnostics(current['rewritten'],c['expected'])
    records.append({'group':group,'prior':c,'current':current,'raw':raw,'rewritten':rewritten})
    print('diagnosed',group,c['id'],flush=True)
(out/'query-diagnostics.json').write_text(json.dumps({'protocol_limits':notes,'prior_evidence_sha256':hashlib.sha256(Path('/tmp/itlr-engineering/runtime-search.json').read_bytes()).hexdigest(),'candidate_policy':'existing candidate_k32, unique_items true; ungated diagnostic floor0 only, never used for engine results','reranker_status':reranker_status,'prior_misses':records,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024},ensure_ascii=False,indent=2))
