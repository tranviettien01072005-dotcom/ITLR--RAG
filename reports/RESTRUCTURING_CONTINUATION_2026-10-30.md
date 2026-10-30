# Tái cấu trúc và chuẩn hóa tài liệu — 2026-10-30

Checkpoint refactor: **Final architecture & maintainability hardening** ở cuối tài
liệu: **410 Python PASS/0 skip, 132 Web PASS**, coverage **65,71% / 45,31%**.
Các checkpoint bên dưới trước mục đó là lịch sử; production vẫn **NO-GO**.
Checkpoint mới hơn về retrieval/release: [release validation](RELEASE_VALIDATION_2026-10-30.md),
414 Python PASS và 132 Web PASS; chưa đo neural/generation hoặc chạy staging.

## Phạm vi và baseline

HEAD `f8ad595`, nhánh `main`. Kế thừa toàn bộ working tree của checkpoint
streaming; không commit/push, migration, activation hoặc gọi API trả phí.
Baseline được người dùng chấp nhận: 386 Python PASS/0 skip, 124 Web PASS.

Đã kiểm kê 137 module Python và 51 tài liệu Markdown được Git theo dõi.
[Inventory](restructure-inventory.json) ghi imports, kích thước, số hàm và phân
loại tài liệu. Đây là graph tĩnh gồm cả deferred imports, không chứng minh runtime
không có cycle. Inventory không bao gồm dependencies bên ngoài và file untracked.

## Before / After

| Vấn đề | Before | After |
|---|---|---|
| P1: snapshot usage làm lộ mutable state | Caller sửa bucket làm hỏng counters nội bộ; regression FAIL | Copy từng bucket dưới lock; regression PASS |
| P2: helper cấu hình thừa | `_pointer_file` không có caller trong Python repo | Bỏ private helper không dùng; giữ resolver và public path API |
| P2: chuyển kiểu đường dẫn dư | Builder dùng Path(str(Path)) | Path trực tiếp, giữ hỗ trợ giá trị path-like |
| ADR-011 không khớp checkpoint | Ghi collection blocker Linux-only như trạng thái hiện hành | Chuyển sang lịch sử; giữ gate Linux runtime/staging |
| Tài liệu kiến trúc | Bản đồ module bằng bảng | Bổ sung Mermaid online/offline, lifecycle và compatibility |
| Navigation và trạng thái | Nhiều checkpoint nối tiếp, khó xác định kết quả mới nhất | Mục trạng thái hiện hành và liên kết inventory/validation |

Không đổi tên module public hoặc chia chatbot/recommender theo số dòng. Hai module
lớn nhất là chatbot 971 dòng, recommender 927 dòng tại thời điểm audit; cần phân
tích trách nhiệm và characterization sâu hơn trước khi tách. Không xóa compatibility
shim, CLI bootstrap hoặc import chỉ vì static scan không thấy caller.

## Module map và dependency direction

Trước và sau giữ: Web routes → services/DB/HTTP adapter → FastAPI → engine →
retrieval/chatbot. Ingestion SQLite → catalog → builders → staging/probe →
pointer/history → engine. Provider SDK ở shared LLM client. Chi tiết và diagram:
[architecture](../docs/ARCHITECTURE.md).

Không thay algorithm, model, cosine threshold, RRF, Top-K, API/schema, SSE,
V2/V3 artifact layout hoặc pickle paths. Thay đổi snapshot ngăn caller ghi ngược
vào state nội bộ; hình dạng dữ liệu trả về giữ nguyên.

## Tài liệu và bằng chứng

Inventory phân loại reports là historical evidence, ADR là decision record và
phần còn lại là guidance cần kiểm tra theo ngữ cảnh. Không xóa hoặc viết lại số
liệu audit lịch sử. README, memory, validation và deployment trỏ đến checkpoint
hiện tại; ADR-011 được sửa status. Các hướng dẫn cũ không tự cấp quyền publish.

Raw logs: `restructure-red.log`, `restructure-targeted.log`,
`restructure-python.log`, `restructure-web.log`. Compileall và pip check PASS.
Web typecheck/lint/build PASS; 124 tests/25 files PASS, line coverage 45.01%.
Full Python: **387 PASS / 0 skip, 91.94s**, coverage 65% làm tròn
(5574 statements, 1952 missed). Baseline 386 → 387 do thêm một regression;
khác thời gian suite không phải benchmark performance. Targeted client/config/
Markdown: **47 PASS**. Test cache có một warning quyền ghi; suite exit code 0.

