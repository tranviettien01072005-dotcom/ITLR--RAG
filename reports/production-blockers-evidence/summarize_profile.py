import json,statistics
from pathlib import Path
p=Path('/tmp/itlr-blockers');d=json.loads((p/'profile-local.json').read_text());rag=[c for c in d['checks'] if c['label']!='warm-smoke-before'];success=[c for c in rag if c['completed']]
def pct(values,percent):
 a=sorted(values)
 if not a:return None
 x=(len(a)-1)*percent;lo=int(x);return a[lo]+(a[min(lo+1,len(a)-1)]-a[lo])*(x-lo)
resources={}
for sample in d['resource_samples']:
 for proc in sample['processes']:
  slot=resources.setdefault(proc['name'],{'rss_mib_peak':0,'cpu_percent':[]});slot['rss_mib_peak']=max(slot['rss_mib_peak'],proc['rss_mib'])
  if proc['interval_cpu_pct'] is not None:slot['cpu_percent'].append(proc['interval_cpu_pct'])
for slot in resources.values():
 values=slot.pop('cpu_percent');slot.update(interval_cpu_pct_mean=statistics.mean(values),interval_cpu_pct_p95=pct(values,.95),interval_cpu_pct_max=max(values),samples=len(values))
summary={'scope':'4 directOllama RAGcalls on2developmentqueries; not independentquality benchmark; sharedhost/cache state','rag_completed':len(success),'rag_attempted':len(rag),'observed_completion_rate':len(success)/len(rag),'elapsed_including_timeouts_s':{'p50':pct([r['wall_s'] for r in rag],.5),'p95':pct([r['wall_s'] for r in rag],.95)},'successful_only_ttft_s':{'p50':pct([r['ttft_s'] for r in success],.5),'p95':pct([r['ttft_s'] for r in success],.95)},'successful_only_decode_tokens_per_s':[r['decode_tokens_per_s'] for r in success],'resources':resources,'human_faithfulness':None,'model_coldstart':None,'context_overflow_reproduced':False,'max_prompt_tokens_observed':max(r['terminal']['prompt_eval_count'] for r in success),'num_ctx_loaded':4096,'timed_out_prompt_eval_count':None,'note':'successfulcachehit terminal counters do not reveal howmuch prefill timedout requestcompleted; unknown notzero'}
(p/'profile-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
