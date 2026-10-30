import os,sys,json,time,resource,subprocess
from pathlib import Path
sys.path.insert(0,'/home/o/ITLR--RAG')
for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(k,None)
os.environ.update(ITLR_ARTIFACTS_DIR='/tmp/itlr-system-audit/staging',HF_HOME='/home/o/ITLR--RAG/var/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='0',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
from itlr.engine import load_engine
from eval.eval_release_retrieval import metrics
import numpy as np
root=Path('/home/o/ITLR--RAG');engine=load_engine();output={}
old={'__name__':'engineering_baseline'}
exec(compile(subprocess.check_output(['git','show','HEAD:itlr/engine.py'],text=True),'baseline-engine.py','exec'),old)
before=old['RecommenderEngine'](engine.items,engine.model,engine.search_index,engine.cf_model,engine.chatbot)
for dataset in ('engineering_queries','release_queries','engineering_confirmation_queries'):
 cases=[json.loads(line) for line in (root/'eval'/f'{dataset}.jsonl').read_text().splitlines()]
 for split in sorted({c.get('split','release') for c in cases}):
  group=[c for c in cases if c.get('split','release')==split]
  for name,threshold in [('before',90),('after',84)]:
   records=[]
   for c in group:
    start=time.perf_counter();r=(before if name=='before' else engine).search(c['query'],min_pct=threshold)
    ids=[int(i['item_id']) for i in r['results']];expected={j['item_id'] for j in c['judgments']}
    records.append({'id':c['id'],'query':c['query'],'expected':sorted(expected),'ranked':ids,'note':r['note'],'ms':(time.perf_counter()-start)*1000,'metrics':metrics(ids,expected,5)})
   positive=[r for r in records if r['expected']];negative=[r for r in records if not r['expected']]
   output[f'{split}_{name}']={'metrics5':{k:float(np.mean([r['metrics'][k] for r in positive])) for k in ('recall','precision_judged','mrr','ndcg')},'negative_empty_rate':float(np.mean([not r['ranked'] for r in negative])),'latency_ms':{f'p{p}':float(np.percentile([r['ms'] for r in records],p)) for p in (50,95,99)},'cases':records}
   print(f'{split}_{name}',output[f'{split}_{name}']['metrics5'],output[f'{split}_{name}']['negative_empty_rate'],flush=True)
output['peak_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
Path('/tmp/itlr-engineering/runtime-search.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
