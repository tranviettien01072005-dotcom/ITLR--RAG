# Validation evidence — 2026-10-29

These are commands run during remediation. No production deployment, paid LLM API,
external crawl, or model download was performed. Historical report numbers are not
used as current evidence.

## Environment

Python 3.14.3; FastAPI 0.162.0, httpx 0.28.1, numpy 2.5.4, pandas 3.1.0,
scikit-learn 1.9.1, pytest 9.2.0. Uvicorn 0.54.0, Bandit 1.9.4 and pip-audit 2.10.1
were installed into the existing venv after approved network escalation.
Node/npm were initially absent from PATH; root agent installed isolated Node under
`/tmp` and handles Node results in FINAL_REMEDIATION.md. PostgreSQL/Redis/Docker
commands are absent from PATH. Torch, sentence-transformers, FAISS model assets,
HF model cache and runtime `var/artifacts` are absent. No DeepSeek key is present.
Only key presence was inspected; no secret value was printed.

## Commands actually run

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/ --tb=short` | **PASS: 200 passed, 5 skipped, 1 warning in 29.40s** (outside sandbox; test count includes concurrent remediation edits available at run start) |
| `.venv/bin/python -m pytest tests/test_collect_utils.py tests/test_pipeline_fixture.py` | **PASS: 14 passed in 2.50s** |
| `.venv/bin/python -m pip check` | **PASS: No broken requirements found** |
| `.venv/bin/python -m compileall -q itlr scripts eval` | **PASS: rc=0** |
| `.venv/bin/python -m pip_audit --progress-spinner off --cache-dir /tmp/itlr-pip-audit` | **PASS: No known vulnerabilities found**, installed environment only |
| `.venv/bin/python -m bandit -r itlr scripts -lll` | Initially **FAIL** on SHA1 URL identity use. After declaring `usedforsecurity=False`, **PASS: 0 High**; 52 Low and 26 Medium remain scanner findings requiring context/triage. No rules or findings suppressed. |
| `.venv/bin/python eval/eval_fixture.py` | **PASS**, measured report `reports/fixture_eval.json` |
| PyYAML parsing `.github/**/*.yml` | **PASS**, syntax parse only; GitHub-hosted workflow execution **NOT VERIFIED** |

The five pre-existing artifact-dependent API tests are skipped because artifacts
are absent. This is not evidence that real dense retrieval or CF succeeds.
FastAPI emits a Starlette warning that httpx TestClient support is deprecated.

Sandboxed TestClient hangs were reproduced with faulthandler showing an AnyIO
blocking portal wait during TestClient startup. The same suite completes outside
the sandbox. No tests were skipped or weakened to conceal this environmental issue.

## Actual HTTP smoke

Ran `USE_OLLAMA=0 .venv/bin/python -m uvicorn itlr.api.server:app --host 127.0.0.1 --port 18000 --no-proxy-headers`
outside sandbox, then sent urllib HTTP requests to that loopback listener.

| Endpoint | Observed result |
|---|---|
| GET `/` | 200, 7401 bytes, CSP present, `X-Content-Type-Options: nosniff` |
| GET `/health` | 503, explicit missing-artifacts response |
| POST `/api/search` with `{"query":"docker"}` | 503, explicit missing-artifacts response |
| POST `/admin/reload` with no token | 403, admin API disabled |

API process shut down cleanly after smoke. UI delivery and fail-closed behavior
PASS; engine readiness and a real neural RAG query remain **NOT VERIFIED**.

## Fixture integration and evaluation

`tests/test_pipeline_fixture.py` exercises RSS fixture → extraction/quality →
SQLite → normalized catalog with license/origin → chunking → TF-IDF/BM25 model →
artifact write/reload → ranked retrieval, including expected item ID and URL.
HTTP fetching is a deterministic fixture, not a live crawl. Embeddings and LLM
are deliberately outside this test.

`eval/eval_fixture.py` uses three synthetic catalog items and three authored queries,
20 repeats each (60 requests). Labels are authored expected IDs, not human evaluation.
Recall@3, MRR@3, nDCG@3 each measured 1.0 on this trivial fixture.
Measured lexical latency p50=5.48ms, p95=7.81ms, p99=9.29ms.
Zero LLM calls/tokens means measured API spend $0. Groundedness, citation accuracy
and hallucination are null/unmeasured. This report cannot justify production RAG
quality, live DeepSeek correctness, CPU reranker changes or capacity claims.

## CI additions

`.github/workflows/ci.yml` runs Python compilation/dependency consistency/pytest,
API and fixture pipeline integration, Node lint/typecheck/test/build/npm audit,
pip-audit, Bandit High gate, and a PostgreSQL migration + login HTTP smoke job.
`.github/dependabot.yml` requests weekly Python, Node and Actions updates.
No `continue-on-error` or vulnerability ignore list exists.
The PostgreSQL service uses trust auth **only for its disposable CI database on a
runner loopback port**; no production credentials or repository secrets are required.
Application JWT/admin/database strings are generated per job. Never copy CI trust
authentication to production. Hosted Actions run and branch protection settings
remain unverified; no remote settings or public deployment were changed.

Sources for CI/security tool use:
[GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[pip-audit](https://github.com/pypa/pip-audit),
[Bandit](https://github.com/PyCQA/bandit).
