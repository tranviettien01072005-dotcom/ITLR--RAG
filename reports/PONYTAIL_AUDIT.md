# ITLR–RAG | Intelligent IT Learning Platform

## Security audit before remediation

Historical record: 2026-10-29. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

The platform collects learning resources, builds hybrid retrieval artifacts and exposes search/chat through Python and an Express/PostgreSQL application. The assumed deployment is one instance and worker per service behind an explicitly trusted reverse proxy. This record captures the pre-remediation findings; [remediation evidence](FINAL_REMEDIATION.md) records subsequent changes.

### Findings requiring correction

| Priority | Boundary | Observed defect | Required correction and consequence |
|---|---|---|---|
| Must fix | Browser rendering, `itlr/api/static/index.html` (original lines 134–318) | Query/title/model output entered `innerHTML`; `<img src=x onerror=alert(1)>` could execute. The unversioned marked CDN supplied executable code. | Use `textContent`, HTTP(S) URL validation and escape-first restricted Markdown; remove CDN/inline scripts. Otherwise external authors or model output can execute browser code. |
| Must fix | Credentials, `web/src/config/env.ts` | Missing JWT/admin/database configuration selected known development credentials. | Require explicit strong settings at startup, including development, to prevent forged sessions/admin access. |
| Must fix | Uploads, `web/src/routes/{api,social,admin}.routes.ts` | Claimed MIME types admitted HTML labeled PNG; pending files could be downloaded. | Validate signatures before persistence/extraction, bound size/resources, isolate extraction and authorize pending downloads with sandboxed responses. Otherwise malicious files reach parsers and users. |
| Must fix | Artifacts, `itlr/versioning.py` | `CURRENT.json` accepted outside/absolute paths; rollback skipped probes and file changes were undetected before pickle loading. | Confine resolved paths, hash inventory and verify before load/rollback. Pickles require trusted provenance. |
| Must fix | Rate limiting, `itlr/api/ratelimit.py`, `web/src/server.ts` | In-memory quotas multiplied across workers; Express trusted a proxy hop without deployment-specific configuration. | Require one worker/replica, reject known multiworker settings and opt in proxy trust. Otherwise quotas/address attribution can be bypassed. |
| Must fix | Verification/documentation, `README.md`, `.github/`, `docs/PROJECT_MEMORY.md` | Historical installation/tests did not describe the audit environment: model dependencies/artifacts and Node were absent, and automated CI gates were missing. | Add executable checks and distinguish historical results from available runtime evidence. |
| Should fix | Metrics, `itlr/api/server.py` | Latency dictionary keys used arbitrary request paths. | Use matched route templates and one unmatched label to bound memory growth under unknown-path traffic. |

Security boundaries took priority over launch work. Dense model runtime, live DeepSeek, PostgreSQL, browser and public deployment were unavailable at audit start. This snapshot establishes findings for remediation, without certifying the remaining repository.
