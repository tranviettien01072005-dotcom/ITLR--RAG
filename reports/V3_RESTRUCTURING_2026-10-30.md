# ITLR–RAG | Intelligent IT Learning Platform

## Shared V3 retrieval and durable lifecycle state

Historical record: 2026-10-30. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

This checkpoint extended the 245-Python/59-Web baseline with shared V3 retrieval, a BM25 module relocation and pointer/history process-interruption recovery. Existing uncommitted changes were preserved. The scope remained targeted, without a new whole-repository audit.

### Runtime behavior and compatibility

`itlr/retrieval/service.py` shares encoding, type filtering, relevance and chunk ranking across engine search, semantic chat, quick resources and off-topic detection. V3 no longer appends legacy RAG recommendations after chunk retrieval; legacy artifacts retain their prior branches. Intent/template features remain distinct from LLM-generated answers.

FAISS applies type/relevance filters before truncating candidates. Search schemas retain existing keys and add `chunk_id`/`excerpt`. Raw dense cosine is separate from RRF score and is not a calibrated probability. Generated V3 answers require a selected chunk reference for each cited item; item-only evidence is rejected. Extractive answers include markers, while V2 validation stays compatible. These identity checks do not measure entailment, truth or faithfulness.

Version and bounded transition history now commit together in `CURRENT.json` using temporary write → fsync → replace → directory fsync. The old history file remains a compatibility mirror. Readers import legacy history when the pointer lacks embedded history. A mirror failure may be reported after the pointer has committed; inspect `CURRENT.json` before retrying. A real process-exit/restart test interrupts between pointer commit and mirror export, then confirms rollback finds the previous version. Corrupted reload candidates are rejected while the loaded engine continues serving health requests.

CI explicitly includes shared-service and compatibility regressions. Developer/deployment docs were updated. No active index rebuild, activation, database-content migration, paid API call or deployment occurred.

### Module and state decisions

| Previous location | Replacement | Reason | Compatibility |
|---|---|---|---|
| `itlr/core/bm25.py` implementation | `itlr/retrieval/bm25.py` | Group lexical indexing with retrieval | Old module re-exports the class; pickle GLOBAL resolution and unchanged fields covered by regression |
| Duplicated engine/chatbot V3 adapters | `itlr/retrieval/service.py` | Share encoding/filtering/ranking contract | Existing response keys and V2 artifact branch preserved |
| History only in `CURRENT.json.history.json` | Embedded in `CURRENT.json` | Eliminate two-file transition gap | Import legacy history; continue exporting mirror |

The BM25 relocation used `git mv`; compatibility shim and implementation were recorded in code commit `4b0a0d1`. Git represents the result as a new implementation plus the shim at the original path. No dependency was removed speculatively.

The directory review covered `itlr`, `web`, `tests`, `eval`, `scripts`, `configs`, `deploy`, `.github`, `docs` and `reports`. Established names were retained: `collect` already owns ingestion; `chatbot/llm_client.py` owns generation. Broad renaming would add import/pickle/CLI risk without resolving the shared-retrieval defect. `itlr/core/chunks.py` remained in place. This is a targeted module-boundary improvement, without a claim that every module follows Clean Architecture. [ADR-010](../docs/decisions/ADR-010-shared-retrieval-and-atomic-state.md) records responsibilities.

### Failure reproduction and review

Three missing-service tests failed before implementation. V3 generation without a chunk marker was incorrectly accepted before strict validation; it is now rejected. Simulated interrupted transitions lost history before embedded atomic state, and recover afterward. Quick resources bypassed shared retrieval before correction. Process-exit and corrupted-artifact tests exercise failure paths without touching runtime data, and existing endpoint assertions remain.

Ponytail Ultra review traced search/chat, quick resources, relevance, source serialization, generation validation, legacy BM25 imports/pickles, activation/rollback/GC and CI references. The newly found quick-resource bypass was corrected; no unexplained High/Critical issue remained within the diff. Assumptions are one API process, local Linux filesystem and cooperating CLI writers.

### Measured experiment

Raw output: `reports/chunks_v3_unified_experiment.json`.

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python eval/bench_chunks_v3.py
```

| Configuration | Recall@5 / MRR@5 / nDCG@5 | p95 query + retrieval | Mean query + retrieval CPU |
|---|---|---:|---:|
| Item-mean dense | 1.0 / 1.0 / 1.0 | 129.07ms | 113.98ms |
| Chunk BM25 + dense + RRF | 1.0 / 1.0 / 1.0 | 130.23ms | 114.98ms |

The corpus contained eight real documentation snapshots, 98 chunks and eight hand-authored item-level judgments. E5-base ran on CPU, without CrossEncoder or generation. Whole-process peak RSS was 1468.86MiB, including model load and both configurations. Query encoding was measured once and shared in the totals. Every chunk was eligible; this did not model bounded runtime candidate pools or load. No quality/speed improvement was established. Faithfulness/hallucination/citation accuracy are null because generation was excluded.

### Validation and limits

Full Python suite: 256 passed / 0 skipped in 44.63s outside the sandbox; fixtures disabled paid providers, OMP/MKL/OpenBLAS=1. Web typecheck/build passed; lint 0 errors / 20 existing warnings; 59 tests passed with 25.01% line coverage. compileall, `pip check` and `git diff --check` passed. No type/lint/coverage rule was weakened. Temporary logs: `/tmp/itlr-restructure-final.log`, `/tmp/itlr-unified-benchmark.log`.

At this checkpoint, all-result FAISS filtering materialized chunk scores and BM25 still scanned the corpus; larger-corpus latency/RAM remained unmeasured. Later BM25 work is covered by current validation. V3 cosine off-topic calibration, independent passage qrels, real CrossEncoder inference/load and semantic citation entailment remained pending. Process-interruption recovery does not establish device/controller-failure or network-filesystem durability. Source-tree renaming, unproven dead-code deletion and speculative dependency removal were excluded.

Live DeepSeek was not authorized; PostgreSQL, Docker Compose (`docker`/`psql`/`postgres` absent from PATH), browser E2E, full-corpus evaluation and monitoring/deployment were not exercised. Mock LLM tests remained in regression. These are evidence gaps rather than proven service failures.

### Packaging follow-up

Namespace discovery initially stalled at metadata. Setting `namespaces=false` matched regular packages with `__init__.py` and allowed offline wheel creation. Asset inspection then failed because the wheel contained zero static files. Explicit `itlr.api` HTML/JS/CSS package data fixed the omission; the rebuilt wheel contained all four UI assets, retrieval modules and the legacy BM25 shim. Builds used `--no-index --no-deps --no-build-isolation`; no dependencies were downloaded.
