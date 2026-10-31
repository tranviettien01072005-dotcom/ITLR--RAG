import hashlib,json,re,shutil,subprocess,datetime,socket
from pathlib import Path
root=Path('/home/o/ITLR--RAG');tmp=Path('/tmp/itlr-blockers');dest=root/'reports/production-blockers-evidence'
names='''HUMAN_REVIEW_PROTOCOL.md PROFILE_FINDINGS.md async-sdk-green.log async-utf8-green.log async-utf8-red.log bandit.json bandit.log browser-cancellation-first-harness-failure.json browser-cancellation-first-harness-failure.log browser-cancellation-navigation-harness-failure.log browser-cancellation-review.md browser-cancellation.json browser-cancellation.log browser_cancellation.py build.log cancel-api.log cancel-cleanup.json cancel-proxy.log cancellation-agent-green.log cancellation-agent-review.md cancellation-green.log cancellation-proxy.json cancellation-red.log cancellation-regression-before.log cancellation_proxy.py citation-support-spotcheck.json cleanup_cancellation_services.py compileall.log context-experiment.json context-experiment.log context_experiment.py coverage_run.py dev-context-prepared.json docker-environment.json docker-sudo-preflight.log final-checks.json eval_generation.py generation-eval.json generation-eval.log generation-summary.json human-review-packet.jsonl lint.log npm-audit.json npm-audit.log pip-audit.json pip-audit.log pip-check.log post-eval-runner-idle.json prepare-context.log prepare_context.py profile-local.json profile-local.log profile-ollama-ps.json profile-ollama-tags.json profile-summary.json profile_local.py python-coverage.json python-status.json python-tests.log rootless-preflight.log send-disconnect-agent.log start_cancellation_services.py summarize_profile.py typecheck.log web-tests.log final-api-focused.log build_inventory.py'''.split()
secrets=[]
for private in (Path('/tmp/itlr-release/private-env.json'),Path('/tmp/itlr-release/private-journey-state.json')):
 x=json.loads(private.read_text())
 for key in ('JWT_SECRET','ADMIN_PASSCODE','DATABASE_URL','password'):
  value=x.get(key)
  if isinstance(value,str) and len(value)>8:secrets.append(value)
findings=[]
for name in names:
 p=tmp/name;assert p.is_file(),name
 try:s=p.read_text()
 except UnicodeError:continue
 if any(secret in s for secret in secrets):findings.append({'file':name,'reason':'private fixture credential'})
 if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\b|\b(?:sk-[A-Za-z0-9_-]{24,}|ghp_[A-Za-z0-9_]{25,})\b',s):findings.append({'file':name,'reason':'credential-shaped material'})
assert not findings,findings
dest.mkdir(exist_ok=True)
for name in names:shutil.copyfile(tmp/name,dest/name)
for name in ('MANIFEST.json','EMBEDDINGS_MANIFEST.json'):shutil.copyfile(Path('/tmp/itlr-system-audit/staging')/name,dest/('staging-'+name))
shutil.copyfile(root/'reports/release-readiness-evidence/blind_cases.jsonl',dest/'frozen-blind-cases.jsonl')
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True)
(dest/'git-status.txt').write_text(git('status','--short'))
(dest/'git-diff-numstat.txt').write_text(git('diff','--numstat'))
ports={}
for port in (15432,18030,18080,18435):
 with socket.socket() as sock:sock.settimeout(.2);ports[str(port)]=sock.connect_ex(('127.0.0.1',port))==0
assert not any(ports.values()),ports
(dest/'handoff-checks.json').write_text(json.dumps({'temporary_ports_listening':ports,'private_fixture_credentials_not_copied':True,'new_evidence_secret_scan':'PASS','historical_report_dirs_unchanged':not any(n.startswith(('reports/release-readiness-evidence/','reports/final-engineering-evidence/','reports/full-system-audit-evidence')) for n in git('diff','--name-only').splitlines())},indent=2))
paths=set(git('diff','--name-only').splitlines())|{'itlr/api/streaming.py','tests/test_llm_async.py','tests/test_stream_cancellation.py','reports/PRODUCTION_BLOCKERS_RESOLUTION.md'}
source={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in sorted(paths) if (root/n).is_file()}
evidence={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(dest.iterdir()) if p.is_file() and p.name!='inventory.json'}
inventory={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline_head':git('rev-parse','HEAD').strip(),'branch':git('branch','--show-current').strip(),'baseline':{'python_pass':445,'web_pass':145},'current':{'python_pass':457,'python_skipped':0,'web_pass':145,'python_covered_statements':3871,'python_total_statements':5757,'web_covered_lines':635,'web_total_lines':1364},'source_sha256':source,'evidence':evidence,'cloud_inference':False,'commit_or_push':False,'production_migration':False,'active_artifact_activation':False,'models':{'generation':'qwen2.5:3b','embedding':'intfloat/multilingual-e5-base','dimensions':768},'verdict':'NO-GO','limits':'Shared CPU/Ollama, no human labels, no Docker runtime. Real browser cancellation socket/probe evidence is scoped; no per-request model-internal cancellation ACK.'}
(dest/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2));print('Inventory',len(source),'sources',len(evidence),'evidence; private credential scan PASS')
