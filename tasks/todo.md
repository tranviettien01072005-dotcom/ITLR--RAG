# Upgrade Checklist

## Phase 0 — Security

- [ ] Rotate/remove credential-shaped value in `.env.example`
- [ ] Add secret scanning to tests/CI
- [ ] Sanitize Markdown and catalog/user fields
- [ ] Protect or disable `/admin/reload`
- [ ] Add API input limits and correct error status codes

## Phase 1 — Evaluation

- [ ] Fix hallucination/citation edge cases
- [ ] Fix evaluator NaN formatting
- [ ] Make `run_all.py` propagate failures
- [ ] Add label provenance and run metadata
- [ ] Regenerate baseline reports from a clean run

## Checkpoint A

- [ ] Tests pass
- [ ] Holdout baseline is reproducible
- [ ] Retrieval comparison table includes all enabled stages

## Phase 2 — Retrieval

- [ ] Define query/qrel tracks and holdout split
- [ ] Tune hybrid weights on validation only
- [ ] Benchmark reranker latency and quality
- [ ] Evaluate RRF/MMR Pareto trade-off

## Phase 3 — Generation

- [ ] Implement strict citation validation
- [ ] Add context budget and answerability policy
- [ ] Make partial stream failures explicit
- [ ] Add groundedness/refusal evaluation

## Phase 4 — Productization

- [ ] Fix wheel package discovery and package-data
- [ ] Add clean install smoke test
- [ ] Add dependency constraints/lock
- [ ] Add runtime metrics and SLO checks
- [ ] Split chatbot orchestration into focused modules
