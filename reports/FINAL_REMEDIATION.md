# ITLR remediation — 2026-10-29

**Release verdict: NOT PRODUCTION-READY.** Code fixes and local regression checks are real;
full neural RAG, PostgreSQL user flows, real browser and hosted CI are not verified.
Existing uncommitted work was preserved. No commit, public deployment, paid API call,
broad external crawl or deletion of user data was performed.

## Findings and implementation

| Finding | Files / behavior | Status |
|---|---|---|
| F-01 XSS | `itlr/api/static/index.html`, new `ui.js`: textContent cards/options/prompts, HTTP(S) URL allowlist, escape-first limited Markdown; Node vm malicious-input regression | PASS targeted regression; real browser NOT VERIFIED |
| F-02 default credentials | `web/src/config/env.ts`, `.env.example`: JWT/admin/DB explicitly required, production origin validated | PASS targeted tests; database runtime NOT VERIFIED |
| F-03 limiting/proxy | `itlr/api/ratelimit.py`, web env/server, Docker/Compose: one worker/replica, known multiworker env rejected, proxy trust opt-in, full limiter rejects rather than evicting active buckets | PASS targeted tests; distributed deployment unsupported |
| F-04 uploads | shared `web/src/middleware/uploads.ts`, API/social/admin routes, parser worker: signatures/MIME/size checks before persistence, pending attachment authorization, sandbox/nosniff/private responses | PARTIAL: no durable AV quarantine/content disarm; public uploads remain release blocker |
| F-05 CSP/CDN | local external scripts, no inline script handlers, response CSP/nosniff/frame/referrer headers in Python and Node | PASS static/API/vm checks; browser NOT VERIFIED |
| F-06 documentation | README, AGENTS, PROJECT_MEMORY, CHANGELOG, deployment guide and ADR-009 updated; historical counts kept distinct from current evidence | PASS current evidence recorded |
| F-07 CI | `.github/workflows/ci.yml`, Dependabot: Python, TypeScript, lint/tests/build, audit/Bandit, fixture and PostgreSQL smoke | Implemented; hosted execution NOT VERIFIED |
| F-08 artifacts | versioning/config/engine/ANN/index probe: pointer confinement, SHA256 inventory, activation/rollback/load verification, pin one active directory per load | PASS 7 new regressions + focused existing tests |
| Additional | route-template metric labels prevent arbitrary path memory growth; stable URL SHA1 explicitly nonsecurity; reset token logging removed; broken web extraction imports repaired; seed failure no longer swallowed | PASS targeted checks; see validation evidence |

SHA256 is integrity checking, not signing: only trusted builders may write pickles/manifests.
Production must use `ITLR_REQUIRE_ARTIFACT_MANIFEST=1` and read-only API artifact mounts.
Legacy manifests require trusted re-probe; unsigned legacy root loading remains development-only.
In-process limiter guards do not detect arbitrary manually launched replicas: orchestration must
keep one replica. Redis/shared rate limiting is required before scaling horizontally.

## Actual checks

Full command evidence: [VALIDATION.md](VALIDATION.md). Web evidence: [SECURITY_REMEDIATION](../web/SECURITY_REMEDIATION.md).

- Python full suite: **200 passed, 5 pre-existing artifact-dependent skips, 1 warning**, 29.40s.
- `.venv/bin/python -m pip check`: PASS; compileall: PASS.
- Installed-environment pip-audit: no known vulnerabilities. This does not audit absent model dependencies.
- Bandit High gate: 0 High. 52 Low/26 Medium scanner findings still require triage; no suppression added.
- Static CSP/header/metrics/worker tests: 4 passed; preceding API/static focused run: 12 passed.
- Real loopback Uvicorn HTTP: UI 200 + CSP/nosniff; readiness/search 503 missing artifacts; admin 403 without token. Process shut down cleanly.
- Web `npm run typecheck`, `npm run lint`, `npm run build`: PASS; lint retains 20 existing any warnings.
- Independent `npm test`: **22 passed / 6 files**; V8 line coverage **9.34%**, too narrow for full web correctness claims.
- Dependency upgrade audit reports **0 vulnerabilities**, after initial 18 (12 High/1 Critical). Multer/Zod/Nodemailer upgraded; unsafe/unfixable Office parser dependencies removed. Office/video uploads now fail closed. Clean normal `npm ci` in isolated /tmp: PASS (322 packages added, 323 audited, zero vulnerabilities), without peer-dependency bypass.
- Git diff whitespace check: PASS at final review.
- One npm build attempt from repository root failed ENOENT (no root package.json); rerun from `web/` passed.

Sandbox TestClient hangs were reproduced; identical tests completed outside sandbox.
No new skips or relaxed assertions were used to obtain a passing result.

## End-to-end and measurement scope

