"""Frozen evaluation only; no tuning, no human scores and no daemon changes."""
import asyncio,json,os,sys,time,resource,hashlib
from contextlib import aclosing
from pathlib import Path
root=Path('/home/o/ITLR--RAG');sys.path.insert(0,str(root));out=Path('/tmp/itlr-blockers')
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(key,None)
os.environ.update(ITLR_ARTIFACTS_DIR='/tmp/itlr-system-audit/staging',HF_HOME=str(root/'var/hf'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='1',OLLAMA_MODEL='qwen2.5:3b',OLLAMA_BASE_URL='http://127.0.0.1:11434',OLLAMA_TIMEOUT='45',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
from itlr.engine import load_engine
p=root/'reports/release-readiness-evidence/blind_cases.jsonl';assert hashlib.sha256(p.read_bytes()).hexdigest()=='2a3a98e2d207b7c4932ced6ec87b3d7db9668c8b543730545e9a76d10abe6dd1'
cases=[json.loads(x) for x in p.read_text().splitlines()];engine=load_engine();rows=[]
async def main():
 for case in (cases[0],cases[7],cases[-1]):
  started=time.perf_counter();events=[];first=None
  async with aclosing(engine.achat_stream(case['query'])) as response:
   async for kind,data in response:
    if kind=='text' and first is None:first=time.perf_counter()-started
    events.append({'type':kind,'data':data})
  final=next(e['data'] for e in events if e['type']=='final')
  rows.append({'id':case['id'],'query':case['query'],'seconds':time.perf_counter()-started,'ttft_s':first,'events':events,'final':final,'human_groundedness':None,'human_hallucination':None,'human_answer_relevance':None})
  (out/'generation-eval.json').write_text(json.dumps({'dataset_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'dataset_author':'frozen fresh AI author, not human labels','model':'qwen2.5:3b','budget_s':45,'cases':rows,'scope':'current engine async stream, no HTTP proxy, sequential shared-daemon evaluation; no policy tuning'},ensure_ascii=False,indent=2))
  print(case['id'],rows[-1]['seconds'],final['generation_mode'],flush=True)
asyncio.run(main())
# Packets contain outputs and exact supplied evidence; all score fields remain null.
with (out/'human-review-packet.jsonl').open('w') as f:
 for row in rows:
  f.write(json.dumps({'id':row['id'],'query':row['query'],'response':row['final']['response'],'provisional_model_text':''.join(e['data'] for e in row['events'] if e['type']=='text'),'generation_error':row['final'].get('generation_error'),'sources':row['final'].get('sources',[]),'reviewer_id':None,'claim_support':None,'answer_relevance':None,'refusal_appropriate':None,'notes':None,'generation_mode':row['final']['generation_mode']},ensure_ascii=False)+'\n')
