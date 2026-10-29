> **Ngữ cảnh đồ án — 2026-10-30:** Quyết định kiến trúc theo thời điểm. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../../README.md).

# ADR-010: Share chunk retrieval and commit lifecycle state in one pointer

Date: 2026-10-30. Status: implemented; release validation remains incomplete.

Search and chatbot previously used different ranking paths, and off-topic decisions
used item averages even when matching passages existed. `itlr.retrieval.service`
now owns query encoding, type filtering, chunk ranking and relevance gating for
artifacts that contain chunk vectors. BM25 moves into this package because it is a
retrieval index, not a general core utility. API and chatbot adapt service results
to their existing response schemas. Legacy artifacts retain their existing path.

Ranking uses RRF; relevance uses raw normalized vector cosine. A fused rank score
is not a probability and must never be compared to the existing cosine threshold.
Type and relevance filters run before candidate truncation. V3 generated answers
must cite both item and selected chunk identifiers. This proves identity only,
not semantic entailment. Offline templates retain their explicit template mode.

`CURRENT.json` now atomically commits version, relative directory and bounded
transition history together. File and directory fsync follow the pointer write.
`CURRENT.json.history.json` remains a compatibility mirror; internal readers prefer
embedded history and read the old mirror only for legacy pointers without it.
If interrupted after pointer replacement, restart reads the committed history and
can roll back. Legacy history is imported on the next transition. A mirror-write
failure can report failure after a committed transition: operators must inspect
CURRENT.json before retrying. These guarantees assume a local Linux filesystem;
they do not establish distributed coordination or storage power-loss behavior.

## Migration mapping

| Previous path | Current path | Technical reason | Compatibility |
|---|---|---|---|
| `itlr/core/bm25.py` implementation | `itlr/retrieval/bm25.py` | Keep lexical indexing in the retrieval package | Old module re-exports BM25Index; old pickle GLOBAL resolves; fields unchanged |
| Chunk branch duplicated in chatbot/API | `itlr/retrieval/service.py` | Shared encoding, filtering, scores and ranking contract | Public HTTP schemas and V2 artifact loading retained |
| History solely in `CURRENT.json.history.json` | History embedded in `CURRENT.json` | Remove pointer/history crash window | Old pointer/mirror read; mirror still exported; artifact paths unchanged |

The tracked BM25 implementation was moved with git mv. No database schema, runtime
content, artifact filename, CLI entrypoint or environment path was renamed.
Existing `collect`, `chatbot`, `api`, `pipelines`, `eval`, `scripts`, `deploy` and web
packages have identifiable responsibilities. Moving them all would invalidate
imports and persisted pickle references without resolving the shared-retrieval
bug, so they remain in place. This is a targeted migration, not a claim that every
module now satisfies Clean Architecture dependency rules.
