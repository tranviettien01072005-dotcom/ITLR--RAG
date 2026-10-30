import subprocess,time,json
from pathlib import Path
rows=[]
for _ in range(120):
 lines=subprocess.check_output(['ps','-eo','pid,ppid,pcpu,rss,comm'],text=True).splitlines()[1:];sample=[]
 for line in lines:
  parts=line.split()
  if len(parts)==5 and (parts[0]=='53579' or parts[-1].startswith('ollama') or parts[-1]=='llama-server'):
   sample.append(dict(zip(('pid','ppid','cpu_percent_lifetime','rss_kib','comm'),parts)))
 rows.append({'time':time.time(),'processes':sample})
 Path('/tmp/itlr-release/resources-with-runner.json').write_text(json.dumps({'cpu_scope':'ps lifetime-average percent; not per-request attribution','samples':rows},indent=2))
 time.sleep(1)
