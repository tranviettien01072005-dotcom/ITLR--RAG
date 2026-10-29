What this change does: It closes browser rendering, credentials, upload and artifact trust boundaries and adds executable CI gates. It preserves the existing uncommitted application work. Expected deployment is one process and one replica per service.

## Must fix before release

1. **Full dense retrieval cannot be verified in this environment** (`requirements.txt`, runtime `var/artifacts/`).
   - **What this is:** E5/FAISS plus reranker drive the production search path.
   - **Problem:** Model dependencies/cache and artifacts are missing. Fixture lexical tests cannot establish production quality or latency.
   - **Fix:** Install declared dependencies, run trusted V2 build/probe and real query evaluation in the target runtime.
   - **If we skip it:** A release can pass unit tests and still return 503 for search/chat.
2. **Upload scanning remains incomplete** (`web/src/middleware/uploads.ts`).
   - **What this is:** Shared validation checks actual file signatures before route persistence.
   - **Problem:** Signatures do not detect embedded malware; worker heap caps do not bound every native allocation.
   - **Fix:** Keep unsupported formats rejected; gate public document upload launch on resource isolation and scanning policy.
   - **If we skip it:** Crafted accepted documents can still attack downstream parsers/clients.

Verdict: Do not ship publicly; see FINAL_REMEDIATION.md for measured gates and remaining blockers.
Not checked: Browser rendering, real PostgreSQL user flows, live DeepSeek and full dense runtime. Node vm and mock API regressions cover specific boundaries only.
