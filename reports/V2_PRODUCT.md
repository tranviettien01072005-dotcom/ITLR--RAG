# ITLR–RAG | Intelligent IT Learning Platform

## V2 platform implementation

Historical record: 2026-10-29. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

This implementation followed authorized priorities 1–4 and the recorded commit message `itrl v2`. It introduced a curated real-source catalog, validated source references, streamed chat and persisted learning workflows.

### Delivered behavior

- Collected 128 official Python/MDN/Docker pages with robots checks and rate limits, yielding 118 distinct normalized resources. Stored source links, attribution/license, retrieval dates, original-source hashes and normalized-snapshot hashes. Included an offline snapshot importer. An authored allowlist and automated availability checks selected resources; this was not human relevance evaluation.
- Added real-only catalog/index builds while preserving the legacy synthetic CSV separately. Full source text survives catalog → item_list → chunks. Chunk whitespace can be normalized, so excerpts need not be byte substrings of original source HTML/text.
- Validated retrieved citation IDs; missing, unknown or synthetic references trigger insufficient-evidence responses. Metadata declares `semantic_grounding: not_verified`; valid IDs alone do not establish entailment.
- Implemented SSE across Python → authenticated Express → browser. Sources precede generation; streamed tokens remain provisional until an authoritative final response replaces them. Cancellation, upstream errors, stream validation and source/first-token/total timing are handled. Owner-scoped final history retains source metadata, cards and valid citation links after reload.
- Added account learning goals, a server-scored 3-question orientation, ordered real-resource roadmaps and PostgreSQL enrollment save/progress. The diagnostic is rule-based and confers no certification. The Python roadmap regression orders introduction/controlflow → modules/errors → CSV/JSON.

### Verification recorded

| Check | Evidence |
|---|---|
| Python regression | 215 passed / 5 existing legacy-artifact-location skips in 75.14s; subsequent focused snapshot/source tests passed |
| Web | 58 tests / 14 files passed; typecheck/build passed; lint 0 errors / 20 existing warnings |
| Dependency/security audit | npm audit 0 vulnerabilities; Bandit 0 High, with 58 Low / 28 Medium pending contextual triage. pip-audit found no known vulnerabilities for auditable dependencies but skipped Torch 2.15.0+cpu, absent from PyPI. |
| PostgreSQL | Real PostgreSQL 16 rootless container; random credentials only in `/tmp`; migrations and 118-row upsert passed. No deployed database/account was touched. |
| Chromium journey | Registration → diagnostic → six real roadmap resources → save 40% → reload persistence passed. Anonymous access redirected to login; 390px mobile view had no horizontal overflow; `pageErrors=[]`. |

Screenshots: `reports/learning-*.png`; journey evidence: `journey_browser_smoke.json`. The original checkpoint deferred actual Qwen SSE/updated-source-index evidence and a final consolidated Python count, without appending those results here. The figures above remain the recorded evidence; consult current validation for later checkpoints.

### Reproduction

These commands import/build catalog artifacts and migrate/synchronize the configured database; use an intended local environment and private credentials.

```bash
python scripts/import_curated_snapshot.py   # validated offline snapshot, preserving IDs
# Optional bounded refresh: python scripts/collect_curated.py --refresh
HF_HOME="$PWD/var/hf" DISABLE_RERANKER=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  python scripts/build_all_v2.py --real-only
python scripts/export_web_catalog.py
# Configure web/.env with private DB/JWT/admin credentials first.
cd web
npm ci
npm run migrate
npm run sync
npm run build
npm start
```

See [local model setup](../deploy/LOCAL_MODELS.md) for Qwen/Ollama/API configuration. Web routes are `/learning` and `/chat`. Model binaries, runtime databases, secrets, node_modules and generated coverage remain excluded from Git. Hosted CI execution is separate from local evidence.

Human-rated RAG quality, live DeepSeek, distributed rate limiting and arbitrary-upload malware quarantine/native isolation remained unresolved. No paid API call or public deployment occurred, and this checkpoint did not approve public release.
