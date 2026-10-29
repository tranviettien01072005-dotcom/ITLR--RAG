# ITLR–RAG | Intelligent IT Learning Platform — Follow-up checklist

Updated **2026-10-30**. Scope and acceptance criteria: [improvement plan](plan.md).
Implemented behavior and completed checks belong to [README](../README.md) and
[Validation](../reports/VALIDATION.md); unchecked items below are outstanding evidence or work,
not claims that all previous implementation is missing.

## Evaluation and retrieval

- [ ] Create independent passage-level relevance judgments with provenance and query holdout.
- [ ] Calibrate V3 cosine/off-topic thresholds against representative IT and non-IT cases.
- [ ] Compare lexical/dense/hybrid configurations on clean/noisy tracks with uncertainty.
- [ ] Measure real reranker quality, latency and memory before changing its default.
- [ ] Benchmark full-corpus bounded candidate pools and concurrent load against agreed targets.
- [ ] Evaluate RRF/MMR trade-offs without changing test qrels or tuning on the holdout.

## Generation and learner experience

- [ ] Measure semantic faithfulness/entailment and citation precision/recall independently of ID checks.
- [ ] Evaluate answerability and refusal precision on representative supported/unsupported requests.
- [ ] Exercise authenticated SSE, cancellation/error handling and final-answer persistence end to end.
- [ ] Verify account-scoped diagnostic, roadmap, saved-resource and progress flows in PostgreSQL/browser.
- [ ] If authorized, validate the configured paid provider separately from local/template runs.

## Deployment and security

- [ ] Verify a clean supported-environment install of the built wheel and packaged static assets.
- [ ] Run Docker/proxy deployment checks with explicit credentials, HTTPS origin and one replica/service.
- [ ] Validate parser/native-memory limits and the upload scanning/quarantine policy on the target host.
- [ ] Exercise backup/restore and version activation/reload/rollback without losing runtime data.
- [ ] Confirm monitoring, health/readiness, log redaction and agreed latency/capacity alerts.
- [ ] Refresh dependency/security assessment when preparing a release; retain unresolved advisory scope.
- [ ] Recheck source rights/attribution and rebuild/probe/activate when indexed full-text permission changes.

## Completion discipline

For each completed item, record date, command/configuration, corpus/version, result and limits in
Validation or its linked report. Keep synthetic data and simulated labels explicit. Do not replace
missing integration evidence with unit-test counts, weaken quality gates, delete the BM25 shim,
activate artifacts or migrate runtime data as part of documentation maintenance. Commit/push,
paid calls and public deployment require authorization in the current request.
