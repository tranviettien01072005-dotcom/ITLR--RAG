# ADR-010: Share chunk retrieval and atomically commit lifecycle state

Product: **ITLR–RAG | Intelligent IT Learning Platform**. Implemented, 2026-10-30;
release validation remains incomplete. Evidence: [V3 report](../../reports/V3_RESTRUCTURING_2026-10-30.md)
and [validation](../../reports/VALIDATION.md).

## Context and decision

Search and chatbot had separate ranking paths; off-topic checks used item averages even when
relevant passages existed. `itlr/retrieval/service.py` now owns query encoding, type filtering,
chunk ranking and relevance gating for artifacts with chunk vectors. API and chatbot adapt the
results to their response schemas; legacy artifacts retain the V2 path.

RRF determines ranking; raw normalized dense cosine determines relevance. Neither fused scores
nor displayed confidence are calibrated probabilities. Filters run before candidate truncation.
Generated V3 answers cite both item and selected chunk identifiers. Identity checks do not prove
semantic entailment or faithfulness. Offline templates keep an explicit mode.

`CURRENT.json` commits version, relative directory and bounded transition history together:
temporary write → file fsync → replace → directory fsync. The old history file remains a
compatibility mirror. Readers prefer embedded history and import the mirror for legacy pointers.
An interruption after pointer replacement leaves committed history available on restart/rollback.
A mirror-write failure can be reported after commit; inspect `CURRENT.json` before retrying.

## Migration mapping

| Previous location | Current location | Reason and compatibility |
|---|---|---|
| BM25 implementation in `itlr/core/bm25.py` | `itlr/retrieval/bm25.py` | Retrieval owns lexical indexing; original module re-exports BM25Index so old pickle GLOBAL references and fields remain compatible |
| Duplicated chatbot/API chunk branch | `itlr/retrieval/service.py` | Share encoding, filters, scores and ranking; retain existing HTTP keys and V2 loading |
| History only in `CURRENT.json.history.json` | Embedded history in `CURRENT.json` | Remove two-file commit gap; still read legacy pointers/mirror and export mirror |

## Consequences and limits

The tracked BM25 implementation was moved with `git mv`; keep the original module as a shim.
No database schema, runtime content, artifact filename, CLI or environment path was renamed.
`collect`, `chatbot`, `api`, `pipelines`, `eval`, `scripts`, `deploy` and `web` retain established
responsibilities; broad renaming would risk imports and persisted pickle references.

These are targeted boundary changes, not a claim that every module follows Clean Architecture.
Coordination assumes cooperating writers on a local Linux filesystem, one process/replica per
service. Process-interruption recovery does not establish multi-host coordination or storage
power-loss guarantees. Independent passage evaluation and deployment checks remain separate gates.