## Giới hạn và release decision

Maintainability được cải thiện ở những vị trí đã xác minh; chưa có bằng chứng
chứng nhận toàn repository hết code chết hoặc duplication. Chưa có parser Mermaid
trong môi trường: diagram được review cú pháp thủ công, không tuyên bố render PASS.
Không refactor configs/deploy/tests chỉ để đồng nhất hình thức.
Docker/PostgreSQL/HTTPS staging, backup/restore, Linux lifecycle và đánh giá neural/
generation độc lập chưa chạy trong checkpoint này. **NO-GO cho production**.


## Enterprise continuation - working tree baseline 387/124

This section supersedes the scoped status above for the current refactor only.
The earlier section and its evidence remain historical. No paid calls, migrations,
runtime artifact writes, commits or pushes were performed.

### Responsibility changes and compatibility

| Before | After | Contract retained |
|---|---|---|
| Catalog display cleanup inside recommender.py | core/display.py owns display formatting | Original names remain imported from recommender; retrieval/tokenize module paths unchanged |
| Provider history/fallback adapters inside chatbot.py | chatbot/llm_adapter.py owns adaptation | Original helper imports and chatbot call/patch points remain |
| Chat validation/persistence/SSE inside general api.routes.ts | routes/chat.handlers.ts owns chat handlers | API router keeps URLs, auth ordering and direct route registration |
| Unused imports in ingestion/tests | Removed 4 verified unused imports | Re-exports, BM25 shim and side-effect imports retained |
| Several stale README checkpoints and appended navigation | One product/development/operations overview | Dated metrics kept in historical reports, not presented as current |
| Inconsistent ADR section headings | 11 ADRs have Context/Decision/Alternatives/Consequences/Status | Decision content and historical evidence preserved; added comparison sections are editorial clarification |

Six moved Python functions have identical ASTs before/after; source bodies of both
Web chat handlers and their schema were moved without changing logic. Full suites
cover the integration. No algorithms, thresholds, weights, embedding models,
PostgreSQL schema, artifact filenames or existing public module names changed.
The three new files own cohesive responsibilities; no factory/service hierarchy
or dependency was added. Existing larger orchestration modules are retained where
a further split would require broader characterization rather than cosmetic moves.

Orchestration source sizes: chatbot.py **971 → 932**, recommender.py **927 → 884**,
api.routes.ts **465 → 403** lines. Responsibility moves redistribute code; these
numbers do not claim net code deletion, speedup or improved algorithm quality.
No existing file was renamed or removed; three cohesive implementation files were
added. This continuation fixes no new behavioral defect; it preserves the prior
snapshot/stream fixes and tests their compatibility through the refactor.

### Fresh validation and Before/After

| Gate | Before | After |
|---|---|---|
| Python full suite | 387 PASS / 0 skip | 387 PASS / 0 skip, 145.77s |
| Python statement coverage | 3622/5574 = 64.98% | 3626/5578 = 65.01% |
| Web full suite | 124 PASS / 25 files | 124 PASS / 25 files |
| Web line coverage | 609/1353 = 45.01% | 609/1353 = 45.01% |
| Focused Python presentation/citations/artifacts/scripts | 35 PASS | 35 PASS |
| Focused Web chat/SSE/realtime | 15 PASS | 15 PASS |
| Adapter/citation/presentation after extraction | Existing regressions | 26 PASS |
| Typecheck / lint / build | Prior baseline | PASS |
| Compileall / pip check | Prior baseline | PASS |
| Markdown local paths and anchors | One stale README anchor found after rewrite | All inventory paths/anchors resolve |
| ADR sections | Mixed headings / missing standalone fields | 11/11 complete |

Final documentation/path gate after rewrite: **19 PASS** in
`enterprise-docs.log` (Markdown paths plus evaluation CLI/path checks).
Final self-check also asserted exact Web handler/schema source parity after
normalizing function registration signatures, old/new helper object identity,
and legacy pickle GLOBAL resolution for recommender.tokenize and core.bm25.BM25Index:
**PASS**. All 53 document paths/anchors resolved again after the final edits.

