# ITLR–RAG | Intelligent IT Learning Platform — Changelog

## 2026-10-30 - Verified architecture increment

- Separate offline answer presentation from chatbot orchestration while preserving existing helper imports and Markdown output.
- Fix upload append for provenance catalogs: use the same 10/16-column contract as PostgreSQL sync; reject unsupported headers before writes.
- Log streaming generation failures consistently and remove redundant console fallback branches.
- Add template characterization, catalog regression and Web HTTP health/readiness tests.
- Actual results and release blockers: [architecture checkpoint](reports/ARCHITECTURE_REFACTOR_2026-10-30.md).
- Serialize catalog CSV appends and recompute the last ID inside the write queue; the documented single-worker limit remains.

## 2026-10-30 - Deployment preparation and process boundaries

- Add an opt-in production Compose stack with HTTPS proxy, private Web/API/PostgreSQL and persistent volumes.
- Keep credentials outside Git; document release jobs, backup/recovery and coordinated index/catalog rollback.
- Separate Express composition (`app.ts`) from process lifecycle (`server.ts`); add bounded SIGTERM draining.
- Container startup now serves traffic only: migration/catalog sync must run explicitly before launch.
- Runtime verification deferred at user request; no cloud deployment or new dependency installation.

## 2026-10-30 - SSE transport hardening

- Server and browser reject malformed UTF-8 and incomplete code points at EOF.
- Browser checks complete frame size before JSON parsing and event delivery.
- Regressions reproduced RED -> GREEN; see [checkpoint](reports/PRODUCTION_CHECKPOINT_2026-10-30.md).

## Chưa phát hành — 2026-10-30: correctness và tài liệu sản phẩm

- V3: Top-K không bị cắt ngầm ở 32; tìm tài nguyên loại trùng item trước giới hạn ứng viên;
  truy hồi bằng chứng vẫn giữ nhiều chunk. Cosine được chặn trong [-1, 1], so ngưỡng với sai số float32.
- Hybrid: RRF đếm một tài liệu một lần trong mỗi ranking; pipeline tái sử dụng điểm nền đã tính.
- Evaluation: dùng retrieval model của engine đã nạp, hoạt động khi không có CF; đóng file LTR sau đọc.
- Probe: truyền đường dẫn staging qua môi trường, kiểm tra cả exit code và sentinel.
- Web: chặn redirect có backslash; quyền user được lấy từ database hiện tại sau xác minh JWT.
- Crawler: đồng bộ policy/provenance khi cập nhật; không tái sử dụng full text đã bị thu hồi trong lần
  export tiếp theo. Listing/article không phải 2xx bị từ chối; redirect kiểm robots và rate-limit mỗi hop.
- Viết lại toàn bộ Markdown tracked theo thương hiệu thống nhất; giữ số liệu và phạm vi lịch sử,
  phân biệt implemented/verified/experimental/planned. Không thêm giấy phép hay dịch vụ memory ngoài.
- Kết quả thực chạy và giới hạn triển khai: [Validation](reports/VALIDATION.md).
  Thu hồi policy không sửa artifacts đang active; cần rebuild, probe và activate có kiểm soát.


## 2026-10-30 — BM25 và đóng gói Web (checkpoint lịch sử)

- Sửa BM25 refit, thêm inverted postings và hỗ trợ pickle cũ; ngăn race công bố postings dở.
- Build Web đóng gói EJS/public/schema; bỏ copy trùng trong Dockerfile.
- Viết lại hướng dẫn hiện hành quanh web3000/PostgreSQL/API8000, không yêu cầu Claude-Mem.
- Rà soát Markdown, gắn ngữ cảnh lịch sử, sửa nhãn mô phỏng và kiểm tra local links.
- Bỏ khai báo MIT của package, giữ thông báo bản quyền bên thứ ba.
- Kiểm chứng cuối:260 Python pass/0 skip,59 Web pass; build/typecheck/wheel/links pass,lint20 cảnh báo cũ.
- Bằng chứng, benchmark và giới hạn xem reports/VALIDATION.md.

