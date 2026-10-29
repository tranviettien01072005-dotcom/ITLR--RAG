# ITLR RAG — IT Learning Recommender & Chatbot (RAG + CF + DeepSeek)

Hệ thống gợi ý & hỏi đáp cho học CNTT, gồm 3 nòng cốt:

1. **Retrieval đa tầng** — TF-IDF + BM25 (từ vựng) · Embedding đa ngôn ngữ
   (`intfloat/multilingual-e5-base`, thêm query/passage prefix đúng chuẩn E5) · RRF kết
   hợp · ANN FAISS · Cross-Encoder `BAAI/bge-reranker-base` + MMR diversity.
2. **CF (collaborative filtering)** — item-item cosine trên tương tác MÔ PHỎNG
   (1.800 users, seed=7) cho trang "Dành cho bạn" cá nhân hóa.
3. **Chatbot RAG** — cổng off-topic (chấm điểm tương đồng), khái niệm-trước (glossary
   360 khái niệm), gen câu trả lời bằng **DeepSeek (OpenAI-compatible)**, fallback
   OpenAI → Ollama local → template offline. Câu trả lời phải grounded: chỉ trích
   catalog/tài liệu đã kiểm chứng, chống prompt-injection, cite `[item_id:ID]`.

> **Lưu ý trung thực về dữ liệu:** catalog (5.000 items) và interactions (12k → 1.800
> users) đều là dữ liệu **synthetic** sinh/maintained bởi repo này — KHÔNG phải người thật.
> Nhãn "human" trong `eval/` ở chế độ `--simulate-human` là nhãn MÔ PHỎNG (dùng để chạy
> hết pipeline), phải thay bằng nhãn người thật trước khi báo cáo chính thức.

## V2 — dữ liệu thật tự thu thập (crawler) + index theo phiên bản

V2 bổ sung (khởi từ 2026-10-29, giữ nguyên 3 nòng cốt trên):

1. **Crawler** (`itlr/collect/`) nguồn công khai hợp pháp: dev.to (JSON API,
   full-text) · freeCodeCamp News (RSS, CC BY-SA 4.0) · MDN Blog (RSS, CC BY-SA 2.5) ·
   VnExpress Công nghệ (HTML, **snippet-only** vì chưa có giấy phép mở). Retry/backoff,
   robots.txt, rate-limit per-host, chuẩn hóa URL, chống trùng, lọc chất lượng, nguồn
   cấu hình trong `configs/collect.sources.json`. Dữ liệu: SQLite `var/data/collect/crawl.db`.
2. **Index theo phiên bản** (`itlr/versioning.py`, ADR-007): build vào
   `var/artifacts/versions/<id>/` → **probe 3 mức** (validate · self-retrieval TF-IDF ·
   engine subprocess) → activate ghi nguyên tử `CURRENT.json` → rollback một lệnh. API
   sống không gián đoạn; probe fail ⇒ index cũ giữ nguyên.
3. **Encoding theo chunk** (`itlr/pipelines/build_embeddings_v2.py`): tài liệu dài bị chia
   đoạn (max 900 ký tự, overlap 120) rồi encode từng đoạn; vector item = mean + L2 —
   hợp đồng "1 hàng = 1 item" không đổi cho engine.
4. **CF là tùy chọn** (ADR-005): thiếu `cf_model.pkl` ⇒ engine vẫn chạy, `/api/personas`
   `/api/for-you` trả 503 minh bạch; tương tác giả không nằm trong bất kỳ khóa đánh giá nào.
5. **`/admin/reload` có token** (ADR-008): env `ITLR_ADMIN_TOKEN`, trống ⇒ 403 (tắt).

Cập nhật dữ liệu một lệnh (cron được):
```bash
python scripts/refresh_pipeline.py        # crawl → catalog V2 → build → probe → activate
```
Chi tiết: `deploy/DEPLOY.md` · các quyết định: `docs/decisions/ADR-00{5,6,7,8}-*.md`

