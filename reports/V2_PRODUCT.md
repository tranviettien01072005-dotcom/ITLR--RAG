# Product V2 implementation — 2026-10-29

User-authorized priorities1–4, commit message `itrl v2`.

-128 official Python/MDN/Docker pages collected with robots checks/rate limits;118 distinct
  resources after normalization. Source links, attribution/license, retrieval dates, original
  source hash and normalized snapshot text hash retained. Snapshot and offline importer included.
  Selection is an authored allowlist with automated availability checks, not human evaluation.
-Real-only catalog/index build; synthetic legacy CSV preserved separately. Full source text
  preserved across catalog→item_list→chunks. Chunk whitespace may be normalized; excerpts are
  indexed passages, not guaranteed byte substrings of the original HTML/text.
-Backend validates retrieved citation IDs, rejects missing/unknown/synthetic references and
  uses explicit insufficient-evidence responses. ID validity does not establish semantic entailment;
  response metadata states `semantic_grounding: not_verified`.
-True SSE through Python→authenticated Express→browser. Sources sent before generation; tokens
  provisional until authoritative final replaces them. Cancellation, upstream failure, stream
  validation and source/first-token/total timing are implemented. Owner-scoped final history
  stores source metadata; source cards and valid citation links restore after reload.
-Account learning goal + server-scored3-question orientation, ordered roadmap using real resources,
  saved/progress in PostgreSQL enrollments. Diagnostic is rule-based, not a certification.
  Python roadmap regression now starts introduction/controlflow → modules/errors → CSV/JSON.

## Verification executed

- Python full regression:215 passed,5 existing legacy-artifact-location skips (75.14s), plus
  subsequent focused snapshot/source tests PASS. Final consolidated count recorded below.
- Web58 tests/14 files PASS; typecheck/build PASS; lint0 errors/20 existing warnings.
- npm audit:0 vulnerabilities. Bandit:0 High (58 Low/28 Medium still need contextual triage).
- pip-audit reported no known vulnerabilities for auditable dependencies, but explicitly skipped
  Torch2.15.0+cpu as absent on PyPI; CPU wheel audit remains a limitation, not a clean-all claim.
- Real PostgreSQL16 rootless container, random credentials in/tmp only; migrations and118-row
  upsert PASS. No production database or account was touched.
- Actual Chromium registration→diagnostic→six real roadmap resources→save40%→reload persisted;
  anonymous access redirects to login; mobile390px has no horizontal overflow; pageErrors=[] .
  Screenshots and JSON evidence in reports/learning-*.png and journey_browser_smoke.json.
- Actual Qwen SSE/updated-source index verification is recorded below after completion.

Remaining release limits: no human-rated RAG quality, no DeepSeek live, no distributed limiter,
no arbitrary-upload malware quarantine/native resource isolation. This V2 commit is not a claim
that all public-production release gates are met. No paid API or public deployment performed.

## Reproduce

```bash
python scripts/import_curated_snapshot.py   # offline validated source snapshot; preserve IDs
# Or bounded refresh: python scripts/collect_curated.py --refresh
HF_HOME="$PWD/var/hf" DISABLE_RERANKER=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  python scripts/build_all_v2.py --real-only
python scripts/export_web_catalog.py
# Configure web/.env with private DB/JWT/admin credentials, then:
cd web
npm ci
npm run migrate
npm run sync
npm run build
npm start
```

Qwen/Ollama and API setup: deploy/LOCAL_MODELS.md. Web exposes/learning and/chat.
Model binaries, runtime databases, secrets, node_modules and generated coverage are excluded
from git. GitHub-hosted CI execution is separately reported from local checks.