### Phạm vi lịch sử


Các mục dưới ghi trạng thái tại thời điểm thay đổi, không phải chứng nhận runtime hiện tại.
Phiên bản package hiện vẫn là `1.0.0`; tiêu đề `2.0.0` bên dưới là nhãn lịch sử, không xác nhận một release tag.
Bằng chứng mới nhất: [Validation](reports/VALIDATION.md).

Định dạng theo [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.0.0] - 2026-10-29

### Added — dữ liệu thật + vận hành (crawling & versioned index)
- **Crawler Python** (`itlr/collect/`): `http.py` (HTTPX + retry exponential-backoff,
  robots.txt + Crawl-delay, rate-limit per-host), `extract.py` (chọn content theo mật độ
  `_pick_main`, chống listing-junk), `sources.py`/`adapters.py` (JSON API · RSS · HTML
  listing; `link_pattern` lọc trang mục lục VnExpress), `store.py` (SQLite docs + item_map
  item_id ổn định), `quality.py` (too_short/dup/hash), `chunk.py` (900 chars/overlap 120),
  `runner.py` (lượt chạy + tổng kết `last_run.json`), `normalize.py` (schema ITLR +
  chống trùng legacy, provenance `origin/crawl_license/crawl_lang/crawl_hash`).
- **`scripts/collect_data.py`** — crawl CLI: `--sources`,`--stats-only`,`--verbose`;
  lượt đầu: 85 docs (devto 25 · fCC 10 · MDN 25 · VnExpress 25 snippet-only).
- **`scripts/build_all_v2.py`** — catalog V2 (legacy 5000 + crawl thật, item_id từ 5001)
  → build staging → probe 3 mức → activate nguyên tử → GC keep=3; `--dry-run`,
  `--no-activate`, `--no-probe`, `--with-cf`, `--online`, `--max-items`.
- **`scripts/refresh_pipeline.py`** — cron entry một lệnh (crawl → build nếu có docs mới;
  mọi nguồn lỗi ⇒ không build).
- **Index phiên bản hóa** (`itlr/versioning.py` + `itlr/indexv2.py`): `versions/<id>`,
  MANIFEST probe, `CURRENT.json` ghi nguyên tử, `rollback()`, `garbage_collect(3)`;
  con trỏ được `itlr.config.current_dir()` re-read mỗi lần gọi — engine thấy version mới
  khi restart/reload.
- **Embeddings V2** (`itlr/pipelines/build_embeddings_v2.py`): encode TỪNG CHUNK
  (max 900/overlap 120), vector item = mean + L2 → giữ hợp đồng 1 hàng ↔ 1 item;
  thêm `chunk_meta.pkl`; ANN/faiss + char n-gram như cũ.
- **API admin có token** (`itlr/api/server.py`): `/admin/reload` đòi
  `X-Admin-Token` khớp env `ITLR_ADMIN_TOKEN`; env trống ⇒ 403 (fail-closed).
- **CF thành tùy chọn** (`itlr/engine.py`): thiếu `cf_model.pkl` ⇒ log WARNING, engine
  chạy bình thường; `/api/personas`,`/api/for-you` trả 503 (`CFUnavailable`);
  `/health` và `/admin/reload` báo `"cf": true|false`.
- **`eval/eval_v2_real.py`** — số đo thực trên index active: Recall@5/10, MRR@10,
  NDCG@10 (qrels rule-based, đánh dấu trung thực), latency p50/p95, citation accuracy.
- **Deployment**: `Dockerfile` (healthcheck, smoke-import, var/ volume),
  `docker-compose.yml` (api + refresh profile), `bin/refresh_env.sh`,
  `deploy/DEPLOY.md` (cron + systemd service/timer + rollback + giám sát).
- **Docs**: ADR-005 (CF optional), ADR-006 (nguồn/licensing/robots), ADR-007
  (versioning), ADR-008 (admin token); README phần V2 + sơ đồ build.
