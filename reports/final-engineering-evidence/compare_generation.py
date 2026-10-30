import json,os,sys,time,urllib.request
from pathlib import Path
sys.path.insert(0,'/home/o/ITLR--RAG')
for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(k,None)
os.environ.update(ITLR_ARTIFACTS_DIR='/tmp/itlr-system-audit/staging',HF_HOME='/home/o/ITLR--RAG/var/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='1',OLLAMA_MODEL='qwen2.5:3b',OLLAMA_BASE_URL='http://127.0.0.1:11434',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
from itlr.engine import load_engine
from itlr.chatbot.citations import validate_citations
engine=load_engine();out=Path('/tmp/itlr-engineering');results=[]
cases=[('release','How does Docker daemon access affect root privileges?'),('dev','HTTP 404 Not Found cho biết điều gì về tài nguyên được yêu cầu?'),('holdout','Phải bind giá trị Python vào câu SQL SQLite như thế nào để tránh SQL injection?'),('holdout','Which Python copy operation recursively copies nested objects?')]
for split,query in cases:
    kind,p=engine.chatbot._prepare(query,[])
    if kind!='generate':
        results.append({'split':split,'query':query,'kind':kind,'final':p});continue
    messages=[{'role':'system','content':p['sys_prompt']},{'role':'user','content':p['llm_message']}]
    for temp in (.3,0.):
        options={'num_predict':256,'temperature':temp,'seed':42}
        payload={'model':'qwen2.5:3b','messages':messages,'stream':True,'options':options,'keep_alive':'2h'}
        start=time.perf_counter();pieces=[];first=None;terminal=None
        req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=240) as response:
            for line in response:
                r=json.loads(line);piece=r.get('message',{}).get('content','')
                if piece:
                    if first is None:first=time.perf_counter()-start
                    pieces.append(piece)
                if r.get('done'):terminal={k:v for k,v in r.items() if k!='message'}
        answer=''.join(pieces)
        result={'split':split,'query':query,'temperature':temp,'max_tokens':256,'input_chars':sum(len(m['content']) for m in messages),'seconds':time.perf_counter()-start,'ttft_seconds':first,'answer':answer,'terminal':terminal,'citation':validate_citations(answer,engine.chatbot._public_sources(p['sources']),require_chunks=True)}
        results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
        (out/'sampling-comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
