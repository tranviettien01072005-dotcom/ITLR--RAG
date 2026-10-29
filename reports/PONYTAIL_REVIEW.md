# ITLR–RAG | Intelligent IT Learning Platform

## Security remediation review

Historical record: 2026-10-29. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

The reviewed change tightened rendering, credentials, upload and artifact trust boundaries and added executable CI gates. Existing uncommitted application work was preserved. The deployment assumption remained one process and replica per service.

### Open release gates

| Gate | Evidence gap | Required follow-up |
|---|---|---|
| Dense retrieval (`requirements.txt`, `var/artifacts/`) | E5/FAISS/reranker dependencies, cache and artifacts were absent in the review environment. Lexical fixtures cannot establish neural quality or latency; search/chat may still return 503. | Install declared dependencies, perform trusted V2 build/probe and evaluate actual queries on the target runtime. The subsequent [local model verification](LOCAL_MODELS.md) addresses part of this historical gap. |
| Upload isolation (`web/src/middleware/uploads.ts`) | Shared validation verifies signatures, but embedded malware remains possible. Worker heap caps do not cover all native allocations. | Reject unsupported formats and verify scanning policy/resource isolation before public document uploads. |

The recommendation at this checkpoint was to withhold public release. See [FINAL_REMEDIATION.md](FINAL_REMEDIATION.md) for measured gates and unresolved blockers. Browser rendering, PostgreSQL user flows, live DeepSeek and full dense runtime were unverified; Node vm and mocked API checks established only specific regressions.