- **Tests mới** (+21): `test_collect_utils.py`, `test_http_layer.py`,
  `test_versioning.py`, `test_collect_crawl.py`, `test_collect_runner.py`,
  `test_normalize.py`, `test_index_probe.py`, `test_admin_security_cf.py`,
  `test_build_model_load.py` — tổng: **152 passed / 5 skipped** (tăng ratchet so 131).

### Changed
- `itlr/pipelines/build_model.py`: `load_catalog_items()` — chỉ loại hàng khuyết cột cốt
  lõi (có log), ô tùy chọn rỗng giữ "" thay vì NaN (bug âm thầm nổ 5000 hàng).
- `configs/collect.sources.json` — license mô tả trung thực; VNE thêm `link_pattern`.
- `requirements.txt`/`pyproject.toml` — thêm httpx/beautifulsoup4/feedparser; đóng gói
  theo packages.find (itlr*).
- `.env.example` — ITLR_ADMIN_TOKEN + cấu hình crawler.

### Fixed
- `itlr/collect/extract.py`: stale-attrs crash sau decompose (attrs=None guard) và
  trích xuất rỗng cho fCC (container `post-and-sidebar` khớp nhầm "sidebar") — chọn
  main content theo mật độ thay vì chặt rác cấp cao.
- `scripts/collect_data.py`: precedence bug khi ghi `last_run.json` (mkdir sai đường dẫn).
- `itlr/versioning.py`: `_id()` strftime trên struct_time (crash build V2 lần đầu).

## [1.0.0] - 2026-10-27

### Added
- **DeepSeek làm LLM chính**: `itlr/chatbot/llm_client.py` — tầng LLM thống nhất
  (DeepSeek → OpenAI → Ollama), retry/backoff + timeout, token/chi phí tracking,
  `mask_key` chống lộ key, `LLMError` báo rõ (không nuốt lỗi); chatbot chỉ delegate.
- **SYSTEM_PROMPT rule 10** — chống prompt-injection + bắt buộc CITE `[item_id:ID]`
  (context LLM giờ kèm `item_id` từng item).
- **`itlr/pipelines/generate_interactions.py`** — tương tác MÔ PHỎNG latent-persona
  (1.800 users, seed=7, MIN_HISTORY=5, EXPLORATION_CAP=1); backup interactions cũ
  tại `var/data/interactions_backup_500users.csv`.
- **`scripts/build_all.py`** — build artifacts một lệnh, idempotent, có
  `--dry-run/--force/--step`; artifacts ghi vào `var/artifacts` theo `itlr.config`.
- **`eval/eval_generation.py`** — quality generation đo trực tiếp citation
  `[item_id:ID]` (valid/in-context) + hallucination rate; groundedness/relevancy ghi
  rõ là proxy rule-based; `--llm` fail-fast khi chưa có key.
- **`var/data/eval/offtopic_testset.csv`** — 121 câu hand-curated (60 IT / 61 ngoài
  chủ đề) để chốt ngưỡng cổng off-topic bằng dữ liệu.
- **`AGENTS.md` + `docs/PROJECT_MEMORY.md`** — bộ nhớ trong repo về kiến trúc, cấu hình không chứa secret, ADR, build/test/eval và giới hạn.
  Lịch sử có tham chiếu notes #102–#107; giao thức cũ đó đã được thay bằng đọc và cập nhật
  file trong repo. Không tích hợp hoặc yêu cầu Claude-Mem.
- Kết quả eval mới chạy rc=0: `reports/offtopic_eval.md`
  (AUC 0.9825; ngưỡng hiện 0.55 → F1 0.663; tối ưu F1 0.800 → P 0.881 / R 0.983 / F1 0.929)
  và `reports/generation_eval_template.{csv,md,json}`
  (template: groundedness proxy 0.385, relevancy proxy 0.929, refusal off-topic 0/21,
  false-refusal IT 0/29).
