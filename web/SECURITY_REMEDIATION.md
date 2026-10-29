# ITLR–RAG | Intelligent IT Learning Platform — Web security remediation

Historical checkpoint: **2026-10-29**. The Express application authenticates learners, stores
conversations/social content in PostgreSQL and calls the Python RAG API. This review assumed
one Node process behind an explicitly configured proxy. Later evidence and operating limits
are in [Validation](../reports/VALIDATION.md), [deployment](../deploy/DEPLOY.md) and
[final remediation](../reports/FINAL_REMEDIATION.md).

## Findings and changes at the checkpoint

| Finding before remediation | Implemented boundary |
|---|---|
| Known JWT key, admin passcode `1` and database defaults allowed impersonation on reachable development hosts | Require explicit strong credentials in all modes |
| Uploads trusted attacker MIME/extension and could persist active content | Shared signature/MIME checks before storage, bounded multipart input and fail-closed formats |
| Pending attachment download/inline/text routes bypassed approval | Require approval, ownership or privileged access |
| `trust proxy=1` trusted arbitrary direct peers and could bypass per-IP limits | Direct connections by default; explicit trusted proxy IP/CIDR list |
| `dataset.ts` had duplicate extraction exports, missing imports and wrong catalog path | Central `ITEMS_CSV` and dedicated extraction worker |
| Template inline scripts required `unsafe-inline` | External initialization/event handlers and CSP blocking inline JavaScript |

Uploads remain in private request memory until validation succeeds. This is transient isolation,
not a durable malware quarantine. Signature checks do not replace antivirus or decoder validation.
Existing blobs may predate the checks; sandbox response headers and `nosniff` also apply to them.

Office/video uploads are rejected. Review found that ZIP local-header checks could disagree with
Office parsers’ central-directory view; the final scope removed Mammoth/XLSX and limited extraction
to bounded PDF. UI selectors/messages reflect supported formats. Extraction permits at most two
worker threads, a five-second timeout, V8 heap caps, output and page limits. Worker limits do
not cap native allocations or total process memory; configure OS/container limits on the host.

Both rate limiting and presence remain in memory. Startup rejects common cluster settings;
orchestration must still keep one process/replica. `TRUSTED_PROXIES` must name actual peers,
and the proxy must overwrite forwarded headers. These controls do not provide multi-host limiting.
Production-mode configuration requires explicit HTTPS `APP_ORIGIN`; entrypoint seed errors are
reported rather than swallowed.

## Recorded verification

- Node 22.16.0 syntax checks passed for `src/public/app.js` and `src/public/init.js`.
- A Node VM check of Python static `ui.js` passed HTML escaping, executable/protocol-relative
  URL rejection and text-only malicious catalog rendering with a throwing HTML sink.
- Vitest regressions were added for environment, upload and static-UI boundaries. Reset-token
  logging had recorded FAIL → fix → PASS; other new tests lacked recorded pre-fix execution.
- An exact `uploads.ts` copy executed with Node’s experimental type stripping passed disguised
  HTML, SVG, MIME mismatch, valid PNG signature and 415 quarantine-boundary cases. This did
  not replace typecheck, database route tests or browser execution.
- PDF worker tests exercised corrupt-input rejection and parser-capacity recovery.

The first npm test attempt could not run because npm was absent from PATH. Dependency audit
initially reported **18 findings: 12 high and 1 critical**. Updates moved Multer to 2.x, Zod to
4.x and Nodemailer to 10.x and removed Mammoth/XLSX. npm 10 Arborist crashed on ordinary
`audit fix`/`update`; `update --legacy-peer-deps` completed. A separate normal
`npm ci --ignore-scripts --prefix /tmp/itlr-web-install-check` installed **322 packages** and
audited **323 with 0 vulnerabilities** at that checkpoint, without a persisted peer bypass.
An offline attempt lacked a cached tarball; the online retry passed. This historical audit
is not a current vulnerability assessment.

After upgrades, typecheck/build passed, lint had 0 errors / 20 existing `any` warnings,
and **22 tests in 6 files passed**. Source line coverage was about **9.34%**, covering selected
regressions rather than the full application. Later test totals belong to later validation runs.

## Review scope and remaining evidence

The changes established explicit credentials, validation-before-persistence, pending-file access
control, proxy constraints, extraction isolation and CSP. No PostgreSQL integration, SMTP delivery,
real browser rendering, malware scan, native-memory exhaustion, multi-host deployment or production
deployment was exercised in this checkpoint. Static VM tests do not substitute for browser tests.
Release decisions still need current dependency review, database/browser flows, upload scanning
policy and target-host resource validation; no readiness certification is claimed.

The originating work applied security, TDD, source-driven development, debugging, Git workflow and
Ponytail Ultra review. Technical references retained for that work:
[Express proxies](https://expressjs.com/en/guide/behind-proxies/),
[Node workers](https://nodejs.org/api/worker_threads.html),
[OWASP uploads](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).
