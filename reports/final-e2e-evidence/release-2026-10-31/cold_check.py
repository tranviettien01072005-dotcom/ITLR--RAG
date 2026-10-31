"""Cold vs warm prefill for the real selection prompt in a throwaway Ollama container."""
import json, subprocess, time, urllib.request
from pathlib import Path
PROMPT = Path('/tmp/opencode/itlr-bench-prompt.txt').read_text()
NAME = 'itlr-cold-check'; PORT = 19610
def docker(*a, check=True): return subprocess.run(['docker', *a], capture_output=True, text=True, check=check)
docker('rm','-f',NAME,check=False)
docker('run','-d','--name',NAME,'--cpus','8','-p',f'127.0.0.1:{PORT}:11434',
       '-v','/usr/share/ollama/.ollama/models:/root/.ollama/models:ro',
       '-e','OLLAMA_HOST=0.0.0.0:11434','-e','OLLAMA_NUM_PARALLEL=1','-e','OLLAMA_MAX_LOADED_MODELS=1',
       '-e','OLLAMA_CONTEXT_LENGTH=4096','ollama/ollama:0.40.13')
def post(path,payload,timeout=240):
    req=urllib.request.Request(f'http://127.0.0.1:{PORT}{path}',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    t=time.monotonic(); body=json.load(urllib.request.urlopen(req,timeout=timeout)); return body, time.monotonic()-t
try:
    for _ in range(120):
        try: urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/tags',timeout=2).read(); break
        except Exception: time.sleep(0.5)
    rows=[]
    for label in ('cold','warm'):
        body, wall = post('/api/generate', {'model':'qwen2.5:3b','prompt':PROMPT,'stream':False,
                                            'options':{'num_predict':20,'temperature':0,'num_ctx':4096}})
        pe=body.get('prompt_eval_duration',0)/1e9; ed=body.get('eval_duration',0)/1e9
        rows.append({'state':label,'wall_s':round(wall,3),'load_s':round(body.get('load_duration',0)/1e9,3),
                     'prompt_tokens':body.get('prompt_eval_count'),'prefill_s':round(pe,3),
                     'prefill_tok_s':round(body.get('prompt_eval_count',0)/pe,1) if pe else None,
                     'decode_s':round(ed,3),'decode_tok_s':round(body.get('eval_count',0)/ed,1) if ed else None,
                     'done_reason':body.get('done_reason')})
    doc={'prompt_chars':len(PROMPT),'container':'ollama/ollama:0.40.13, --cpus 8, NUM_PARALLEL=1, ctx 4096','rows':rows}
    Path('/tmp/opencode/itlr-bench/components-cold.json').write_text(json.dumps(doc,indent=2))
    print(json.dumps(doc,indent=2))
finally:
    docker('rm','-f',NAME,check=False)