Raw logs: enterprise-before-python.log, enterprise-after-python.log,
enterprise-before-web.log, enterprise-after-web.log, enterprise-adapter.log,
enterprise-python.log, enterprise-web.log. Statement coverage JSON:
enterprise-python-coverage.json. Test duration is not a retrieval speed benchmark.
One pytest cache permission warning remains; no skips or weakened assertions added.
An initial extraction syntax error and unused Web import were caught by typecheck/
lint, fixed, and all final gates rerun successfully.

### Graph and audit limits

No top-level Python or static TypeScript import cycle was detected. The deferred
config/versioning/locking cycle remains; lazy resolution is preserved intentionally.
Static import analysis does not prove absence of dynamic cycles. Exact duplicate
top-level function scan found two small independent vroot test fixtures; they are
retained to keep each lifecycle suite self-contained. Unused import candidates
that are compatibility re-exports were not deleted.

The inventory is a structural/source review with local regression evidence,
not a claim of exhaustive line-by-line security or algorithm review. No module
was marked dead merely because a static caller search was empty. Tests, fixtures,
source configs and deployment templates were read by the structural audit;
runtime gates apply only to the installed local environment.

Mermaid blocks have balanced fences and recognized flowchart declarations, but
parser/render is BLOCKED (not installed). Docker/PostgreSQL/HTTPS staging,
backup/restore, Linux target lifecycle, neural/reranker and independent generation
evaluation remain unverified in this checkpoint. No dependency installation was
needed. Production verdict: **NO-GO**. Maintainability improves in the extracted
responsibilities and documentation navigation; no numeric maintainability score
is claimed.

### Full module/configuration inventory

Status Retained means structural review completed and no safe demonstrated reason
to modify behavior; it does not mean every runtime branch was exercised. Refactored
identifies this continuation's source changes. The machine-readable import graph
and review limits are in [enterprise-inventory.json](enterprise-inventory.json).

