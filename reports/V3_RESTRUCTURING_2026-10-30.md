What this change does: continues the 245-Python/59-Web checkpoint with shared V3 retrieval, a targeted module migration and pointer/history crash recovery. Existing uncommitted changes were preserved. No full-repo audit was restarted.

Implemented and reviewed with Ponytail Ultra:

- `itlr/retrieval/service.py` shares encoding, type filtering, relevance and chunk ranking between engine search, chatbot semantic retrieval, quick resources and off-topic detection. V3 no longer appends legacy RAG recommendations after chunk retrieval. Legacy artifacts continue to use legacy branches. Existing intent/template features remain explicitly separate from LLM-generated answers.
- FAISS chunk search now applies type/relevance filters before candidate truncation. Raw dense cosine is distinct from RRF scores. Search response schemas retain their keys, with chunk_id/excerpt added to results. The raw similarity field is not a calibrated probability.
- V3 generated answers require a valid selected chunk reference for each cited item. Item-only generation is rejected as insufficient evidence. V2 validation remains backward compatible. Extractive answers include chunk markers. Identifier validation still does not measure entailment, truth or faithfulness.
- BM25 was moved with git mv into the retrieval package. Existing callers were updated. The old module re-exports the class to preserve imports and GLOBAL resolution of persisted pickle artifacts. No dependency was removed speculatively.
- Version and bounded transition history commit together in CURRENT.json using temporary file + fsync + replace + directory fsync. The old history file remains an exported compatibility mirror. Readers import legacy history when the pointer lacks embedded history. A mirror failure can report failure after a committed pointer: inspect CURRENT.json before retrying.
- Actual process-exit/restart test interrupts after pointer commit and before mirror export; rollback still finds the previous version. Existing locking/thread/process tests remain. Corrupted version reload is rejected while the already loaded engine keeps serving health requests.
- CI explicitly runs shared-service and compatibility regressions with the integration group. Developer/deployment docs updated. No active index rebuild, activation, migration of database contents, paid API call, or deployment was performed.

TDD evidence: missing retrieval service failed three tests before implementation; a V3 generated answer missing its chunk passed incorrectly before strict validation and is rejected afterward; a simulated interrupted transition lost history before atomic embedding and now recovers; quick resources invoked legacy embedding retrieval before the fix and now passes through the shared service. Existing endpoint assertions were retained. Added process-exit and corrupted-artifact recovery checks exercise failure paths without altering runtime data.

## Path mapping and repository decisions

| Old path/location | New path/location | Reason | Compatibility |
|---|---|---|---|
| itlr/core/bm25.py implementation | itlr/retrieval/bm25.py | Lexical indexing belongs with retrieval | Re-export shim; pickle GLOBAL regression; unchanged class fields |
| Duplicated V3 adapter logic in engine/chatbot | itlr/retrieval/service.py | One contract for encoding/filtering/ranking | Existing API keys and V2 artifact branch retained |
| History solely in CURRENT.json.history.json | Embedded history in CURRENT.json | Remove two-file transaction gap | Legacy pointers imported; mirror still exported |

The BM25 implementation was relocated with git mv and the compatibility shim was included in code commit 4b0a0d1. Git records the final files as an implementation addition plus a shim at the old path; runtime imports and legacy pickle resolution are covered by regression tests.

Directory inventory reviewed: itlr runtime package, web frontend/server, tests, eval experiment entrypoints, scripts orchestration, configs, deploy, .github, docs and reports. Their established names express their roles and were retained. `collect` already owns ingestion and `chatbot/llm_client.py` owns generation. Renaming those entire packages would add pickle/import/CLI risk without fixing the current shared-retrieval defect. `itlr/core/chunks.py` remains at its existing path in this group. This is a targeted boundary improvement, not a completed conversion of every module to Clean Architecture. Old/new responsibilities are also recorded in ADR-010.

## Measured experiment

Raw result: reports/chunks_v3_unified_experiment.json; reproducible command:
`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python eval/bench_chunks_v3.py`.

Eight real checked-in documentation snapshots, 98 chunks, eight hand-authored item-level query judgments, E5-base CPU, no CrossEncoder, no generation. Both configurations scored Recall@5/MRR@5/nDCG@5=1.0. Item-mean dense p95=129.07ms; chunk BM25+dense+RRF p95=130.23ms. Mean query+retrieval CPU=113.98/114.98ms. Peak whole-process RSS=1468.86MiB includes model load and both configurations. Query encoding cost is measured once and shared in both totals. The benchmark allows every chunk as candidate; it is not a production pool/load benchmark. No measured quality or speed improvement is claimed. Faithfulness/hallucination/citation accuracy remain null because generation was not run.

## Ponytail review

What this change does: consolidates runtime retrieval responsibilities and makes lifecycle state self-contained. Assumed deployment remains one API process, local Linux storage and cooperating CLI writers.

Review traced search/chat adapters, quick resources, relevance gate, source serialization, generation validation, BM25 pickle/import consumers, version activation/rollback/GC and CI references. Newly found quick-resource bypass was fixed before completion. No unexplained High/Critical finding remains in this group.

Release limitations: all-result FAISS filtering currently materializes chunk scores and BM25 still scans the corpus; large-corpus latency/RAM needs measurement before release. V3 cosine gate needs real off-topic calibration. Existing intent templates remain and are not represented as grounded LLM output. Real CrossEncoder inference and semantic citation entailment remain unverified. Atomic replacement tests show process interruption recovery; they do not simulate device/controller failure or validate network-filesystem durability. Full source-tree renaming, deletion of unproven dead code and speculative dependency removal were avoided.

Not checked: DeepSeek live (paid calls not authorized), PostgreSQL execution, Docker Compose execution (docker/psql/postgres are absent from PATH), browser E2E, full-corpus/passages qrels, neural reranker load test, live monitoring/deployment. Existing mock LLM tests remain part of regression. These are outstanding release gates, not proven failures of those services. No production-ready claim.

Final validation: full Python suite 256 passed, zero skipped in 44.63s (outside sandbox, paid providers disabled by fixtures, OMP/MKL/OpenBLAS=1). Web typecheck/build passed; ESLint zero errors and 20 existing warnings; 59 tests passed with 25.01% line coverage. compileall, pip check and git diff --check passed. No type/lint/coverage rule was weakened. Temporary execution logs: /tmp/itlr-restructure-final.log and /tmp/itlr-unified-benchmark.log.

Packaging verification: initial namespace discovery stalled at metadata; setting namespaces=false
(regular packages all have __init__.py) allowed offline wheel build to complete. The first wheel
then failed asset inspection: zero static assets. Added explicit itlr.api static HTML/JS/CSS package
data; rebuilt wheel successfully and verified all four UI assets, retrieval modules and legacy
BM25 shim are present. No dependency downloads (--no-index --no-deps --no-build-isolation).
