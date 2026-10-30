import json,os,sys,time,urllib.request
from pathlib import Path
sys.path.insert(0,'/home/o/ITLR--RAG')
for key in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(key,None)
os.environ.update(ITLR_ARTIFACTS_DIR='/tmp/itlr-system-audit/staging',HF_HOME='/home/o/ITLR--RAG/var/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='1',OLLAMA_MODEL='qwen2.5:3b',OLLAMA_BASE_URL='http://127.0.0.1:11434',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
from itlr.engine import load_engine
from itlr.chatbot.llm_client import trim_messages
engine=load_engine()
kind,p=engine.chatbot._prepare('How does Docker daemon access affect root privileges?',[])
assert kind=='generate'
messages=trim_messages([{'role':'system','content':p['sys_prompt']},{'role':'user','content':p['llm_message']}])
Path('/tmp/itlr-engineering/prompt-before.json').write_text(json.dumps({'messages':messages,'sources':engine.chatbot._public_sources(p['sources'])},ensure_ascii=False,indent=2))
results=[]
for threads in (None,2):
    options={'num_predict':256,'temperature':0,'seed':42}
    if threads:options['num_thread']=threads
    payload={'model':'qwen2.5:3b','messages':messages,'stream':True,'options':options,'keep_alive':'2h'}
    start=time.perf_counter();pieces=[];first=None;terminal=None
    req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=240) as response:
        for line in response:
            row=json.loads(line)
            piece=row.get('message',{}).get('content','')
            if piece:
                if first is None:first=time.perf_counter()-start
                pieces.append(piece)
            if row.get('done'):terminal={k:v for k,v in row.items() if k!='message'}
    result={'threads':threads,'input_chars':sum(len(m['content']) for m in messages),'seconds':time.perf_counter()-start,'ttft_seconds':first,'answer':''.join(pieces),'terminal':terminal}
    results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    Path('/tmp/itlr-engineering/generation-before-profile.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
