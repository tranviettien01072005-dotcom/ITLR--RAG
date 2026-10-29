# ITLR–RAG | Intelligent IT Learning Platform

## Security remediation and release evidence

Historical record: 2026-10-29. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

The remediation corrected application trust boundaries and added executable checks. Public release remained blocked by incomplete runtime, upload and integration validation. Existing uncommitted work was preserved. No commit, public deployment, paid API call, broad external crawl or user-data deletion occurred in this group.

### Findings and implementation

| Finding | Change | Verification at this checkpoint |
|---|---|---|
| F-01 XSS | `itlr/api/static/index.html` and `ui.js` use `textContent`, HTTP(S) URL allowlisting and escape-first limited Markdown. | Node vm malicious-input regression passed; real browser unverified. |
| F-02 default credentials | `web/src/config/env.ts` and `.env.example` require explicit JWT/admin/DB settings and validate production origin. | Targeted tests passed; database runtime unverified. |
| F-03 limiting/proxy | Python/web configuration and Docker/Compose require one worker/replica, reject known multiworker settings and opt in proxy trust. Full limiters reject new buckets instead of evicting active ones. | Targeted tests passed; distributed deployment unsupported. |
| F-04 uploads | Shared `web/src/middleware/uploads.ts`, API/social/admin routes and parser worker validate signature/MIME/size before persistence, authorize pending attachments and return sandbox/nosniff/private responses. | Partial: durable antivirus quarantine/content disarm absent; public uploads remained blocked. |
| F-05 CSP/CDN | Removed inline handlers, moved scripts local and added CSP/nosniff/frame/referrer headers in Python/Node. | Static/API/vm checks passed; browser unverified. |
| F-06 documentation | Updated README, AGENTS, PROJECT_MEMORY, CHANGELOG, deployment guide and ADR-009, separating current evidence from historical counts. | Recorded evidence updated. |
| F-07 CI | Added `.github/workflows/ci.yml` and Dependabot: Python, TypeScript, lint/tests/build, audit/Bandit, fixture and PostgreSQL smoke. | Implemented; hosted execution unverified. |
| F-08 artifacts | Versioning/config/engine/ANN/probe confine pointer paths, inventory SHA256, verify activation/rollback/load and pin one active directory per load. | Seven new regressions plus focused existing tests passed. |
| Additional hardening | Bounded route-template metric labels; marked stable URL SHA1 nonsecurity; removed reset-token logging; repaired extraction imports; stopped swallowing seed failures. | Targeted checks passed. |

SHA256 establishes integrity, not authenticity. Only trusted builders may write pickle artifacts/manifests. The deployment contract requires `ITLR_REQUIRE_ARTIFACT_MANIFEST=1` and read-only API artifact mounts. Trusted re-probe is required for legacy manifests; unsigned legacy-root loading remains development-only. In-process worker guards cannot detect manually launched replicas, so orchestration must enforce one replica. Horizontal scaling requires shared rate limiting such as Redis.

### Measured checks

Detailed evidence is in [validation](VALIDATION.md) and the [web security record](../web/SECURITY_REMEDIATION.md).

- Python: 200 passed, 5 pre-existing artifact-dependent skips, 1 warning, 29.40s. `pip check` and compileall passed. Sandbox TestClient hangs reproduced, while identical tests completed outside the sandbox without added skips or weakened assertions.
- Installed-environment pip-audit found no known vulnerabilities; absent model dependencies were outside its scope. Bandit reported 0 High, with 52 Low / 26 Medium requiring triage; no suppression was added.
- Static CSP/header/metrics/worker checks: 4 passed; preceding API/static focused run: 12 passed.
- Loopback Uvicorn: UI HTTP 200 with CSP/nosniff, readiness/search 503 for missing artifacts, admin 403 without token. The process shut down cleanly.
- Web typecheck/lint/build passed; lint retained 20 explicit-any warnings. Independent tests: 22 passed / 6 files; V8 line coverage 9.34%, insufficient for broad correctness claims.
- Dependency audit reached 0 vulnerabilities from an initial 18, including 12 High / 1 Critical. Multer/Zod/Nodemailer were upgraded and unsafe/unfixable Office parser dependencies removed; Office/video uploads fail closed. Normal isolated `/tmp` `npm ci` passed: 322 packages added, 323 audited, zero vulnerabilities, no peer-dependency bypass.
- Final `git diff --check` passed. A root-directory npm build failed ENOENT because no root package.json exists; the build passed from `web/`.

### Integration and evaluation scope

