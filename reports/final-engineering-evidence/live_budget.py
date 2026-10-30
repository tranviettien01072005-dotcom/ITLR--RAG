import os,sys,json,time,urllib.request
from pathlib import Path
sys.path.insert(0,'/home/o/ITLR--RAG')
for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(k,None)
os.environ.update(USE_OLLAMA='1',OLLAMA_MODEL='qwen2.5:3b',OLLAMA_BASE_URL='http://127.0.0.1:11434',OLLAMA_TIMEOUT='2')
from itlr.chatbot import llm_client as lc
start=time.perf_counter();pieces=[];error=None
try:
 for token in lc.stream([{'role':'user','content':'Write a long detailed essay of at least 2000 words about Python programming.'}],max_tokens=2000):pieces.append(token)
except lc.LLMError as exc:error=str(exc)
result={'model':'qwen2.5:3b','mock':False,'configured_budget_s':2,'elapsed_s':time.perf_counter()-start,'deltas_received':len(pieces),'error':error,'completed':error is None}
assert error is not None,result
assert result['elapsed_s']<10,result
Path('/tmp/itlr-engineering/live-budget.json').write_text(json.dumps(result,indent=2))
print(result)