| File | Status | Review outcome |
|---|---|---|
| `Dockerfile` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `compose.production.yml` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `configs/collect.sources.json` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `configs/curated.resources.json` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `deploy/Caddyfile` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `deploy/api.env.example` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `deploy/compose.env.example` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `deploy/postgres.env.example` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `deploy/web.env.example` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `eval/adapt_real_data.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/bench_chunks_v3.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/bench_latency.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/build_ltr.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/eval_cf.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/eval_fixture.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/eval_generation.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/eval_lexical_real.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/eval_off_policy.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/eval_offtopic.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/eval_v2_real.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/evaluate_human.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/make_judgments.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/prepare_labeling_sheet.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/run_all.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `eval/run_evaluation.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `itlr/__init__.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/api/__init__.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/api/__main__.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/api/ratelimit.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/api/server.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/chatbot/__init__.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/chatbot/chatbot.py` | Refactored | Responsibility extraction or verified unused import cleanup; full regression passed. Legacy helper/module re-exports explicitly preserved. |
| `itlr/chatbot/citations.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/chatbot/intent_router.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/chatbot/knowledge_base.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/chatbot/llm_adapter.py` | Refactored | Responsibility extraction or verified unused import cleanup; full regression passed. |
| `itlr/chatbot/llm_client.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/chatbot/opencode_client.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/chatbot/presentation.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/chatbot/query_understanding.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/collect/__init__.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. Legacy helper/module re-exports explicitly preserved. |
| `itlr/collect/adapters.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/collect/chunk.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/collect/extract.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/collect/http.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/collect/normalize.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. Legacy helper/module re-exports explicitly preserved. |
| `itlr/collect/quality.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/collect/runner.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/collect/sources.py` | Refactored | Responsibility extraction or verified unused import cleanup; full regression passed. |
| `itlr/collect/store.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/collect/url_util.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/config.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. Deferred cycle retained; changing lazy initialization would alter runtime behavior. |
| `itlr/core/__init__.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/core/ann.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/core/bm25.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. Legacy helper/module re-exports explicitly preserved. |
| `itlr/core/chunks.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/core/display.py` | Refactored | Responsibility extraction or verified unused import cleanup; full regression passed. |
| `itlr/core/embeddings.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/core/pipeline.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/core/rag.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/core/recommender.py` | Refactored | Responsibility extraction or verified unused import cleanup; full regression passed. |
| `itlr/core/rerank.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/data/__init__.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/data/generate_interactions.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/data/generate_items.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/engine.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/eval/__init__.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/eval/cf_eval.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/eval/diversity.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/eval/loader.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/eval/ltr_features.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/eval/metrics.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/eval/off_policy.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/eval/significance.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/indexv2.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/locking.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. Deferred cycle retained; changing lazy initialization would alter runtime behavior. |
| `itlr/pipelines/__init__.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `itlr/pipelines/build_cf.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `itlr/pipelines/build_embeddings.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `itlr/pipelines/build_embeddings_v2.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `itlr/pipelines/build_model.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `itlr/pipelines/generate_interactions.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `itlr/retrieval/__init__.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/retrieval/bm25.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/retrieval/service.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/utils/__init__.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/utils/repickle.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/utils/runtime_patches.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `itlr/versioning.py` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. Deferred cycle retained; changing lazy initialization would alter runtime behavior. |
| `scripts/build_all.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `scripts/build_all_v2.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `scripts/collect_curated.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `scripts/collect_data.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `scripts/export_web_catalog.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `scripts/import_curated_snapshot.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `scripts/refresh_pipeline.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `scripts/verify_local_models.py` | Retained | Retained after structural review; offline entrypoints kept to avoid unproven behavioral change. |
| `tests/conftest.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_admin_security_cf.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_ann.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_ann_active_version.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_api_hardening.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_api_integration.py` | Refactored | Responsibility extraction or verified unused import cleanup; full regression passed. |
| `tests/test_artifact_integrity.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_audit_regressions.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_bm25_refit.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_build_all_v2_cli.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_build_model_load.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_catalog_export_safety.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_chatbot_llm_adapter.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_chatbot_presentation.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_chatbot_retrieval_fixes.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_chunk_contract.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_chunks_v3.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_collect_crawl.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_collect_reconcile.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_collect_runner.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_collect_store_close.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_collect_utils.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_curated_collection.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_embedding_presets.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_engine_reload.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_env_examples.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_eval_generation.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_eval_integrity.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_eval_loader.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_eval_metrics_diversity.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_eval_scripts_paths.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_generate_interactions.py` | Refactored | Responsibility extraction or verified unused import cleanup; full regression passed. |
| `tests/test_grounded_citations.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_http_layer.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_index_probe.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_lexical_real_eval.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_lifecycle_robustness.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. Duplicated small vroot fixture retained for independent test setup. |
| `tests/test_llm_client.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_locking.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_markdown_links.py` | Refactored | Responsibility extraction or verified unused import cleanup; full regression passed. |
| `tests/test_normalize.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_offtopic_gate.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_pickle_handles.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_pipeline_fixture.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_rag_query_utils.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_real_source_text.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_retrieval_service.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_scripts_and_configs.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_significance.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_static_security.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `tests/test_versioning.py` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. Duplicated small vroot fixture retained for independent test setup. |
| `web/Dockerfile` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/app.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/app.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/config/catalog.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/config/env.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/config/env.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/db/check.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/db/migrate.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/db/pool.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/db/seed-courses.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/db/sync-courses.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/db/types.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/middleware/auth.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/middleware/auth.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/middleware/security.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/middleware/security.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/middleware/uploads.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/middleware/uploads.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/routes/admin-login.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/routes/admin-security.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/routes/admin.routes.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/routes/api.routes.ts` | Refactored | Responsibility extraction or verified unused import cleanup; full regression passed. |
| `web/src/routes/auth-security.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/routes/auth.routes.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/routes/chat-page.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/routes/chat.handlers.ts` | Refactored | Responsibility extraction or verified unused import cleanup; full regression passed. |
| `web/src/routes/chat.routes.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/routes/learning.routes.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/routes/learning.routes.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/routes/media-range.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/routes/pages.routes.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/routes/realtime-lifecycle.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/routes/social.routes.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/routes/upload-extraction.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/server.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/catalog-csv.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/chat-client.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/services/chat-history.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/services/chat-history.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/chat-stream.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/services/chat-stream.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/dataset-extract.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/services/dataset-extract.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/dataset.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/services/dataset.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/http-range.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/learning.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/services/learning.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/mailer.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/markdown.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/services/markdown.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/password.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/posts.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/realtime.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/recommender-stream.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/services/recommender.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/social.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/services/social.ts` | Retained | Retained after structural review; runtime contracts kept to avoid unproven behavioral change. |
| `web/src/services/static-ui.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |
| `web/src/views/views.test.ts` | Retained | Retained after structural review; test fixtures and assertions kept to avoid unproven behavioral change. |

### Full Markdown inventory

The original tracked inventory has 51 files. The two prior untracked checkpoint
reports are also included, giving 53 reviewed documents. Historical evidence is
retained; current guidance is linked to fresh validation rather than rewriting old
measurements. Mermaid render remains separately blocked.

| File | Status | Category / review outcome |
|---|---|---|
| `AGENTS.md` | Refactored | current guidance; Structure, local links and contracts checked; external commands not all executed. |
| `CHANGELOG.md` | Refactored | current guidance; Structure, local links and contracts checked; external commands not all executed. |
| `CONSTRAINTS.md` | Refactored | current guidance; Structure, local links and contracts checked; external commands not all executed. |
| `README.md` | Refactored | current guidance; Structure, local links and contracts checked; external commands not all executed. |
| `RESEARCH_ITLR.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `data/README.md` | Reviewed | current guidance; Structure, local links and contracts checked; external commands not all executed. |
| `deploy/DEPLOY.md` | Refactored | current guidance; Fix README testing anchor after navigation rewrite; operational commands preserved. |
| `deploy/LOCAL_MODELS.md` | Reviewed | current guidance; Structure, local links and contracts checked; external commands not all executed. |
| `deploy/PRODUCTION.md` | Refactored | current guidance; Structure, local links and contracts checked; external commands not all executed. |
| `docs/ARCHITECTURE.md` | Refactored | current guidance; Structure, local links and contracts checked; external commands not all executed. |
| `docs/PROJECT_MEMORY.md` | Refactored | current guidance; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-001-deepseek-primary-llm.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-002-centralized-artifact-paths.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-003-synthetic-interactions-policy.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-004-evaluation-design.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-005-cf-optional-decoupling.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-006-data-sources-licensing.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-007-artifact-versioning.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-008-admin-token.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-009-security-runtime-boundaries.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-010-shared-retrieval-and-atomic-state.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/decisions/ADR-011-chatbot-presentation-and-catalog-contract.md` | Refactored | ADR; Structure, local links and contracts checked; external commands not all executed. |
| `docs/review-2026-10-27.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `docs/superpowers/plans/2026-10-29-itrl-v2.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `docs/superpowers/specs/2026-10-29-itrl-v2-design.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/ARCHITECTURE_REFACTOR_2026-10-30.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/AUDIT_2026-10-29.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/AUDIT_INCREMENT_2026-10-30.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/AUDIT_PORTABILITY_2026-10-30.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/BANDIT_TRIAGE_2026-10-30.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/FINAL_REMEDIATION.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/HARDENING_STREAM_2026-10-30.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/LOCAL_MODELS.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/PONYTAIL_AUDIT.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/PONYTAIL_REVIEW.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/PRODUCTION_CHECKPOINT_2026-10-30.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/RESTRUCTURING_CONTINUATION_2026-10-30.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/SKILLS_INVENTORY.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/V2_PRODUCT.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/V3_PROGRESS_2026-10-30.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/V3_RESTRUCTURING_2026-10-30.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/VALIDATION.md` | Refactored | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/cf_eval.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/generation_eval_template.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/human_eval.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/latency.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/off_policy.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/offtopic_eval.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/tables.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `reports/tables_kw_noisy.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `tasks/plan.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `tasks/todo.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |
| `web/SECURITY_REMEDIATION.md` | Retained | historical evidence/plan; Preserve dated evidence; current claims defer to validation. |


