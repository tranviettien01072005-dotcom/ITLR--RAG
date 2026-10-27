# AGENTS.md — Hướng dẫn bắt buộc cho agent (OpenCode / Claude / Codex...) làm việc trên repo này

> **Cập nhật:** 2026-10-27 · Duy trì file này mỗi khi repo thay đổi đáng kể.
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

- **ITLR RAG** — hệ thống gợi ý học CNTT + chatbot RAG: catalog 5.000 items (SYNTHETIC),
  interactions CF 1.800 users (SYNTHETIC, seed=7), glossary 360 khái niệm, 19 career roles.
- Pipeline: retrieval (E5 768d + FAISS · TF-IDF + BM25 · RRF) → [tùy chọn] rerank
  cross-encoder + MMR → generation grounded → recommendation CF ("Dành cho bạn").
  Tầng gọi LLM duy nhất là `itlr/chatbot/llm_client.py`
  (chuỗi DeepSeek → OpenAI → Ollama → template offline).
- API FastAPI `itlr.api.server:app` + UI tĩnh; build một lệnh `scripts/build_all.py`
  (artifacts `var/artifacts/*.pkl`, không đưa vào VCS).
- Tổ chức: `itlr/` (package) · `eval/` (entrypoint đánh giá) · `scripts/` · `tests/` · `reports/`.

## 2) Lệnh cốt lõi

```bash
.venv/bin/python -m pytest -q                           # 70/70 test, 0 skip
python scripts/build_all.py [--dry-run|--force|--step retrieval|embeddings_ann|collaborative]
uvicorn itlr.api.server:app --host 127.0.0.1 --port 8000
python eval/run_all.py [--quick|--with-ltr]             # eval rút gọn khi --quick; ltr.md chỉ khi --with-ltr
python eval/eval_offtopic.py                            # AUC/F1 ngưỡng cổng off-topic
python eval/eval_generation.py [--llm]                  # --llm FAIL-FAST nếu thiếu DEEPSEEK_API_KEY
```

- Venv: `.venv` (Python 3.14.4). Cài: `pip install -r requirements.txt` hoặc `pip install -e "[eval]"`.
- LTR (tùy chọn, chậm): `eval/build_ltr.py --no-cross`.
- Tái sinh interactions: `python -m itlr.pipelines.generate_interactions` rồi build lại `--step collaborative`.

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
- Repo **chưa** là git repo; `.gitignore` đã sẵn sàng (var/artifacts bị loại, reports giữ trong repo).

## 7) Lưu ý khi sửa code (từ audit trước)

- Đóng đúng context-manager cho pickle/FAISS; thiết lập FAISS phải `set_ef(64)` khi cần.
- `eval_generation.py --llm` phải giữ FAIL-FAST (rc=2 khi thiếu key); JSON NaN → null.
- Tên file báo cáo từng bị trỏ sai ở nhiều chỗ: dùng `tables_kw_noisy.md`
  (không phải `tables_noisy.md`).
- Không để ký tự rác (CJK/Cyrillic/...) vào .py/.md; nếu thấy xuất hiện trong code mới thì
  sửa ngay, không che bằng fallback.
