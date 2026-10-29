# AGENTS.md — Hướng dẫn bắt buộc cho agent (OpenCode / Claude / Codex...) làm việc trên repo này

> **Cập nhật:** 2026-10-29 · Duy trì file này mỗi khi repo thay đổi đáng kể.
> Phiên bản đầy đủ của "long-term memory" in-text nằm ở `docs/PROJECT_MEMORY.md`.

## 0) Giao thức bắt buộc mọi phiên làm việc

1. **Trước khi phân tích lại dự án**, bắt buộc làm 2 việc:
   - Tìm kiếm **Claude-Mem** (nếu plugin khả dụng — qua tool `search`/`dumb_search` của namespace
     `claude-mem`, hoặc MCP resource tương đương) với từ khóa relevant đến nhiệm vụ hiện tại.
     Ghi chú dài hạn của dự án nằm trong các memory #102…#107 (không tìm thấy thì đọc
     `docs/PROJECT_MEMORY.md`).
   - Đọc **file này (AGENTS.md)** và `docs/PROJECT_MEMORY.md`.
2. **Tiếp tục từ trạng thái gần nhất** — không phân tích lại toàn bộ dự án từ đầu.
3. **Sau mỗi thay đổi quan trọng** (bug fix đáng kể, đổi kiến trúc/config, đánh giá mới):
   - Lưu note vào Claude-Mem bằng tool thật (`save_memory`). Ghi nội dung vào chat/thả trong
     hội thoại là KHÔNG đủ. Tìm duplicate trước khi lưu; không lưu API key/secret vào
     memory hay file nào cả.
   - Cập nhật `AGENTS.md` + `docs/PROJECT_MEMORY.md` + `CHANGELOG.md` cho đồng bộ.
4. Xem to-do/diễn biến phiên trong Claude-Mem `work_state` (tool `work_state_read`), nếu có.

## 1) Dự án là gì (tóm tắt 30 giây)

- **ITLR RAG (V2)** — hệ thống gợi ý học CNTT + chatbot RAG: catalog **5.060 items =
  5.000 legacy synthetic + 60 crawl thật** (dev.to · freeCodeCamp News · MDN Blog
  · VnExpress snippet-only — xem ADR-006); item_id crawl **ổn định từ 5001**.
  Interactions CF 1.800 users (SYNTHETIC, seed=7) — CF là **tùy chọn** (ADR-005:
  thiếu `cf_model.pkl` ⇒ engine vẫn sống, `/api/personas` `/api/for-you` 503).
- Pipeline: retrieval (E5 768d encode TỪNG CHUNK + FAISS · TF-IDF + BM25 · RRF) →
  [tùy chọn] rerank cross-encoder + MMR → generation grounded → CF.
  Tầng gọi LLM duy nhất `itlr/chatbot/llm_client.py`
  (chuỗi DeepSeek → OpenAI → Ollama → template offline).
- **Index theo phiên bản** (ADR-007): build vào `var/artifacts/versions/<id>/` → probe
  3 mức → activate (`CURRENT.json`) → rollback; API không gián đoạn.
- **Crawler** (`itlr/collect/`): httpx + bs4/feedparser, robots.txt + rate-limit +
  retry; SQLite `var/data/collect/crawl.db`; nguồn cấu hình
  `configs/collect.sources.json`.
- API FastAPI `itlr.api.server:app` + UI tĩnh; build một lệnh `scripts/build_all_v2.py`;
  **`/admin/reload` đòi `X-Admin-Token`** khớp `ITLR_ADMIN_TOKEN` (trống ⇒ 403, ADR-008).
- Tổ chức: `itlr/` (package) · `eval/` (entrypoint đánh giá) · `scripts/` · `tests/` ·
  `configs/` · `deploy/` (cron/systemd/Docker) · `reports/`.

## 2) Lệnh cốt lõi

```bash
.venv/bin/python -m pytest tests/                        # 156 passed / 5 skipped (10-29)
python scripts/collect_data.py [--sources a,b]           # crawl (rate-limit + robots)
python scripts/build_all_v2.py [--dry-run|--no-activate|--with-cf|--online]
python scripts/refresh_pipeline.py                       # cron: crawl → build → probe → activate
uvicorn itlr.api.server:app --host 127.0.0.1 --port 8000
python eval/run_evaluation.py --no-rerank --tag _v2      # ablation V2 (qrels rule-based)
python eval/eval_v2_real.py                              # số thực đo: recall/MRR/NDCG + latency + citation
python eval/run_all.py [--quick|--with-ltr]              # eval tổng (legacy, vẫn chạy được)
python eval/eval_offtopic.py                             # AUC/F1 ngưỡng cổng off-topic
python eval/eval_generation.py [--llm]                   # --llm FAIL-FAST nếu thiếu DEEPSEEK_API_KEY
```