## Final architecture & maintainability hardening — 2026-10-30

### Kết quả và phạm vi

Kế thừa working tree baseline **387 Python PASS / 124 Web PASS**, coverage
**65,01% statements / 45,01% lines**. Không commit/push, migration, paid API,
cloud deployment hoặc thay dữ liệu/artifacts runtime. Bốn nhóm lỗi thực tế được
tái hiện trước khi sửa; không thay model, scoring, threshold hoặc schema.

| Finding | Before / RED | After / GREEN |
|---|---|---|
| P1: OpenAI-compatible text completion bỏ qua finish reason không hoàn tất | 4 stream + 4 non-stream cases FAIL | Helper validation dùng chung từ chối length/filter/tool completion; partial stream không retry |
| P1: Ollama nuốt malformed/error JSON và chấp nhận EOF/truncation | 5 cases FAIL trước fix | JSON/schema/error/terminal checks fail-closed; timeout chuyển thành LLMError; thêm valid completion và type-boundary tests |
| P2: SSE parser nhận event sau done | 4 cases FAIL | Từ chối mọi data event sau done, vẫn cho phép heartbeat không có data |
| P2: Ollama startup prewarm không đóng response | 2 cases FAIL cả read success/error | Context manager đóng response trên mọi đường thoát |

Regression mới cho history window/role filtering/input immutability, strict fallback,
generator cancellation, route authorization order và actual unauthenticated denial.
Provider behavior được thử qua SDK/HTTP fakes, không phải inference live.

