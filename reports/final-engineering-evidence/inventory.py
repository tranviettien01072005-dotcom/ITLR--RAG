import ast,hashlib,json,re
from pathlib import Path
from collections import defaultdict
root=Path('/home/o/ITLR--RAG');files=[];duplicates=defaultdict(list)
for folder in ('itlr','scripts','eval','web/src'):
 for p in sorted((root/folder).rglob('*')):
  if not p.is_file() or p.suffix not in ('.py','.ts'):continue
  text=p.read_text();entry={'file':str(p.relative_to(root)),'lines':len(text.splitlines()),'kind':'test' if p.name.startswith('test_') or '.test.' in p.name else 'source'}
  if p.suffix=='.py':
   tree=ast.parse(text);entry['imports']=sorted({n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names})
   entry['functions']=[{'name':n.name,'line':n.lineno,'lines':n.end_lineno-n.lineno+1,'branch_nodes':sum(isinstance(v,(ast.If,ast.For,ast.While,ast.ExceptHandler,ast.IfExp)) for v in ast.walk(n))} for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
   if entry['kind']=='source':
    for n in tree.body:
     if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.end_lineno-n.lineno>=8:
      key=hashlib.sha256(ast.dump(ast.Module(body=n.body,type_ignores=[]),include_attributes=False).encode()).hexdigest();duplicates[key].append(f'{entry["file"]}:{n.lineno}:{n.name}')
  else:entry['imports']=re.findall(r'from\s+["\']([^"\']+)',text)
  files.append(entry)
result={'scope':'static inventory, not exhaustive reachability or runtime proof','files':files,'counts':{'python':sum(f['file'].endswith('.py') for f in files),'typescript':sum(f['file'].endswith('.ts') for f in files)},'exact_duplicate_top_level_bodies':[v for v in duplicates.values() if len(v)>1]}
Path('/tmp/itlr-engineering/structure.json').write_text(json.dumps(result,indent=2))
print(result['counts']);print('Duplicate source candidates',result['exact_duplicate_top_level_bodies'])
