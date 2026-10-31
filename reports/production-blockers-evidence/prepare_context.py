import os,sys,json
from pathlib import Path
root=Path('/home/o/ITLR--RAG');sys.path.insert(0,str(root));out=Path('/tmp/itlr-blockers')
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(key,None)
os.environ.update(ITLR_ARTIFACTS_DIR='/tmp/itlr-system-audit/staging',HF_HOME=str(root/'var/hf'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='1',OLLAMA_MODEL='qwen2.5:3b',OLLAMA_BASE_URL='http://127.0.0.1:11434',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
from itlr.engine import load_engine
engine=load_engine();case=next(json.loads(s) for s in (root/'eval/engineering_queries.jsonl').read_text().splitlines() if json.loads(s)['id']=='dev-vi-5061')
kind,p=engine.chatbot._prepare(case['query'],[]);assert kind=='generate';sources=engine.chatbot._public_sources(p['sources'])
(out/'dev-context-prepared.json').write_text(json.dumps({'case':case,'system_prompt':p['sys_prompt'],'system_base':engine.chatbot.SYSTEM_PROMPT,'message':p['llm_message'],'sources':sources},ensure_ascii=False,indent=2))
for s in sources:print(s['chunk_id'],len(s['excerpt']),s['excerpt'])