### Architecture Before / After

Dependency map giữ nguyên: Web routes → chat handlers → history/recommender adapter →
HTTP → FastAPI → engine → retrieval/chatbot → LLM adapter/client. Offline ingestion,
builders và versioning không đổi. Finish-reason validation được tập trung trong một
helper dùng cho chat và stream; transport errors không cần một framework retry mới.

Ba boundary extraction trước tiếp tục được giữ. Không tìm thấy lý do đã chứng minh
để gộp lại hoặc thêm DI container. Runtime import smoke của config, locking, versioning,
recommender, chatbot, retrieval service và API thành công khi socket connections bị
chặn; import không khởi động model/network inference trong phép kiểm đó. Console/env
setup khi import vẫn tồn tại có chủ đích; không tuyên bố mọi module hoàn toàn side-effect-free.
Deferred config/versioning/locking cycle được giữ để bảo toàn lazy configuration;
smoke không chứng minh mọi thứ tự dynamic import hoặc mọi nhánh runtime.

Không xóa public export hoặc module chỉ vì thiếu caller nội bộ. Legacy
opencode_client.get_ai_response chưa có caller trong application graph, nhưng là
entrypoint import được; giữ để tránh phá consumer ngoài repo, không dùng làm provider
mặc định. BM25 pickle shim và alias helper cũ vẫn được giữ.

Code bị loại bỏ trong checkpoint này là nhánh **except/continue nuốt JSON lỗi** của
Ollama, có RED → GREEN chứng minh tác động. Không có file/module nào bị xóa hoặc đổi tên.
Thêm validation helper có hai caller thực tế; không thêm dependency ứng dụng.

### Fresh verification

| Gate | Baseline | Final |
|---|---|---|
| Python full suite | 387 PASS / 0 skip | **410 PASS / 0 skip**, 80,83s |
| Python statements | 3626/5578 = 65,01% | **3679/5599 = 65,71%** |
| Web full suite | 124 PASS | **132 PASS**, 25 files, không skip mới |
| Web lines | 609/1353 = 45,01% | **614/1355 = 45,31%** |
| llm_adapter coverage | Baseline file đã tách | **100% statements** |
| llm_client coverage | Baseline file dùng chung | **81,85% statements** |
| API server coverage | Baseline API | **88,59% statements** |
| Typecheck / ESLint / build | Baseline PASS | **PASS** |
| Compileall / pip check | Baseline PASS | **PASS** |
| Documentation/path tests | Baseline | **19 PASS** |
| Runtime import smoke, network blocked | Chưa chạy trong checkpoint này | **PASS**, 7 module entrypoints |
| Online npm audit | Kết quả cũ không tái sử dụng | **0 vulnerabilities**, exit 0 |
| Online pip-audit venv ứng dụng | Kết quả cũ không tái sử dụng | **88 distributions, 0 advisories, 0 skipped**, exit 0 |
| Bandit full scan itlr/scripts | Không coi là scanner sạch | **0 High / 27 Medium / 47 Low**, exit 1 vì còn findings |
| Mermaid render | Tool không có | **NOT VERIFIED** |

Log chính: final-python.log, final-web.log, final-docs.log, final-import-smoke.log.
RED evidence: final-python-red.log, final-nonstream-red.log, final-ollama-red.log,
final-prewarm-red.log, final-web-red.log. Vitest RED dùng name filter nên báo các
test không được chọn là skipped; không có skip được thêm vào source hoặc full suite.
Full Python run cuối thay thế các lượt 398/406 tests trước đó; các số trung gian
không được dùng làm kết quả cuối. Một pytest cache permission warning còn tồn tại.

### Security triage và giới hạn

[Bandit triage](final-bandit-triage.json) ghi từng vị trí/rule/severity và lý do:
22 pickle-load Medium chấp nhận có điều kiện trusted builder/ACL; 5 URLopen Medium
yêu cầu URL/operator/network boundary. Low gồm RNG synthetic/eval, imports pickle/
subprocess, subprocess argument-list và best-effort diagnostics/extraction. Chấp
nhận có điều kiện không có nghĩa rủi ro đã được loại bỏ; không thêm nosec/suppression.

