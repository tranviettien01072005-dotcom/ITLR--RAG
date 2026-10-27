# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
