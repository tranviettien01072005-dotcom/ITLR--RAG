# ADR-012: Calibrated search defaults and confirmed stream persistence

## Status

Implemented in the working tree; local verification only. Production remains NO-GO.
See [engineering review](../../reports/FINAL_ENGINEERING_REVIEW.md).

## Date

2026-10-30

## Context

The default `min_pct=90` meant raw cosine 0.90 and removed most E5 candidates before
BM25/RRF. Rewriting every query and expanding any mentioned glossary concept also
changed the input distribution used for calibration. Web persisted a final response
before upstream completion and accepted EOF without the terminal done event.

## Decision

- Set the search default to **84**, selected only on the frozen development split.
  Preserve explicit `min_pct` overrides and the integer range 0–100. This is cosine
  ×100, not a probability. Keep chatbot off-topic gate 0.80 and ranking weights.
- Expand bare glossary aliases. Preserve raw query text unless actual typo or
  abbreviation correction is required; do not turn a specific question into a topic.
- Require valid `final` + `done` + completed parsing before Web history persistence.
  Sources/tokens remain provisional and are forwarded immediately.
- Keep history text in PostgreSQL intact; bound only the provider-context copy.
- Reuse the source metadata sanitizer for recommendation outputs: NaN/Inf → null,
  internal full snapshot bodies omitted. Do not weaken citation/finish validation.
- Check elapsed Ollama generation budget at NDJSON boundaries as well as read
  timeout. This is not a precise deadline while a blocking read is stalled.

## Alternatives

Dropping the cosine floor to zero admitted negatives. Increasing context, changing
models/weights, or lowering temperature had no sufficient quality evidence. A shorter
prompt experiment reduced latency but still produced malformed citations and an
incorrect SQL example, so it was not applied. Splitting large orchestration modules
solely by size would relocate complexity; remove proven unused work instead.

## Consequences

Search returns more relevant judged results with the measured negative rejection
preserved. The default is a behavioral change; callers wanting the former floor
must pass `min_pct=90`. Real V2 quality, independent semantic labels, authenticated
PostgreSQL journeys and deployment/soak gates remain separate acceptance work.
Only temporary real-snapshot artifacts were used; no activation or schema change.
