import os,sys,json,shutil,time
from pathlib import Path
root=Path('/home/o/ITLR--RAG');sys.path.insert(0,str(root));out=Path('/tmp/itlr-release');fixture=out/'artifact-lifecycle-v2'
for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY'):os.environ.pop(k,None)
os.environ.update(ITLR_ARTIFACTS_DIR=str(fixture),HF_HOME=str(root/'var/hf'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_OLLAMA='0',DISABLE_RERANKER='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',ITLR_REQUIRE_ARTIFACT_MANIFEST='1')
from itlr.versioning import activate,rollback,current_version,verify_integrity,VersionError
from itlr.engine import load_engine, _reload_engine
os.environ.pop("ITLR_ARTIFACTS_DIR")  # config root captured above; enable normal pointer resolution.
checks=[]
assert not fixture.exists(),'fresh fixture required'
for version in ('fixture-a','fixture-b'):
 target=fixture/'versions'/version;shutil.copytree('/tmp/itlr-system-audit/staging',target)
 verify_integrity(target,required=True);checks.append(version+' trusted copy integrity')
 manifest=json.loads((target/'MANIFEST.json').read_text());assert manifest['probe']=='ok'
activate(fixture,'fixture-a');assert current_version(fixture)=='fixture-a';checks.append('isolated pointer a')
start=time.perf_counter();engine=load_engine();assert len(engine.items)==118;assert engine.search('Dockerfile')['results'];checks.append('real E5 engine load a,118items,retrieval')
activate(fixture,'fixture-b');assert current_version(fixture)=='fixture-b';checks.append('isolated pointer b')
del engine
engine=_reload_engine();assert len(engine.items)==118;checks.append('real engine reload b')
assert rollback(fixture);assert current_version(fixture)=='fixture-a';checks.append('isolated rollback a')
# Tamper only the disposable copy and require rejection before any deserialization.
path=fixture/'versions'/'fixture-b'/'item_list.pkl'
with path.open('ab') as stream:stream.write(b'tamper-fixture')
try:activate(fixture,'fixture-b')
except VersionError:checks.append('tampered copy activation rejected')
else:raise AssertionError('tampered artifact accepted')
assert current_version(fixture)=='fixture-a';checks.append('failed switch retains previous pointer')
(out/'artifact-lifecycle.json').write_text(json.dumps({'scope':'temporary root only; repository active CURRENT untouched; direct engine load, not HTTP reload','checks':checks,'elapsed_s':time.perf_counter()-start},indent=2))
print(checks,flush=True)
