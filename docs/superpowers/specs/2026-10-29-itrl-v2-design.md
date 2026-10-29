# ITLR product V2

User selected and authorized implementation of priorities1–4 and GitHub commit/push `itrl v2`.
Use existing Python retrieval/LLM adapter and Express/PostgreSQL accounts. Preserve prior dirty
work and include validated session changes in requested V2 commit; no model binaries/secrets.

1. Bounded curated collection of100–300 official learning pages with source URL, attribution,
license, retrieval date/hash and full source text. Real resources distinguishable from synthetic
legacy. Default product dataset real-only; keep synthetic dataset for reproducible research.
2. Expose exact source excerpts with stable chunk IDs and URLs. Verify citations against retrieved
IDs, refuse unavailable evidence, never claim semantic verification from ID matching alone.
3. True SSE from model through API/web, early sources, provisional tokens and authoritative final
validated answer, cancel/error states and measured source/first-token/total timing.
4. Authenticated goal/diagnostic/ordered roadmap, save resources and update progress using
existing enrollments. Rule-based diagnostic is orientation only. Account-scoped persistent state.

Chosen approach: extend current modules and schema with additive changes. Keep one process per
service, no new agent framework. No paid API calls/public deployment. Existing local Qwen/E5
used for real integration; reranker stays disabled unless benchmark warrants change.

Validation: regressions per slice, full Python/web typecheck/lint/tests, actual PostgreSQL-backed
learning flow, real source crawl/index and real Qwen SSE. Independent review before commit.
