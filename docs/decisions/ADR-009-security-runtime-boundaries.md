# ADR-009: Explicit runtime trust boundaries

Date: 2026-10-29. Accepted for remediation; public release remains gated.

Untrusted sources include catalog data, LLM output, upload bytes and forwarded headers.
Static UI builds data nodes with textContent and allows HTTP(S) catalog links only.
Markdown supports escaped emphasis/code/newlines; raw HTML and Markdown links are disabled.
JavaScript is local and external; CSP script-src self does not allow inline scripts.
Source: https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent

Web requires explicit JWT/admin/database credentials even in development. Pending uploads
remain in private request memory until shared signature checks succeed; serving pending files
requires ownership or privileged access. These checks are not antivirus or durable quarantine.
Unsupported formats fail closed. Parser isolation/resource limits still require target-host validation.

Both limiters remain in memory. One process and one replica are required and known worker env
settings are checked at startup. API defaults ignore proxy headers; web proxy trust is opt-in.
Scaling requires shared limiting, rather than multiplying independent quotas.
Source: https://expressjs.com/en/guide/behind-proxies/

Artifacts remain executable trusted-builder inputs. Version pointers cannot escape the configured
root; SHA256 manifests inventory files before engine unpickle and activation/rollback. Strict mode
requires a manifest; one engine load pins one directory. Hashes detect changes, not authenticity
against an attacker who can rewrite both files and manifest. API artifact mounts must be read-only.

Do not change retrieval/reranker algorithms based on historical timings. Current dense evaluation,
live generation and deployment gates must pass before any production-ready claim.
