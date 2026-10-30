exec(open('/tmp/itlr-engineering/compare_generation.py').read().split('for split,query in cases:')[0])
results=[]
for split,query in cases:
 kind,p=engine.chatbot._prepare(query,[])
 if kind!='generate':continue
 sources=engine.chatbot._public_sources(p['sources']);chosen=[];counts={}
 for s in sources:
  iid=s['item_id']
  if counts.get(iid,0)>=2:continue
  counts[iid]=counts.get(iid,0)+1;chosen.append(s)
  if len(chosen)==3:break
 evidence='\n\n'.join(f"[item_id:{s['item_id']}] [chunk_id:{s['chunk_id']}]\n{s['excerpt']}" for s in chosen)
 prompt=engine.chatbot.SYSTEM_PROMPT+'\n\nEVIDENCE:\n'+evidence+'\n\nAnswer the question directly in Vietnamese in at most 3 sentences. Do not repeat the question or list the sources. Cite each factual sentence using both [item_id:ID] and [chunk_id:ID:INDEX] exactly as given above.'
 messages=[{'role':'system','content':prompt},{'role':'user','content':p['llm_message']}]
 options={'num_predict':384,'temperature':.3,'seed':42}
 start=time.perf_counter();pieces=[];first=None;terminal=None
 req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps({'model':'qwen2.5:3b','messages':messages,'stream':True,'options':options,'keep_alive':'2h'}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=240) as response:
  for line in response:
   r=json.loads(line);piece=r.get('message',{}).get('content','')
   if piece:
    if first is None:first=time.perf_counter()-start
    pieces.append(piece)
   if r.get('done'):terminal={k:v for k,v in r.items() if k!='message'}
 answer=''.join(pieces)
 r={'split':split,'query':query,'source_count':len(chosen),'input_chars':sum(len(m['content']) for m in messages),'temperature':.3,'max_tokens':384,'seconds':time.perf_counter()-start,'ttft_seconds':first,'answer':answer,'terminal':terminal,'citation':validate_citations(answer,chosen,require_chunks=True)}
 results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
 (out/'prompt-experiment.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