- **`tests/`** — 70 test pytest (path-regression, ANN, pickle-handles, llm_client,
  chatbot adapter, generate_interactions, eval generation, scripts/config,
  API-integration khi đã build artifacts).
- Docs: `README.md`, `CONSTRAINTS.md` (sàn quality), `docs/decisions/ADR-001..004`,
  `pyproject.toml`, `requirements.txt`, `Makefile`, `.env.example`.
- `itlr/config.py`: `ITLR_ARTIFACTS_DIR` (override artifacts cho sandbox/test).

### Fixed
- `eval/*.py` — 12 file tính sai ROOT (`dirname × 3` → ×2; `import itlr` hỏng khi
  chạy từ ngoài repo); `eval/run_all.py` path cũ `scripts/eval/…` → `eval/…`.
- `itlr/core/ann.py` — mặc định `artifacts_dir` tương đối (theo CWD) → dùng
  `config.ARTIFACTS_DIR` lazily; `faiss.read_index` giờ fail-safe; file handle
  `pickle.load/dump(open(...))` → `with`-block (ann, engine, build_model,
  build_embeddings, build_cf).
- `itlr/api/server.py` — prewarm Ollama bỏ lại khi cấu hình DeepSeek/OpenAI key.

### Security
- Không log API key; `.env` được loại khỏi repo (chỉ `.env.example`); mask key
  trong mọi chuỗi log/lỗi LLM (`test_exhausted_retries_raise_llmerror_no_key_leak`).

### Changed
- DeepSeek là mặc định generation; `DEEPSEEK_MODEL=deepseek-flash` override qua env.
  Tên model + base_url đã verify với docs chính thức (https://api-docs.deepseek.com/,
  2026-10-27); chưa verify LIVE call vì môi trường không có `DEEPSEEK_API_KEY`.

## 2026-10-29 — Security/runtime remediation (unreleased)

- Static UI renders external values safely; restricts Markdown and URLs; local scripts and CSP.
- Web requires explicit credentials, validates upload signatures and protects pending attachments.
- Constrain proxy trust and single-worker deployment; bound metric path cardinality.
- Verify artifact hashes/path confinement and pin active directory per engine load.
- Add Python/TypeScript/security CI and offline fixture pipeline regression.
- Full production release remains gated; actual results: reports/FINAL_REMEDIATION.md.

## Local models install — 2026-10-29 (in progress)

Installed Torch 2.15.0+cpu, sentence-transformers 6.2.0, FAISS 1.15.1, pyarrow26.
Model caches: var/hf (E5-base), var/ollama/models (qwen2.5:3b). Ollama executable
0.40.13 in var/ollama/bin; full runtime archive is partial, llama-server not yet present.
Downloads encountered github DNS failures and HF timeouts. Do not claim inference PASS.
Fixed resolve_preset(full HF ID) to preserve registered E5 query/passage prefixes;
regression reproduced FAIL then PASS. Full Python suite:201 passed,5 skipped (33.37s),
before usable neural index. Caches/downloads excluded from git. Claude-Mem unavailable.

## Local model verification complete — 2026-10-29

E5-base weights downloaded, real768d embedding smoke PASS; Qwen2.5:3b downloaded,
SHA256 verified and CPU inference PASS through Ollama0.40.13. V2 build/probe/activate
PASS on5,000 synthetic items (version20261029-204546). Real HTTP health/search/chat200;
API Qwen response57.01s with valid retrieved citation2716. Reranker disabled, CF unbuilt.
Direct80-token Qwen smoke omitted citation; no general groundedness/hallucination claim.
Evidence reports/LOCAL_MODELS.md and raw JSON; startup deploy/LOCAL_MODELS.md.
DeepSeek, PostgreSQL/browser and other release gates remain unverified.

## Audit checkpoint — 2026-10-29 (Ponytail ultra)

