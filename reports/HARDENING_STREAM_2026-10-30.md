# Hardening continuation — 2026-10-30

Repository: `main`, HEAD `f8ad595`; working tree initially clean. This is a scoped
continuation, not completion of the repository-wide production certification.
No commits, paid calls, migrations, runtime artifact activation or data edits.

## IMPLEMENTED: P1 generation stream compatibility

`itlr/chatbot/llm_client.py` indexed `chunk.choices[0]` unconditionally. A terminal
usage-only chunk with `choices=[]` raised IndexError after answer text had already
been delivered, which became an LLMError and falsely reported a broken stream.
The shared client now ignores chunks without completion choices. Provider order,
retry policy, resource closure and public iterator contract remain unchanged.
Usage-only chunks are not yet incorporated into streaming cost accounting.

Scope inspected: shared client, chatbot streaming adapter, existing client tests,
retrieval service, chunk index, engine thresholds, chunker and lexical evaluator.
No API/schema/index/pickle contract or UI change; no new dependency.

## TESTED: Before vs After

| Check | Before | After |
|---|---|---|
| Usage-only terminal chunk, fake DeepSeek/OpenAI SDK | 2 FAIL | 2 PASS |
| Shared LLM client suite | regression reproduced separately | 34 PASS |
| Web suite | historical results not reused | 124 PASS, 25 files, lines 45.01% |
| Web typecheck/lint/build | not rerun before change | completed successfully |
| Python full suite | 378 PASS / 6 FAIL (default Windows encoding) | 386 PASS / 0 skip, UTF-8, coverage 65% rounded |
| pip check / compileall | not measured before | PASS |
| npm audit --offline | not measured before | 0 vulnerabilities in available cached data |

Commands and raw evidence: `hardening-red.log`, `hardening-green.log`,
`hardening-baseline.log`, `hardening-web.log`. Windows PowerShell blocks npm.ps1;
use npm.cmd. Python 3.12 defaults to cp1252 here: six baseline failures were
UnicodeEncodeError/UnicodeDecodeError in Vietnamese CLI output and UTF-8 fixture
reads. Use `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` when running the documented
Linux checks on this Windows environment. No assertions or quality gates removed.

Final full suite: `hardening-utf8.log`, 386 passed in 188.40s, one pytest cache
permission warning; exit code 0. This includes the two new stream regressions.
Focused portability check: 21 PASS (`hardening-portability-confirm.log`);
client plus Markdown-link review: 35 PASS (`hardening-review.log`).
The outside-sandbox attempt failed with 4 failed / 253 passed / 129 setup errors:
that process could not access the account's pytest temporary directory, and still
used the default Windows encoding. See `hardening-final.log`; despite its name it
is an unsuccessful diagnostic attempt, not the final validation result.
The first focused attempt also used a nonexistent temporary parent (19 PASS /
2 setup errors); creating the parent and using a fresh directory resolved it.
Only the UTF-8 sandbox run is the successful final full-suite gate.

## NOT MEASURED: neural and generation quality

Fresh lexical-only result in `hardening-lexical.json`: 118 real snapshot items,
8 engineer-authored single-annotator qrels, 160 requests, Recall@5 1.0,
MRR@5 0.9375, nDCG@5 0.953866. p50/p95/p99 75.66/131.49/153.36 ms,
throughput 11.99 requests/s. Measured while other checks were active; latency is
not an isolated before/after benchmark and no performance improvement is claimed.
Precision@K, memory, full-corpus neural/reranker evaluation and generation
faithfulness/relevance/hallucination remain NOT MEASURED. No threshold, model,
chunking, RRF weight or FAISS index change is justified by this experiment.

## BLOCKED / remaining work

Docker and psql absent from PATH; no staging HTTPS/browser/backup-restore run.
Bandit and pip-audit are not installed in this venv; previous clean audits are
historical evidence only. Offline npm audit is not a fresh registry advisory scan.
Real API provider compatibility and Linux lifecycle runtime require separate
verification. Current disposition remains NO-GO for production certification.
