"""Offline real-snapshot retrieval experiment; hand-authored item qrels, no generation."""
import json
import os
import sys
import time

try:
    import resource
except ImportError:  # Windows: getrusage unavailable, report peak RSS as null
    resource = None

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('HF_HOME',str(ROOT/'var/hf'))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
import numpy as np
from itlr.collect.chunk import chunk_text
from itlr.core.chunks import ChunkIndex
from itlr.core.embeddings import load_model, resolve_preset, encode_passages, encode_query
from itlr.eval.metrics import ndcg_at_k

CASES = [(5001,'How does Docker daemon access affect root privileges?'),
         (5003,'How do services networks and volumes work together in Compose?'),
         (5011,'How do I publish a container port to a host port?'),
         (5024,'How does a browser use a preflight request for cross origin HTTP?'),
         (5028,'How do I select the first DOM element matching a CSS selector?'),
         (5117,'How do I create and activate a Python virtual environment?'),
         (5121,'How do I handle exceptions with try and except in Python?'),
         (5126,'How do Python lists support indexing and slicing?')]


def main():
    docs = {int(r['item_id']):r for r in map(json.loads,
            (ROOT/'data/curated_resources.jsonl').read_text().splitlines())}
    rows=[]
    for iid,_ in CASES:
        for j,text in enumerate(chunk_text(docs[iid]['full_text'],max_chars=900,overlap_chars=120)):
            rows.append(dict(item_id=iid,chunk_idx=j,chunk_text=text))
    preset=resolve_preset('intfloat/multilingual-e5-base')
    model=load_model(preset['model_name'])
    vectors=encode_passages(model,[r['chunk_text'] for r in rows],preset,batch_size=8)
    index=ChunkIndex(rows,vectors)
    ids=[iid for iid,_ in CASES]
    means=np.stack([vectors[[i for i,r in enumerate(rows) if r['item_id']==iid]].mean(axis=0) for iid in ids])
    means/=np.linalg.norm(means,axis=1,keepdims=True)
    outputs={name:[] for name in ['item_mean_dense','chunk_hybrid_rrf']}
    for iid,query in CASES:
        cpu_start=time.process_time()
        start=time.perf_counter(); q=encode_query(model,query,preset); encode_ms=(time.perf_counter()-start)*1000
        encode_cpu_ms=(time.process_time()-cpu_start)*1000
        for name in outputs:
            cpu_start=time.process_time()
            start=time.perf_counter()
            if name=='item_mean_dense':
                ranked=[ids[i] for i in np.argsort(-(means@q))]
            else:
                hits=index.search(query,q,top_k=len(rows),candidate_k=len(rows))
                ranked=list(dict.fromkeys(h['item_id'] for h in hits))
            elapsed=(time.perf_counter()-start)*1000+encode_ms
            rank=ranked.index(iid)+1 if iid in ranked else None
            outputs[name].append(dict(query=query,expected_id=iid,rank=rank,latency_ms=elapsed,
                cpu_ms=(time.process_time()-cpu_start)*1000+encode_cpu_ms,
                recall_at_5=float(iid in ranked[:5]),mrr_at_5=1/rank if rank and rank<=5 else 0,
                ndcg_at_5=ndcg_at_k([int(x==iid) for x in ranked],5,ideal_rels=[1])))
    report=dict(provenance='real checked-in source snapshots; eight hand-authored item-level query judgments, not human panel labels',
        scope='8 documents only; no distractors outside selected corpus; no reranker; not release quality evidence',
        n_chunks=len(rows),model=preset['model_name'],faithfulness=None,hallucination=None,citation_accuracy=None,
        peak_process_rss_mib=(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
                               if resource else None),
        memory_scope=('Whole process high-water RSS including model load and both configurations, not per-configuration memory'
                      if resource else 'not measured: getrusage is unavailable on this platform'),
        generation='not run; no paid API calls',results={})
    for name,cases in outputs.items():
        report['results'][name]={k:float(np.mean([c[k] for c in cases])) for k in ['recall_at_5','mrr_at_5','ndcg_at_5','cpu_ms']}
        report['results'][name]['p95_latency_ms']=float(np.percentile([c['latency_ms'] for c in cases],95))
        report['results'][name]['cases']=cases
    path=ROOT/'reports/chunks_v3_unified_experiment.json'
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}))
    print(json.dumps({k:{a:b for a,b in v.items() if a!='cases'} for k,v in report['results'].items()}))

if __name__=='__main__': main()
