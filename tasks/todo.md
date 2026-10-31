# ITLR–RAG | Intelligent IT Learning Platform — Follow-up checklist

Updated **2026-10-31**. Scope and acceptance criteria: [improvement plan](plan.md).
Implemented behavior and completed checks belong to [README](../README.md) and
[Validation](../reports/VALIDATION.md); unchecked items below are outstanding evidence or work,
not claims that all previous implementation is missing.

## Evaluation and retrieval

- [ ] Create independent passage-level relevance judgments with provenance and query holdout.
- [ ] Calibrate V3 cosine/off-topic thresholds against representative IT and non-IT cases.
- [ ] Compare lexical/dense/hybrid configurations on clean/noisy tracks with uncertainty.
- [ ] Measure real reranker quality, latency and memory before changing its default.
- [ ] Benchmark full-corpus bounded candidate pools and concurrent load against agreed targets. (partial: conc 1/2/4 + search×8, 2026-10-31 §12.3)
- [ ] Evaluate RRF/MMR trade-offs without changing test qrels or tuning on the holdout.

## Generation and learner experience

- [ ] Measure semantic faithfulness/entailment and citation precision/recall independently of ID checks.
- [ ] Evaluate answerability and refusal precision on representative supported/unsupported requests.
- [x] Exercise authenticated SSE, cancellation/error handling and final-answer persistence end to end. (2026-10-31: HTTP 36/36, Chrome 11/11, cancel socket 55ms — [certification](../reports/FINAL_E2E_CERTIFICATION.md))
- [x] Verify account-scoped diagnostic, roadmap, saved-resource and progress flows in PostgreSQL/browser. (2026-10-31: register/progress/diagnostic/restart PASS, Chrome progress 40 — §11.3)
- [ ] If authorized, validate the configured paid provider separately from local/template runs.

## Deployment and security

- [ ] Verify a clean supported-environment install of the built wheel and packaged static assets.
- [x] Run Docker/proxy deployment checks with explicit credentials, HTTPS origin and one replica/service. (2026-10-31: isolated Compose project, Caddy TLS nội bộ, one replica — §11.3; public ACME NOT VERIFIED)
- [ ] Validate parser/native-memory limits and the upload scanning/quarantine policy on the target host.
- [x] Exercise backup/restore and version activation/reload/rollback without losing runtime data. (2026-10-31: 15 bảng row-hash, activate/reload/rollback/tamper — §11.3)
- [ ] Confirm monitoring, health/readiness, log redaction and agreed latency/capacity alerts. (health/readiness/metrics PASS; external alerts NOT VERIFIED)
- [x] Refresh dependency/security assessment when preparing a release; retain unresolved advisory scope. (2026-10-31: pip-audit 0, npm audit 0, Bandit 0 High; recheck mỗi release)
- [ ] Recheck source rights/attribution and rebuild/probe/activate when indexed full-text permission changes.

## Completion discipline

For each completed item, record date, command/configuration, corpus/version, result and limits in
Validation or its linked report. Keep synthetic data and simulated labels explicit. Do not replace
missing integration evidence with unit-test counts, weaken quality gates, delete the BM25 shim,
activate artifacts or migrate runtime data as part of documentation maintenance. Commit/push,
paid calls and public deployment require authorization in the current request.