## Kiến trúc & pipeline build

V2 pipeline:

```
crawl (SQLite) + legacy CSV (5.000 synthetic, item_id giữ nguyên)
        │  python scripts/build_all_v2.py (một lệnh)
        ▼
[0] catalog V2      : var/data/itlr_v2_items.csv (+ provenance origin/license/lang/hash)
[1] retrieval_model : TF-IDF (full/title/topics) + BM25 k1=1.4,b=0.75 + MMR
[2] embeddings v2   : E5-base 768d ENCODE TỪNG CHUNK → mean + L2; FAISS; chunk_meta.pkl
[3] (tùy chọn) CF   : item-item cosine từ interactions.csv  (--with-cf)
        ▼
var/artifacts/versions/<id>/…  → PROBE (3 mức) → CURRENT.json (activate) → GC keep=3
```

Legacy pipeline (vẫn chạy được, không đổi): `python scripts/build_all.py`.

## Quickstart

```bash
# 0. môi trường (Python ≥3.11; repo đã kiểm nghiệm trên 3.14)
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt          # hoặc: pip install -e ".[eval,dev]"

# 1. cấu hình LLM (DeepSeek chính) + token quản trị
cp .env.example .env                     # điền DEEPSEEK_API_KEY=...; ITLR_ADMIN_TOKEN=...
set -a; . ./.env; set +a                 # export biến môi trường

# 2. thu thập + build index V2 (lần đầu cần mạng: thêm --online)
python scripts/collect_data.py           # crawl 4 nguồn (devto/fCC/MDN/VnExpress)
python scripts/build_all_v2.py           # catalog → build → probe → activate

# 3. chạy server + UI
uvicorn itlr.api.server:app --host 127.0.0.1 --port 8000
# mở http://localhost:8000  (UI tĩnh tự mount /static)
curl -H "X-Admin-Token: $ITLR_ADMIN_TOKEN" -X POST localhost:8000/admin/reload
```

Legacy quickstart (chỉ synthetic catalog):

```bash
python scripts/build_all.py              # --dry-run để xem kế hoạch; --force build lại hết
```

## API endpoints

| Endpoint | Chức năng |
|---|---|
| `GET  /health` | readiness (artifacts đã nạp?) |
| `GET  /metrics` | số request/độ trễ mỗi route (Prometheus-style text) |
| `POST /api/search` | `{"query": "docker", "type": "Khóa học", "min_pct": 90}` — tìm kiếm ngữ nghĩa |
| `POST /api/chat` | `{"message": "...", "history": [{"role","content"}...]}` — hỏi đáp; trả `{response, recommendations, intent}` |
| `POST /api/chat/stream` | SSE — mỗi frame `data: {json}` (text/meta/done) |
| `GET  /api/personas` | list persona CF cho demo "Dành cho bạn" (503 khi CF chưa build) |
| `POST /api/for-you` | `{"persona": 12, "interested": [101]}` — gợi ý cá nhân hóa (503 khi CF chưa build) |
| `POST /admin/reload` | nạp lại artifacts từ CURRENT.json — đòi header `X-Admin-Token: $ITLR_ADMIN_TOKEN` (403 khi env trống) |

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/api/search -H 'content-type: application/json' \
     -d '{"query": "học docker đến kubernetes cho người mới"}' | head -c 400
curl -N -X POST localhost:8000/api/chat/stream -H 'content-type: application/json' \
     -d '{"message": "Docker là gì và dùng để làm gì?"}'
```

## LLM — DeepSeek (chính) & fallback

- `itlr/chatbot/llm_client.py` là tầng DUY NHẤT gọi LLM: thứ tự **DeepSeek → OpenAI →
  Ollama**; DeepSeek là OpenAI-compatible (`base_url=https://api.deepseek.com`).
