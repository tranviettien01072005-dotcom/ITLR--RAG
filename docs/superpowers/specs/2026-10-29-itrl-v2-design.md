# ITLR–RAG | Intelligent IT Learning Platform — V2 product design

Historical specification, **2026-10-29**. The priorities and validation criteria below describe
that session’s intended scope. Results are recorded in [V2 report](../../../reports/V2_PRODUCT.md);
current behavior is in [README](../../../README.md) and [validation](../../../reports/VALIDATION.md).

## Requirements

1. Collect a bounded set of **100–300 official learning pages**, with original URL, attribution,
   license metadata, retrieval date/hash and permitted full text. Keep real resources distinct
   from the synthetic legacy catalog; use real-only product builds while retaining synthetic
   data for reproducible experiments. This range was a target, not a measured collection count.
2. Expose exact excerpts, stable chunk IDs and source URLs. Validate citations against selected
   evidence and report unavailable evidence explicitly. ID matching does not prove entailment.
3. Stream real SSE through Python and authenticated Web: early sources, provisional tokens,
   authoritative validated final answer, cancellation and error states. Measure source,
   first-token and total timing separately.
4. Support authenticated goals, orientation diagnostics, ordered roadmaps, saved resources and
   progress using existing accounts/enrollments. State is account-scoped. Rule-based diagnostics
   guide exploration; they do not establish independently measured learner competence.

## Implementation boundaries

Extend existing Python retrieval/LLM adapters and Express/PostgreSQL modules with additive
changes. Preserve prior working-tree changes and runtime data. Keep one process/replica per
service and no new agent framework. Use local Qwen/E5 for authorized integration; keep reranker
disabled until benchmark evidence supports enabling it. No paid API calls or public deployment.

The originating session authorized a commit named `itrl v2` and a non-force push, excluding
model binaries and secrets. That historical authorization does not grant permission in a new
session; follow the current request and [AGENTS](../../../AGENTS.md).

## Acceptance evidence

Each slice requires regressions, followed by full Python/Web checks, actual PostgreSQL-backed
learning flow, real source/index verification and local Qwen SSE. Independent review precedes
any authorized commit. Mark each check by actual execution; a specification or unit test does
not prove database, browser or deployment integration.
