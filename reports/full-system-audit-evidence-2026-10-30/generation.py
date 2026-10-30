import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path('/home/o/ITLR--RAG')
sys.path.insert(0, str(ROOT))
for key in ('DEEPSEEK_API_KEY', 'OPENAI_API_KEY'):
    os.environ.pop(key, None)
os.environ.update(USE_OLLAMA='1', OLLAMA_MODEL='qwen2.5:3b',
                  OLLAMA_BASE_URL='http://127.0.0.1:11434', DEEPSEEK_TIMEOUT_S='240',
                  DEEPSEEK_STREAM_TIMEOUT_S='240')
from itlr.chatbot import llm_client as lc

rows = {int(row['item_id']): row for row in map(json.loads, (ROOT/'data/curated_resources.jsonl').read_text().splitlines())}
queries = [json.loads(line) for line in (ROOT/'eval/release_queries.jsonl').read_text().splitlines()]
cases = [next(q for q in queries if q['kind'] == kind and q['judgments'])
         for kind in ('english', 'vietnamese')] if any(q['kind']=='english' for q in queries) else [q for q in queries if q['judgments']][:2]
results = []
for case in cases:
    judgment = case['judgments'][0]
    iid = judgment['item_id']
    messages = [{'role':'system','content':'Answer concisely in at most two sentences, only from the source. Cite its [item_id:N]. If unsupported say you cannot answer from the source.'},
                {'role':'user','content':f"Source [item_id:{iid}]: {judgment['quote']}\nQuestion: {case['query']}"}]
    for streaming in (False, True):
        start = time.perf_counter()
        record = {'id':case['id'], 'kind':case['kind'], 'query':case['query'],
                  'source_url':rows[iid]['link'], 'source_quote':judgment['quote'],
                  'streaming':streaming, 'mock':False, 'retrieval':'oracle evidence; not end-to-end'}
        try:
            answer = ''.join(lc.stream(messages, max_tokens=192, temperature=0)) if streaming else lc.chat(messages, max_tokens=192, temperature=0).text
            record.update(status='PASS', answer=answer, citation_identity=f'[item_id:{iid}]' in answer)
            assert answer.strip()
        except lc.LLMError as exc:
            record.update(status='FAIL', error=str(exc))
        record['seconds'] = time.perf_counter()-start
        results.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)

for streaming in (False, True):
    start = time.perf_counter()
    try:
        msgs=[{'role':'user','content':'Write a long essay about Python programming.'}]
        if streaming:
            list(lc.stream(msgs, max_tokens=1))
        else:
            lc.chat(msgs, max_tokens=1)
        status = 'FAIL: truncated completion accepted'
    except lc.LLMError:
        status = 'PASS: truncated completion rejected'
    results.append({'case':'real truncation', 'streaming':streaming, 'status':status,
                    'seconds':time.perf_counter()-start})

messages=[{'role':'system','content':'Answer only using the source. If the answer is absent say: Insufficient evidence.'},
          {'role':'user','content':'Source: Python lists use zero-based indexing. What is tomorrow\'s gold price?'}]
start=time.perf_counter()
try:
    answer=lc.chat(messages,max_tokens=96,temperature=0).text
    results.append({'case':'unanswerable', 'answer':answer, 'status':'OBSERVED', 'seconds':time.perf_counter()-start})
except lc.LLMError as exc:
    results.append({'case':'unanswerable','status':'FAIL','error':str(exc)})
iterator=lc.stream([{'role':'user','content':'Explain Python briefly.'}],max_tokens=96)
start=time.perf_counter()
first=next(iterator)
iterator.close()
results.append({'case':'cancellation', 'status':'PASS', 'first_delta':first, 'seconds':time.perf_counter()-start})
Path('/tmp/itlr-system-audit/generation.json').write_text(json.dumps({
    'provider':'ollama','model':'qwen2.5:3b','results':results,
    'python_peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
    'memory_note':'client only; Ollama runner memory measured separately',
    'faithfulness':None,'hallucination_rate':None,'human_evaluation':None
},ensure_ascii=False,indent=2))