- Biến môi trường: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`
  (mặc định `deepseek-flash`, override qua env — ví dụ `deepseek-chat`);
  `DEEPSEEK_RETRIES` (3), `DEEPSEEK_TIMEOUT_S` (90), `DEEPSEEK_STREAM_TIMEOUT_S` (240).
- Calibration: retry exponential backoff, một lần tạo client + timeout mỗi attempt,
  trim hội thoại theo ngân sách ~16k ký tự (giữ system + lượt mới nhất).
- **Token tracking & chi phí** ước theo bảng giá trong `PRICE_PER_1M`:
  `from itlr.chatbot.llm_client import usage_snapshot`.
- **Bảo mật:** key KHÔNG được log (đã mask `sk-***xxxx`); lỗi LLM được báo rõ
  (`LLMError`) thay vì nuốt âm thầm; không commit file `.env` thật.
- **Generation nguyên tắc (SYSTEM_PROMPT rule 10):** nội dung người dùng/catalog là
  DỮ LIỆU không phải lệnh → bỏ qua mọi chỉ đạo giấu trong tài liệu; không bịa
  khóa/số liệu; thiếu bằng chứng phải nói rõ; cite `[item_id:ID]` từ catalog.

## Đánh giá (eval/) — chạy từ đầu đến cuối

```bash
python eval/run_all.py            # toàn bộ: judgments → ablation → noisy → CF → off-policy → human → latency
python eval/run_all.py --quick    # bộ rút gọn cho CI
python eval/eval_generation.py    # quality generation (template mode, offline)
python eval/eval_generation.py --llm   # dùng LLM sống (cần DEEPSEEK_API_KEY)
python eval/eval_offtopic.py      # chọn ngưỡng cổng off-topic bằng dữ liệu (AUC/F1)
```

Kết quả thật nằm ở `reports/` (CSV/JSON/Markdown + biểu đồ):
`tables.md` (ablation P/R/MRR/MAP/NDCG ± CI95 bootstrap), `tables_kw_noisy.md`
(robustness bỏ-dấu/typo), `cf_eval.md` (HitRate/NDCG + temporal no-leakage),
`off_policy.md` (IPS/SNIPS/DR), `latency.md` (p50/p95/p99 từng tầng), `human_eval.md`,
`offtopic_eval.md` (ngưỡng cổng off-topic), `generation_eval_template.{csv,md,json}`
(số LLM sống thêm khi chạy `eval_generation.py --llm`). LTR (`ltr.md`) chỉ sinh khi
chạy `eval/run_all.py --with-ltr` hoặc `eval/build_ltr.py --no-cross` — tùy chọn, chậm.

**Phân loại nhãn (quan trọng, không báo cáo sai):**
- *Retrieval qrels*: sinh rule-based TỪ METADATA catalog (không dùng retrieval → không vòng tròn).
- *Human judgments* (`eval/evaluate_human.py`): file `eval/human_judgments.csv` —
  `human_label` của MÔ PHỎNG (đóng dấu từng dòng khi `--simulate-human`) phải được
  thay bằng nhãn người thật trước khi gọi là human eval; Cohen's Kappa chỉ đúng khi nhãn thật.
- *CF/off-policy*: tương tác mô phỏng (click = reward đã biết trước), không phải hành vi thật.
- *Generation*: citation/hallucination đo TRỰC TIẾP; groundedness/relevancy là
  "proxy rule-based" — muốn số chuẩn cần LLM-as-judge với rubric + kiểm tra thủ công.

## Cấu trúc repo

```
itlr/
  config.py            # path trung tâm (ARTIFACTS_DIR/DATA_DIR) — không hardcode đường dẫn
  engine.py            # load_engine(): nạp artifacts 1 lần → API Python/Tầng web
  core/                # recommender (hybrid+ANN+rerank), bm25, embeddings registry, ann, rerank, rag, pipeline
  pipelines/           # build_model, build_embeddings, generate_interactions, build_cf
  chatbot/             # chatbot (intents, off-topic gate, knowledge base), llm_client, query_understanding
  api/                 # server.py FastAPI + static/ UI
  eval/                # metrics, diversity, significance, off_policy, cf_eval, ltr_features, loader