| Component | Evidence | Limit |
|---|---|---|
| Crawler → SQLite → provenance catalog → chunks → lexical index → reload → query | `tests/test_pipeline_fixture.py` passed | Deterministic HTTP fixture, without live crawling |
| Python HTTP/UI and security failure paths | Loopback HTTP passed | Did not fabricate engine readiness |
| E5 embeddings, FAISS active index, RRF dense fusion | Unverified at this checkpoint | Torch/sentence-transformers/cache/artifacts absent |
| Reranker/MMR host performance | Unverified | Historical algorithm/benchmark unchanged |
| Live DeepSeek grounding/citations | Unverified | Key absent, no paid request |
| Adapter timeout/retry/fallback/prompt boundaries | Available mock/unit checks passed | No live-provider proof |
| Authenticated PostgreSQL flows | Unverified locally | PostgreSQL unavailable; hosted CI smoke pending |
| Browser visual/DOM integration | Unverified | Node vm is narrower; no configured browser tool |
| Docker Compose startup | Unverified | Docker unavailable; loopback defaults/health probes documented |

`python eval/eval_fixture.py` generated [fixture_eval.json](fixture_eval.json) using three synthetic items, three authored expected IDs and 60 lexical calls. Recall@3/MRR@3/nDCG@3 were each 1.0; p50/p95/p99 were 5.48/7.81/9.29ms. This establishes reproducible fixture plumbing. Embeddings/reranker/generation were excluded. Groundedness, citation accuracy and hallucination are null/unmeasured; LLM calls/tokens=0 and API spend=$0. Historical catalog benchmarks were not rerun. No human labels were available; synthetic, simulated and rule-based results are separate from human evaluation.

### Workflow and review

The [inventory](SKILLS_INVENTORY.md) records exactly 25 installed Addy skills. Applied workflows covered routing (`using-agent-skills`), official platform contracts (`source-driven-development`), reproduction (`debugging-and-error-recovery`), trust boundaries (`security-and-hardening`), regression tests (`test-driven-development`), caller/edge review (`code-review-and-quality`), gates (`ci-cd-and-automation`), measurement (`performance-optimization`), bounded metrics/liveness (`observability-and-instrumentation`), ADR-009/runbooks (`documentation-and-adrs`), dirty-tree preservation (`git-workflow-and-versioning`), release gates (`shipping-and-launch`), independent artifact/web/CI review (`doubt-driven-development`) and verified slices (`incremental-implementation`). Unrelated idea/migration/interview workflows were not activated.

Ponytail Ultra audit and post-group review are recorded in [PONYTAIL_AUDIT.md](PONYTAIL_AUDIT.md) and [PONYTAIL_REVIEW.md](PONYTAIL_REVIEW.md). Claude-Mem was unavailable; no memory save was claimed. Repository memory files were updated.

Original technical references: [MDN textContent](https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent), [Express proxy trust](https://expressjs.com/en/guide/behind-proxies/), [Node worker limits](https://nodejs.org/api/worker_threads.html), [OWASP upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html). These links record the sources used at remediation time, without a fresh source-verification claim.

### Remaining gates and reproduction

1. Install complete model dependencies/cache on a suitable host; trusted build/probe/activate and actual neural queries/citations must pass, including the five skipped integration tests.
2. Validate PostgreSQL migrations/login/upload authorization and hosted CI; triage remaining scanner findings.
3. Verify durable scanning/quarantine and OS/container resource bounds before public arbitrary-document uploads; signatures alone are insufficient.
4. Exercise browser security/rendering and Docker/Compose startup/health.
5. Run live DeepSeek evaluation only with an authorized key, recording actual tokens/cost and answer quality. Templates/mocks do not establish this result.

The following historical commands install dependencies, build artifacts and migrate a configured database. They were documented for an intended target environment, rather than executed by this editorial update.

```bash
. .venv/bin/activate
pip install -r requirements.txt
# Configure .env from .env.example; keep actual secrets outside Git.
python scripts/build_all_v2.py --online  # trusted build; explicit model downloads required
uvicorn itlr.api.server:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
# /live = process; /health = engine readiness
python -m pytest tests/
python eval/eval_fixture.py
# Full evaluation after the target-host build:
python eval/eval_v2_real.py
python eval/eval_generation.py --llm  # only with an authorized DEEPSEEK_API_KEY
# Separate web terminal; configure private web/.env credentials first:
cd web
npm ci
npm run migrate
npm run build
npm start
# /health = process; /ready = PostgreSQL
```

Later on 2026-10-29, local E5/Qwen installation, neural build and API smoke passed; [LOCAL_MODELS.md](LOCAL_MODELS.md) supersedes only the earlier missing-model blocker for that checkout. It does not resolve every gate in this record.
