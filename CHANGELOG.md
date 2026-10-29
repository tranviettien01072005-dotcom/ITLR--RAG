# Changelog

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
- **`AGENTS.md` + `docs/PROJECT_MEMORY.md`** — bộ nhớ dự phòng in-repo, đồng bộ với
  Claude-Mem notes #102–#107 (kiến trúc, config không-secret, bugfix + quyết định
  (ADR), lệnh setup/build/test/eval, datasets + metrics thực đo, tech debt);
  AGENTS.md định nghĩa giao thức bắt buộc đầu phiên (search Claude-Mem + đọc AGENTS.md)
  và quy tắc cập nhật memory sau mỗi thay đổi quan trọng.
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