Confirmed and fixed rolling-feed false missing detection (explicit complete-inventory opt-in),
strict JSON booleans for collection policy, V2 nDCG reuse of standard logarithmic metric,
and small-catalog self-retrieval probe bounds. Regression tests reproduced failures before fixes.
Full suite outside sandbox: 228 passed / 5 existing conditional skips (233 collected).
Web: 59 passed; typecheck/build pass; lint 0 errors / 20 warnings; line coverage 25.01%.
Sandbox FastAPI TestClient hangs in AnyIO portal; outside-sandbox suite passes.
No paid LLM calls, data deletion, activation, migrations or deployment performed.
V3 chunk-vector retrieval and overlapping refresh safety remain unfinished; live DeepSeek,
PostgreSQL, browser, Docker and production load/quality gates remain unverified.
Evidence and scoped audit/review: reports/AUDIT_2026-10-29.md. Claude-Mem unavailable.

## V3 implementation checkpoint — 2026-10-30

Added real chunk-vector FAISS + existing BM25/RRF retrieval to chatbot semantic path,
optional bounded passage CrossEncoder, chunk citation identity validation and persistence of
chunk vectors. Existing V2 item/API search paths remain; no active index rebuild/activation.
Added Linux lifecycle locks, serialized CLI crawl/build and refresh parent jobs, unique staging IDs,
rollback transition tracking, GC staging/rollback preservation, and load-before-swap engine reload.
Temporary versioned API fixtures replace all 5 artifact-conditional skips without deleting assertions.
Final regression:245 Python passed,0 skipped (44.60s);Web59 passed, coverage lines25.01%.
Real E5 experiment:8 source snapshots/98 chunks,8 hand-authored item qrels; both mean-dense and
chunk-hybrid Recall@5/MRR@5/nDCG@5=1.0;p95=117.41/118.36ms. No quality/speed improvement claimed.
Generation faithfulness/hallucination/citation accuracy unmeasured; no paid calls.
Release blockers:V2 API/off-topic paths, real reranker validation, crash-durable pointer/history,
DeepSeek live,PostgreSQL,Docker/browser and full-corpus eval. Claude-Mem tools unavailable.
Evidence:reports/V3_PROGRESS_2026-10-30.md and reports/chunks_v3_experiment.json.

## Shared V3 retrieval and repository migration — 2026-10-30

Baseline245/0 retained;latest full suite256 Python passed/0 skipped (44.63s),Web59 passed.
Web typecheck/build pass;lint0 errors/20 existing warnings;compileall/diff checks pass.
Search,off-topic,semantic chat and quick resources use itlr.retrieval.service for chunk artifacts;
legacy artifact paths remain. V3 generation now requires valid chunk references per cited item.
BM25 implementation moved with git mv to itlr/retrieval/bm25.py; old core module is a pickle/import shim.
CURRENT.json atomically commits pointer+history with fsync; legacy history file remains a mirror.
Process-exit/restart test proves rollback survives pointer/mirror interruption. Corrupt version
reload preserves loaded engine. No runtime data/index activation,paid call or DB migration.
Real E5 experiment8 docs/98 chunks:item mean vs chunk RRF scores all1.0;p95=129.07/130.23ms;
CPU=113.98/114.98ms per query;whole-process peakRSS1468.86MiB. Generation quality unmeasured.
Mapping/review/release limits:reports/V3_RESTRUCTURING_2026-10-30.md and ADR-010.
Docker/psql/postgres absent from PATH;browser/live DeepSeek/real reranker/full-corpus gates pending.
Claude-Mem tools unavailable; fallback memory updated only, no save_memory claim.

Packaging verification: initial namespace discovery stalled at metadata; setting namespaces=false
(regular packages all have __init__.py) allowed offline wheel build to complete. The first wheel
then failed asset inspection: zero static assets. Added explicit itlr.api static HTML/JS/CSS package
data; rebuilt wheel successfully and verified all four UI assets, retrieval modules and legacy
BM25 shim are present. No dependency downloads (--no-index --no-deps --no-build-isolation).