[Raw Bandit](final-bandit.json), [pip-audit](final-pip-audit.json) và
[npm audit](final-npm-audit.json) là kết quả mới. Scanner chạy trong venv công cụ riêng
dưới var/cache, không sửa requirements/lockfiles hoặc venv ứng dụng.
[Secret pattern scan](final-secret-scan.json) chỉ quét UTF-8 files tracked với
mẫu bounded, tìm một test fixture key giả, không in giá trị. Không thay thế full
secret scanner hoặc kiểm tra Git history/local .env.

### Content review toàn bộ 53 Markdown

[Content review từng file](final-document-review.json) ghi trạng thái, nội dung đối
chiếu, headings và environment references của toàn bộ 53 tài liệu. Không chỉ kiểm links:
đã đối chiếu ownership, provider selection, generation/SSE semantics, config paths,
API endpoints, CLI entrypoints, licensing/provenance statements và scope của metrics.
Lệnh migration/deployment/model download trong tài liệu chỉ được đối chiếu nguồn,
không thực thi trên runtime trong checkpoint này. External prices/licenses hoặc
model availability không được tái xác nhận; các ghi chép lịch sử không trở thành
khẳng định hiện hành.

Sửa sai nội dung cụ thể ở ADR-009: formatter UI tĩnh API vô hiệu hóa Markdown links,
nhưng Web markdown-it cho phép links qua URL validation. Cập nhật README/architecture/
adapter docstring để mô tả strict fallback, provider selection, terminal errors và
giới hạn usage accounting. Memory/validation tách rõ số mới với journal lịch sử.
Các report/plan đúng ngữ cảnh được giữ, không viết lại số liệu để tạo thay đổi.

Mermaid đã được review cấu trúc, fences và flow direction; mmdc/mermaid parser không
có sẵn nên render vẫn NOT VERIFIED. Local paths/anchors đã được kiểm tra trên đủ
53 file; không có link lỗi được phát hiện.

### Refactored / Retained / Blocked

| Nhóm/file | Status | Lý do |
|---|---|---|
| itlr/chatbot/llm_client.py | Refactored | Shared finish validation; fail-closed Ollama completion/error contract |
| itlr/api/server.py | Refactored | Scope response của prewarm bằng context manager |
| itlr/chatbot/llm_adapter.py | Refactored | Docstring đúng strict/provisional contract; logic adapters giữ nguyên |
| web/src/services/chat-stream.ts | Refactored | Guard terminal done |
| Python client/adapter/API tests và Web chat/parser/auth tests | Refactored | Regression và tăng coverage các boundary rủi ro |
| README, Architecture, Memory, AGENTS, Constraints, Changelog, Validation, ADR-009 | Refactored | Sửa content mismatch và cập nhật fresh evidence |
| Ba extraction trước, V2/V3, CSV, crawler, artifact lifecycle | Retained | Full regression PASS; không có bằng chứng cần đổi behavior |
| Deferred cycle, compatibility aliases, opencode legacy export | Retained | Lazy config/public import compatibility, không xóa theo static absence |
| Docker/PostgreSQL/HTTPS/backup/restore/Linux target runtime | Blocked | Không có staging/toolchain để kiểm chứng trong môi trường này |
| Mermaid render, neural/reranker/generation human evaluation | Blocked | Thiếu renderer hoặc model/labels/runtime; NOT VERIFIED/NOT MEASURED |

### Remaining limitations và release decision

- OpenAI-compatible stream thiếu finish metadata vẫn giữ hành vi legacy; không khẳng
  định phát hiện mọi trường hợp EOF upstream. Các non-stop reason tường minh bị từ chối.
- Streaming usage/cost chưa được accounting đầy đủ; bảng giá là estimate.
- Bộ test fake và valid citation ID không chứng minh semantic faithfulness/hallucination.
- Trusted pickle, local Linux locking, one worker/replica và cross-service release
  consistency vẫn là operational contracts; không cung cấp distributed guarantees.
- Cần staging Linux: Docker build/Compose, PostgreSQL migration/concurrency, HTTPS/
  authenticated E2E, restore drill và rollback; sau đó neural/reranker và independent
  generation evaluation trước khi xem xét production release.

Maintainability được củng cố bằng validation dùng chung, error contract rõ và
regression ở các boundary thực tế. Không chấm điểm enterprise certification.
**Production decision: NO-GO.**