- Venv: `.venv` (Python 3.14.4). Cài: `pip install -r requirements.txt`
  hoặc `pip install -e ".[eval,dev]"`.
- Build V2 lần đầu (model HF chưa cache): thêm `--online`.
- Tái sinh interactions: `python -m itlr.pipelines.generate_interactions`
  + `python -m itlr.pipelines.build_cf` (hoặc `build_all_v2.py --with-cf`).

## 3) Cấu hình LLM (không có secret nào trong file này)

- DeepSeek **chỉ làm generation**; OpenAI-compatible; biến môi trường:
  `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL` (mặc định `https://api.deepseek.com`),
  `DEEPSEEK_MODEL` (mặc định `deepseek-flash`; verified với docs chính thức
  https://api-docs.deepseek.com/ ngày 2026-10-27), `DEEPSEEK_RETRIES=3`,
  `DEEPSEEK_TIMEOUT_S=90`, `DEEPSEEK_STREAM_TIMEOUT_S=240`.
- Embedding: `intfloat/multilingual-e5-base` (768d) + FAISS; đổi model ⇒
  `build_all.py --force --step embeddings_ann`.
- Bảo mật: key không log (mask), không commit `.env`, không hardcode key/path — path tập trung
  `itlr/config.py` (override test bằng `ITLR_ARTIFACTS_DIR`), xem ADR-002.

## 4) Sự thật về dữ liệu & nhãn (KHÔNG được pha loãng)

- Catalog + interactions là **synthetic**. Nhãn "human" ở chế độ `--simulate-human` là
  **MÔ PHỎNG** (n=228, kappa≈0.719, đồng thuận ~88%) — cấm tuyên bố là nhãn người thật (ADR-003).
- Retrieval qrels là rule-based từ metadata catalog; CF/off-policy dùng click mô phỏng.
- Generation template mode: citation = 0 → hallucination 0% là trivial; **template không từ chối**
  câu off-topic. Số groundedness/relevancy là proxy rule-based.

## 5) Sàn chất lượng (chi tiết trong `CONSTRAINTS.md`)

Test phải pass · không fallback âm thầm · không lệch path · không secret · trung thực về dữ liệu ·
ratchet mode (không hạ sàn). Review biên bản: `docs/review-2026-10-27.md`; ADR-001…004 trong
`docs/decisions/`.

## 6) Trạng thái đã biết & tech debt (ngày cập nhật file này)

- Thiếu `DEEPSEEK_API_KEY` trong môi trường → test LLM dùng mock; chưa verify DeepSeek live.
- `PRICE_PER_1M` (bảng giá LLM) là ước tính.
- `reports/ltr.md` CHƯA sinh (chưa chạy `--with-ltr`).
- Stage2 reranker chậm (p50 ≈ 6.2s trên CPU) — điểm nghẽn chính; hướng: rerank top-k nhỏ,
  batch, cache, model quantized.
- Cổng off-topic đang dùng ngưỡng 0.55; dữ liệu (121 câu, AUC 0.9825) khuyến nghị 0.800
  (F1 0.929) — nên mở rộng bộ test rồi mới đổi runtime.
- Repo đã được git hóa và đồng bộ GitHub tại `origin/main`; `.gitignore` loại artifacts/runtime data, reports giữ trong repo.

## 7) Lưu ý khi sửa code (từ audit trước)

- Đóng đúng context-manager cho pickle/FAISS; thiết lập FAISS phải `set_ef(64)` khi cần.
- `eval_generation.py --llm` phải giữ FAIL-FAST (rc=2 khi thiếu key); JSON NaN → null.
- Tên file báo cáo từng bị trỏ sai ở nhiều chỗ: dùng `tables_kw_noisy.md`
  (không phải `tables_noisy.md`).
- Không để ký tự rác (CJK/Cyrillic/...) vào .py/.md; nếu thấy xuất hiện trong code mới thì
  sửa ngay, không che bằng fallback.

## Security remediation — 2026-10-29 (current session)

Preserved pre-existing uncommitted Python and web changes. Added safe static rendering/CSP,
fail-closed web configuration, upload signature/access boundaries, single-worker/proxy constraints,
SHA256 artifact inventory/path confinement and CI gates (ADR-009).
Actual runtime differs from historical memory: Python 3.14.3, no neural model cache/artifacts;
Node22 downloaded to /tmp for web checks. See reports/FINAL_REMEDIATION.md for authoritative
current test counts, dependency audit and unverified release gates. Historical benchmark numbers
are not current execution evidence. Claude-Mem tools unavailable; no save_memory call claimed.

Current remediation evidence: Python 200 passed/5 pre-existing skips; web 22 passed;
full neural RAG/DeepSeek/PostgreSQL/browser remain NOT VERIFIED.

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
