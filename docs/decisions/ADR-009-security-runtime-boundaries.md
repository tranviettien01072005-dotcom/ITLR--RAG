# ADR-009: Explicit runtime trust boundaries

Product: **ITLR–RAG | Intelligent IT Learning Platform**. Accepted for remediation, 2026-10-29.
Current operations and evidence: [deployment](../../deploy/DEPLOY.md),
[validation](../../reports/VALIDATION.md), [web remediation](../../web/SECURITY_REMEDIATION.md).

## Context and decision

Catalog data, LLM output, upload bytes and forwarded headers cross trust boundaries.
Static UI renders text with `textContent` and permits HTTP(S) catalog links only. Markdown
supports escaped emphasis/code/newlines; raw HTML and Markdown links are disabled. JavaScript
uses local external files; CSP `script-src self` forbids inline execution.
[MDN documents the textContent contract](https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent).

Web requires explicit JWT/admin/database credentials in development as well as deployment.
Uploads remain in private request memory until shared signature checks pass. Access to pending
files requires ownership or privileged access. Unsupported formats fail closed. Signature checks
are neither antivirus nor durable quarantine; parser isolation and resource limits need host validation.

Rate limiters remain in memory. One process and one replica per service are required; startup
rejects known multiworker settings. API defaults ignore proxy headers; web proxy trust is opt-in.
Multiple replicas require shared limiting and coordination. Follow
[Express proxy configuration](https://expressjs.com/en/guide/behind-proxies/) for actual proxy peers.

Artifacts are executable inputs from trusted builders. Pointers stay inside the configured root.
SHA256 inventories are checked before engine unpickle and activation/rollback; strict mode requires
a manifest, and each engine load pins a directory. Hashes detect changes but cannot authenticate
files against an attacker who can rewrite both file and manifest. API mounts must be read-only.

## Consequences and limits

These boundaries reduce specific risks without establishing a deployment security certification.
Keep third-party rights, fail-closed configuration and upload restrictions. Validate current dense
retrieval, generation, dependency exposure and target-host behavior before release decisions;
historical timing results do not justify changing retrieval/reranker algorithms.
