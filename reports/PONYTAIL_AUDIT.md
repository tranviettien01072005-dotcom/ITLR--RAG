What this repo does: ITLR collects learning resources, builds hybrid retrieval artifacts and exposes search and grounded chat through Python and a separate Express/PostgreSQL web app. Assumed load: one instance and one worker per service behind an explicitly trusted reverse proxy.

## Must fix

1. **Untrusted text becomes executable HTML** (`itlr/api/static/index.html`, original lines 134–318).
   - **What this is:** Search and streamed chat display external content.
   - **Problem:** `<img src=x onerror=alert(1)>` in query/title/model output enters innerHTML. The unversioned marked CDN is trusted to execute.
   - **Fix:** Build cards with textContent, validate HTTP(S) links, escape before restricted Markdown formatting, remove CDN and inline scripts.
   - **If we skip it:** A resource author or model response can run browser code.
2. **Default credentials let deployments start insecurely** (`web/src/config/env.ts`).
   - **What this is:** Web startup configures authentication and PostgreSQL.
   - **Problem:** Missing JWT/admin/database settings select development credentials.
   - **Fix:** Require explicit strong values at startup, including development.
   - **If we skip it:** Sessions or administrator access can be forged with known values.
3. **Upload metadata is treated as proof** (`web/src/routes/api.routes.ts`, `social.routes.ts`, `admin.routes.ts`).
   - **What this is:** Users upload documents and media.
   - **Problem:** HTML with a PNG MIME label reaches processing/storage; pending files can be downloaded.
   - **Fix:** Shared signature checks before persistence/extraction, size budgets, isolated extraction, approval checks and sandboxed responses.
   - **If we skip it:** Malicious files reach parsers and other users.
4. **Artifact pointer can escape the trusted root** (`itlr/versioning.py`).
   - **What this is:** Startup follows CURRENT.json then loads Python pickles.
   - **Problem:** An absolute/outside directory is accepted; rollback skips probe validation; file changes are undetected.
   - **Fix:** Constrain resolved paths, hash the file inventory, verify before load and rollback.
   - **If we skip it:** Corrupted or substituted executable pickle data can be loaded.
5. **Process-local rate limits multiply with workers** (`itlr/api/ratelimit.py`, `web/src/server.ts`).
   - **What this is:** Both services limit requests in process memory.
   - **Problem:** Multiple workers multiply quotas; Express trusts a proxy hop without deployment-specific trust.
   - **Fix:** Explicit single worker/replica deployment and fail on known multiworker settings; opt in trusted proxies.
   - **If we skip it:** Clients bypass quotas and spoof addresses.
6. **Runtime and verification differ from documentation** (`README.md`, `.github/`, `docs/PROJECT_MEMORY.md`).
   - **What this is:** Installation and quality checks describe earlier runs.
   - **Problem:** Current environment lacks model dependencies/artifacts and Node; no automated CI gates exist at audit start.
   - **Fix:** Add executable gates and document actual results and unavailable components separately.
   - **If we skip it:** Historical tests are mistaken for release evidence.

## Should fix

7. **Metric labels grow with arbitrary paths** (`itlr/api/server.py`).
   - **What this is:** A dictionary records latency for each request path.
   - **Problem:** Unique unknown paths retain unlimited entries.
   - **Fix:** Use matched route templates and one unmatched label.
   - **If we skip it:** A scanner can grow service memory without calling retrieval.

Verdict: Fix security boundaries first; full launch remains gated on real runtime validation and dependency audit.
Not checked: Full dense model runtime, live DeepSeek, real PostgreSQL, browser and public deployment were unavailable at audit start. This is the pre-remediation source audit snapshot; subsequent results are in FINAL_REMEDIATION.md.
