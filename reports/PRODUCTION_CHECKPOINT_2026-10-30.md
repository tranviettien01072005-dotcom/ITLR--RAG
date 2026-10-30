# Production preparation checkpoint

This checkpoint does not establish production readiness. The user subsequently
requested no more installation and deferred runtime tests in favor of deployment
configuration and code structure work. No cloud deployment, paid LLM call, migration
or runtime index activation occurred.

## Architecture before / after

Before: API/refresh-only Compose, separate Web Dockerfile, automatic migration/seed
on every Web container start, Express wiring and listener in server.ts.

After: existing Compose retained; opt-in compose.production.yml adds Caddy HTTPS,
Web, API and PostgreSQL with persistent volumes. Only proxy ports are published.
Web app composition lives in app.ts; server.ts owns listening and bounded shutdown.
Migration/catalog sync are explicit release operations. Follow deploy/PRODUCTION.md.
No schema/API/artifact renaming and no Python module moves. No dependency removed
or added to project manifests. Browser/server SSE decoding was hardened earlier.

The static Python inventory in production_static_imports.json parsed 61 modules,
with no syntax errors. It resolves absolute imports only, not a complete dynamic
dependency graph. The largest modules remain chatbot.py (1516 lines) and
recommender.py (927 lines); splitting them based on size alone was rejected.

## Executed checks before the deployment/lifecycle edits

| Check | Result |
|---|---|
| UTF-8 truncated stream regressions | RED: 2 failures; GREEN after fix |
| Complete oversized browser SSE frame | RED: 1 failure; GREEN after fix |
| Web suite including UTF-8 fragmentation | PASS: 70 tests, 15 files; line coverage 27.12% |
| Web typecheck/build | PASS before app/lifecycle split |
| Web lint | PASS: 0 errors, 20 existing warnings before split |
| npm lockfile audit | PASS: 0 vulnerabilities |
| Python full suite | FAIL: 4 collection errors, unavailable fcntl on Windows; repeated outside sandbox |
| Selected LLM/citations/chunks/BM25/collection tests | PASS: 46; one sandbox cache permission warning |
| Python compileall | PASS before latest Web changes |
| pip check | PASS |
| Bandit high severity gate | PASS; production_bandit.json retains lower-severity findings |
| pip-audit | Initial FAIL in venv pip 25.0.1; PASS after local pip upgrade to 26.2.2 |
| Lexical fixture evaluation | PASS: 3 synthetic items, 60 requests; Recall/MRR/nDCG@3=1.0; p95=9.13 ms |

Fixture results are in production_fixture_eval.json and are not neural RAG quality
or a performance improvement measurement. Generation quality remains null.

## Current release gates

Latest Compose/Caddy configuration, process shutdown, app split and release jobs:
NOT VERIFIED at runtime; tests intentionally deferred by user. Source diff and
configuration paths reviewed only. No new claim of test PASS applies to these edits.
Docker, HTTPS/cert renewal, Google Cloud VM, PostgreSQL release/restore drill,
authenticated browser/SSE, cross-service index/catalog recovery, real reranker,
full-corpus benchmarks and generation faithfulness remain NOT VERIFIED.

Known limits: single replica/local Linux locks; API container remains base-image
user; template image tags need reviewed digest pinning; alert delivery and off-host
encrypted backups require operator configuration. PostgreSQL/catalog/artifacts have
no shared atomic transaction: maintenance and matching rollback pairs are required.