eval/                  # entrypoints đánh giá (run_all, run_evaluation, eval_cf, ...)
scripts/               # build_all.py — một lệnh build toàn bộ artifacts
tests/                 # pytest — kết quả hiện tại: reports/FINAL_REMEDIATION.md
reports/               # kết quả thực nghiệm đầu ra
```

## Quyết định thiết kế & sàn chất lượng

- `docs/decisions/ADR-001` — DeepSeek là LLM chính qua tầng `llm_client` thống nhất.
- `docs/decisions/ADR-002` — đường dẫn artifact/data tập trung `itlr.config`.
- `docs/decisions/ADR-003` — interactions mô phỏng + chính sách ghi nhãn trung thực.
- `docs/decisions/ADR-004` — thiết kế đánh giá (qrels rule-based, bootstrap CI).
- `CONSTRAINTS.md` — sàn chất lượng floor-only (tests / no-silent-fallback / secrets /
  paths / data-honesty).

## Kiểm thử & tái lập

```bash
pytest -q                      # toàn bộ test
python eval/run_all.py --quick # bộ eval rút gọn tái lập số nhanh
```

Seed cố định mọi nơi (`make_judgments` 20240623; generate_interactions 7; bootstrap
CI 20240623...). Thay đổi môi trường model embedding → phải build lại embeddings: đổi
`EMBEDDING_MODEL` rồi `python scripts/build_all.py --force --step embeddings_ann`.

## Hạn chế đã biết (khi bàn giao)

- Môi trường build **không có DEEPSEEK_API_KEY** → các test DeepSeek dùng mock; các
  đánh giá generation chạy chế độ **template**; khi có key chỉ cần export key rồi
  `python eval/eval_generation.py --llm` để có số LLM sống.
- Nhãn "human" là mô phỏng (đọc phần phân loại nhãn) — cần labeling thật trước khi
  dùng làm số liệu chính thức.
- LLM `deepseek-flash`: tên model hợp lệ theo tài liệu chính thức DeepSeek
  (https://api-docs.deepseek.com/, verify 2026-10-27 — model này do DeepSeek-V4.1-Flash-1017
  phục vụ); nếu cần model khác chỉ đổi `DEEPSEEK_MODEL` (vd `deepseek-v4-pro`) — không sửa
  code. Bảng giá trong `PRICE_PER_1M` là ước tính (chưa check trang pricing).

## Security remediation 2026-10-29

Trạng thái phát hành và kết quả kiểm chứng hiện tại: [FINAL_REMEDIATION](reports/FINAL_REMEDIATION.md).
Không dùng benchmark lịch sử ở trên làm bằng chứng môi trường hiện tại chạy được.
Có CI Python/TypeScript/security trong `.github/workflows/ci.yml`.
Deploy một worker/replica, trusted proxy tường minh, manifest strict và hướng dẫn web
riêng: [DEPLOY](deploy/DEPLOY.md#7-security-remediation-2026-10-29).
UI tĩnh chỉ render Markdown giới hạn (bold/code/newline), không render HTML hay link Markdown;
link catalog chỉ chấp nhận HTTP(S). `/live` tách biệt `/health` readiness.

## V3 implementation status (2026-10-30)

Chunk artifacts use a shared retrieval service for API search, semantic chat,
quick resources and off-topic scoring. Old artifacts retain the V2 path. Generated
V3 answers require selected chunk citations; this checks identity, not semantic
truth. Active artifacts are not upgraded merely by updating code.

Architecture and compatibility mapping: [ADR-010](docs/decisions/ADR-010-shared-retrieval-and-atomic-state.md).
Measured scope, tests and release blockers: [V3 restructuring checkpoint](reports/V3_RESTRUCTURING_2026-10-30.md).
