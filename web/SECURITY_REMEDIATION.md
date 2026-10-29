> **Ngữ cảnh đồ án — 2026-10-30:** Tài liệu lịch sử: giữ số đo, phạm vi và kế hoạch tại thời điểm ghi. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../README.md).

What this repo does: The Node web app authenticates learners, stores conversations and social content in PostgreSQL, and calls the Python RAG API. This review assumes one Node process behind an explicitly configured reverse proxy.

## Audit before fixes

1. **Must fix: default credentials permit impersonation.** `src/config/env.ts` supplied a known signing key, admin passcode `1`, and PostgreSQL credentials outside production. Starting development on a reachable host exposed privileged access. Fix: require strong explicit configuration in all modes.
2. **Must fix: uploads trust attacker MIME and extension.** API, social and admin handlers persisted arbitrary bytes and served the attacker MIME inline. A fake avatar with `image/svg+xml` could carry active content; document parsers ran directly on the event loop. Fix: shared signature/MIME validation before storage, bounded multipart inputs, rejection of unvalidated Office/video formats, extraction worker timeout and response sandbox.
3. **Must fix: pending attachments bypass moderation.** `/api/download/:id`, inline and text routes returned unapproved files to any authenticated user. Fix: require approval or ownership for ordinary users; admin has its separate protected download route.
4. **Must fix: spoofed forwarding headers bypass per-IP limits.** `trust proxy=1` assumed every peer was a proxy. Fix: direct connections by default; explicit trusted proxy IP/CIDR list; refuse common multiworker settings while limiter/presence are in memory.
5. **Must fix: web build broken.** `dataset.ts` had duplicate extraction exports, missing imports and an incorrect catalog path. Fix: use central `ITEMS_CSV` and dedicated extraction worker.
6. **Should fix: inline scripts weaken CSP.** Templates required `unsafe-inline`. Fix: external init script and event listeners; CSP now forbids inline JavaScript and attributes.

## Implementation limits

Signature checks are not antivirus or full decoder validation. Files remain in private request memory until all signatures pass. This is quarantine before validation, not a durable malware scanning queue. Existing blobs may predate validation; response sandbox and nosniff also cover those blobs.

Office documents and videos are rejected pending safe validation. The initial ZIP validator relied on local headers while Office parsers use the central directory; review found that mismatch could bypass its limits. The final change rejects all Office uploads, removes Mammoth/XLSX parser dependencies, and only extracts bounded PDF input. UI file selectors and messages match this restriction.

Document extraction uses at most two worker threads, five second timeout, V8 heap caps, bounded output and page limits. Worker memory limits do not cap native allocations or total process memory; use container/OS resource limits. Full malware scanning and content disarm remain necessary before production acceptance of arbitrary user documents.

One-process deployment is an explicit constraint, not distributed limiting. Guards reject common cluster settings, but orchestration must keep replicas at one. Configure `TRUSTED_PROXIES` only for actual proxy CIDRs and make that proxy overwrite forwarding headers.

## Skills and sources

Applied security-and-hardening (trust boundaries and abuse cases), test-driven-development (regression cases), source-driven-development (official contracts), debugging-and-error-recovery (broken dataset module), git-workflow-and-versioning (preserved user changes), and Ponytail ultra/audit/review (shared middleware and minimal changes).

- [Express proxy trust](https://expressjs.com/en/guide/behind-proxies/)
- [Node worker limits](https://nodejs.org/api/worker_threads.html)
- [OWASP upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)

## Review after fixes

What this change does: It requires explicit credentials, validates uploads before persistence, restricts pending attachment access, and constrains proxy/worker assumptions. It also separates document extraction from the request event loop and blocks inline JavaScript.

Verdict: Do not declare production-ready until dependency audit, full web tests, PostgreSQL integration, scanner/quarantine policy and deployment resource limits pass. No live database or browser proof is implied by unit tests.

Not checked: Real PostgreSQL flows, full browser rendering, antivirus, native memory exhaustion, multi-host deployment.

## Executed checks (2026-10-29)

- `/tmp/node-v22.16.0-linux-x64/bin/node --check web/src/public/app.js`: PASS.
- Same syntax check for `web/src/public/init.js`: PASS.
- Node vm self-check against full `itlr/api/static/ui.js`: PASS for HTML escaping, executable/protocol-relative URL rejection, and text-only malicious catalog rendering with an HTML sink that throws.
- Added persistent Vitest regressions in `src/config/env.test.ts`, `src/middleware/uploads.test.ts`, `src/services/static-ui.test.ts`.
- Initial test attempt: NOT RUN because npm was absent in PATH; dependency installation then completed. Reset-token logging was separately reproduced with a failing route-level test before its fix; other new tests lack recorded pre-fix execution.
- Node22 `--experimental-strip-types` execution of an exact copy of `src/middleware/uploads.ts`: PASS for disguised HTML, SVG, mismatched MIME, valid PNG signature, and quarantine returning 415 without invoking the route. This does not substitute for TypeScript typecheck or database route tests.

Final dependency remediation: npm audit initially reported 18 findings (12 high, 1 critical). Updated lockfile, upgraded Multer to 2.x, Zod to 4.x and Nodemailer to 10.x; removed Mammoth/XLSX. `npm audit fix` and ordinary `npm update` hit an npm 10 Arborist peer-resolver crash; `npm update --legacy-peer-deps` succeeded. A fresh **normal** `npm ci --ignore-scripts --prefix /tmp/itlr-web-install-check` then installed 322 packages and audited 323 with **0 vulnerabilities**, proving the lockfile needs no persisted peer bypass. Offline clean-install attempt failed only because a tarball was not cached; online retry passed.

Verification after upgrades: TypeScript typecheck PASS; ESLint PASS with 20 existing `any` warnings; build PASS; full Vitest suite **22 tests / 6 files PASS**. Source line coverage is only about **9.34%**; these tests cover selected regressions and are not comprehensive application coverage. Worker tests exercise corrupt PDF rejection and parser capacity recovery. Static UI VM tests do not replace a real browser.

Review also confirmed entrypoint seed errors are no longer swallowed. Production requires explicit HTTPS APP_ORIGIN. No PostgreSQL integration, SMTP delivery, browser UI or production deployment is claimed here.
