import hashlib,json,shutil,subprocess,datetime
from pathlib import Path
root=Path('/home/o/ITLR--RAG');tmp=Path('/tmp/itlr-release');dest=root/'reports/release-readiness-evidence';dest.mkdir(exist_ok=True)
files='''build_inventory.py final-review-checks.json blind_cases.jsonl blind_protocol.md retrieval-independent.json query-diagnostics.json retrieval_diagnostic.py cancellation_repro.py cancellation_repro.json cancellation_cleanup_pattern.py cancellation_cleanup_pattern.json review.md ui-red.log ui-green.log pdf-red.log pdf-green.log pdf-typecheck.log pdf-lint.log pdf-build.log python-tests.log python-coverage.json python-status.json coverage_run.py web-tests.log typecheck.log lint.log build.log bandit.json bandit.log pip-audit.json pip-audit.log npm-audit.json npm-audit.log pip-check.log compileall.log runtime.json runtime.log runtime.py runtime-server.log direct-generation.json direct-generation.log direct_generation.py measurement-summary.json resources-with-runner.json sample_runner.py ollama-list.log ollama-ps.log ollama-tags.json ollama-ps.json artifact_lifecycle.py artifact-lifecycle.json artifact-lifecycle.log POSTGRES_STAGING_SUMMARY.md migration-result.json migration-1.log migration-2.log http-db-result.json http-db.log http-db-before-parser-fix.log http-db-first-fixture-failure.log pdf-red.log pdf-green.log backup-restore-result.json backup-restore.log browser-db-result.json browser-db.log tls-smoke-result.json tls-smoke.log db-cleanup-result.json pg-shutdown.log http_db_journeys.py browser_db.py backup_restore.cjs setup_db.cjs start_services.py upstream_fixture.cjs tls_smoke.py cleanup_db_services.py db_query.cjs pg-download.log'''.split()
missing=[]
for name in set(files):
 p=tmp/name
 if p.is_file():shutil.copyfile(p,dest/name)
 else:missing.append(name)
for name in ('MANIFEST.json','EMBEDDINGS_MANIFEST.json'):shutil.copyfile(Path('/tmp/itlr-system-audit/staging')/name,dest/('staging-'+name))
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True)
(dest/'git-status.txt').write_text(git('status','--short'))
(dest/'git-diff-numstat.txt').write_text(git('diff','--numstat'))
paths=set(git('diff','--name-only').splitlines())|{'web/src/services/chat-ui.test.ts','reports/RELEASE_READINESS_FINAL.md'}
paths|={str(p.relative_to(root)) for p in (root/'eval').glob('*.jsonl')}
source={}
for name in sorted(paths):
 p=root/name
 if p.is_file():source[name]=hashlib.sha256(p.read_bytes()).hexdigest()
evidence={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(dest.iterdir()) if p.name!='inventory.json' and p.is_file()}
inventory={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'head':git('rev-parse','HEAD').strip(),'new_behavior_files':['web/src/public/app.js','web/src/services/chat-ui.test.ts','web/src/services/dataset-extract.ts','web/src/services/dataset-extract.test.ts'],'evidence':evidence,'source_sha256':source,'missing_optional_copy_names':sorted(set(missing)),'cloud_inference':False,'active_artifact_activation':False,'production_db_changes':False,'baseline':{'python_pass':445,'web_pass':140},'current':{'python_pass':445,'python_skip':0,'web_pass':145,'python_statements_covered':3755,'python_statements_total':5630,'web_lines_covered':635,'web_lines_total':1364},'limits':'No private env/key/dump/profile copied; AI-authored incomplete qrels, not human evaluation. No clean Bandit or production readiness claim.'}
(dest/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2));print('evidence',len(evidence),'sourcehashes',len(source),'missingoptional',sorted(set(missing)))
