# ITLR–RAG | Intelligent IT Learning Platform — Improvement plan

Updated **2026-10-30**. This plan carries forward the earlier security, evaluation, retrieval,
generation and packaging roadmap. It describes acceptance criteria; completion requires dated
execution evidence in [Validation](../reports/VALIDATION.md). For implemented behavior and
compatibility boundaries, read [README](../README.md), [project memory](../docs/PROJECT_MEMORY.md)
and [ADR-010](../docs/decisions/ADR-010-shared-retrieval-and-atomic-state.md).

## Objective and working rules

Improve the platform’s reliability, source-backed learning support and reproducible evaluation.
Keep offline experiments distinct from runtime behavior. Do not change qrels, leak holdout data,
weaken assertions or relabel simulated data to improve results. Preserve user changes, database
content and active artifacts. No commit/push or paid API call is implied by this plan.

Each behavior change requires a reproduced failure or baseline, a focused implementation,
regression evidence and diff review. Improvements need a matching corpus/configuration and
confidence intervals or paired comparisons where appropriate; historical metrics are not a
baseline for a different runtime. Keep unmeasured metrics `null`.

## 1. Security and operating boundaries

Retain explicit secrets, safe text rendering/CSP, authenticated admin reload, bounded requests,
upload validation/access controls, trusted-proxy configuration and one worker/replica per service.
Credential rotation belongs to the operator if a real value has been exposed; changing examples
alone does not rotate an existing credential. Preserve secret scanning and dependency checks.

Acceptance requires rejection of unauthorized reload, malicious rendering, oversized requests
and unsupported upload content. Target-host memory/parser limits, malware handling, real account
flows and proxy configuration need their own evidence; unit tests do not certify deployment.
See [web remediation](../web/SECURITY_REMEDIATION.md).

## 2. Evaluation validity and reproducibility

Retain citation/NaN edge-case checks and nonzero exit codes when evaluation stages fail. Record
seed, corpus hash, config and source revision with label provenance (`human`, `simulated`,
`synthetic`, `imported`). Distinguish metadata qrels from independent relevance judgments.

The next evidence set should include independent passage qrels, clean/noisy query groups,
query-level holdout and reproducible comparisons of enabled lexical, dense and reranking stages.
Do not claim real-user quality from simulated human labels or CF clicks. Citation identity and
token-overlap proxies are separate from semantic faithfulness. Follow
[ADR-004](../docs/decisions/ADR-004-evaluation-design.md).

## 3. Retrieval and reranking

For chunk artifacts, keep shared encoding/filtering/relevance/ranking across search and chatbot.
Keep legacy V2 loading and the BM25 compatibility shim. Tune normalization, top-k, character/fusion
weights and relevance thresholds only on validation data, then assess holdout quality.

Benchmark CrossEncoder quality, latency and memory before enabling it. Evaluate RRF/MMR against
accuracy/diversity trade-offs; add cache or batching only when measured cost justifies it.
Define latency/capacity targets before judging a run against an SLO. Eight-document experiments
do not establish full-corpus gains, multiuser capacity or production suitability.

## 4. Generation and streaming

Keep selected item/chunk identity validation, bounded context and duplicate removal. Define
answerability and refusal behavior for missing or out-of-scope evidence. Sources arrive early;
tokens remain provisional until the final validated answer. Errors/cancellation must not persist
partial output as successful completion.

Evaluate citation precision/recall, entailment/faithfulness and refusal precision separately on
independent cases. Tests rejecting invalid references do not establish a universal 100% semantic
accuracy result. Run local inference and authenticated persistence flows with explicit configuration;
use paid providers only when separately authorized.

## 5. Packaging, observability and deployment evidence

Wheel package-data/discovery checks have recorded follow-up evidence in the
[V3 report](../reports/V3_RESTRUCTURING_2026-10-30.md); retain them and verify installation in a
clean supported environment before a release. Preserve dependency constraints and health/readiness
contracts. Record retrieval/rerank timing, usage, citation validity, refusals and errors without secrets.

Exercise PostgreSQL-backed learning/account flows, browser journeys, Docker/proxy configuration,
backup/restore, activation/reload/rollback and resource limits. Local Linux locks do not coordinate
multiple hosts. Split orchestration modules only when a concrete defect or maintenance need
justifies the import/compatibility cost; broad renaming is not a release requirement.

## Delivery order and decision criteria

Address security/evaluation regressions first, then minimal packaging needed for trustworthy
experiments, retrieval calibration, generation evaluation and operational exercises. The
[checklist](todo.md) tracks remaining evidence rather than restating historical unchecked plans.
A release decision requires current results and explicit acceptance of known limits; passing
regression suites alone does not close database, browser, quality or capacity gates.