| Component | Status | Evidence / limit |
|---|---|---|
| Crawler → SQLite → catalog/provenance → chunks → lexical index → reload → query | PASS fixture | `tests/test_pipeline_fixture.py`; HTTP fixture, not live crawl |
| Python HTTP/UI delivery/security failure modes | PASS | actual loopback HTTP; no fake engine success claimed |
| E5 embeddings, FAISS active production index, RRF dense fusion | NOT VERIFIED | Torch/sentence-transformers/model cache and runtime artifacts absent |
| Reranker/MMR target-host performance | NOT VERIFIED | no algorithm changed from historical benchmark |
| DeepSeek live grounding/citations | NOT VERIFIED | key absent; no paid request sent |
| Adapter timeout/retry/fallback and prompt boundaries | PASS available tests | mock/unit evidence only; not live provider proof |
| PostgreSQL-backed authenticated web flows | NOT VERIFIED locally | PostgreSQL unavailable; CI smoke added, hosted run pending |
| Browser visual/DOM integration | NOT VERIFIED | no configured browser tool; Node vm is a narrower regression |
| Docker Compose startup | NOT VERIFIED | Docker unavailable; safe loopback defaults and health probes documented |

`python eval/eval_fixture.py` produced [fixture_eval.json](fixture_eval.json): three synthetic
items, three authored expected IDs, 60 lexical calls. Recall@3/MRR@3/nDCG@3 each 1.0;
p50/p95/p99 = 5.48/7.81/9.29ms. This trivial fixture proves reproducibility plumbing only.
No embeddings/reranker/generation participate. Groundedness, citation accuracy and hallucination
are **null/unmeasured**. LLM calls/tokens=0, API spend=$0. Historical real-catalog metrics
were not rerun and are not current release evidence. Human labels remain unavailable;
synthetic, simulated and rule-based results must not be described as human evaluation.

## Skills and Ponytail

Inventory: [SKILLS_INVENTORY.md](SKILLS_INVENTORY.md), exactly 25 installed Addy skills.
Applied only relevant workflows: using-agent-skills (routing), source-driven-development
(official platform contracts), debugging-and-error-recovery (reproduce and localize),
security-and-hardening (trust boundaries), test-driven-development (regressions),
code-review-and-quality (caller/edge review), ci-cd-and-automation (executable gates),
performance-optimization (measurement before changing reranking), observability-and-instrumentation
(bounded route labels/liveness), documentation-and-adrs (ADR-009/runbooks),
git-workflow-and-versioning (preserve dirty tree), shipping-and-launch (release gates),
doubt-driven-development (independent artifact/web/CI reviews), incremental-implementation
(verify slices). Ponytail **ultra**, audit before fixes and review after security groups:
[PONYTAIL_AUDIT](PONYTAIL_AUDIT.md), [PONYTAIL_REVIEW](PONYTAIL_REVIEW.md), web review above.
Unrelated idea/migration/interview skills were not activated just to increase the count.
Claude-Mem tools were unavailable; no memory save was claimed. Repo memory files were updated.

Official references used: [MDN safe text rendering](https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent),
[Express proxy trust](https://expressjs.com/en/guide/behind-proxies/),
[Node worker limits](https://nodejs.org/api/worker_threads.html),
[OWASP uploads](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

## Remaining release gates and run commands

1. Install complete declared model dependencies/cache in a suitable target host; trusted build/probe/activate and verify real neural queries and citations. Five skipped tests must run there.
2. Verify PostgreSQL migrations/login/upload authorization in the real web runtime and execute hosted CI. Triage remaining static scanner findings.
3. Add/verify durable scanning/quarantine and OS/container resource bounds before accepting public arbitrary documents. Signature checks alone are insufficient.
4. Run browser security and rendering flows; Docker image/Compose health startup checks.
5. With an authorized key, run DeepSeek live evaluation; record actual tokens/cost and grounded answers. Do not treat template/mocks as this proof.

```bash
. .venv/bin/activate
pip install -r requirements.txt
# Configure .env from .env.example; keep actual secrets outside git.
python scripts/build_all_v2.py --online  # trusted build; explicit model downloads required
uvicorn itlr.api.server:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
# /live = process; /health = engine readiness
python -m pytest tests/
python eval/eval_fixture.py
# Full target-host evaluation, after build:
python eval/eval_v2_real.py
python eval/eval_generation.py --llm  # only with valid authorized DEEPSEEK_API_KEY
# Web: separate terminal, configure web/.env with private credentials first:
cd web
npm ci
npm run migrate
npm run build
npm start
# /health = process; /ready = PostgreSQL
```

## Subsequent local model verification (2026-10-29)

E5/Qwen installed and real neural build/API smoke now PASS in this checkout.
See [LOCAL_MODELS.md](LOCAL_MODELS.md) for evidence and limits. This supersedes
the earlier missing-model blocker only; it does not establish production readiness.
