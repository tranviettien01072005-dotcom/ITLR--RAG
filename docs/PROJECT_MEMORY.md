# PROJECT_MEMORY.md — Bộ nhớ dự phòng (fallback) của ITLR RAG

> **Vai trò:** đây là bản "long-term memory" in-repo, dùng khi Claude-Mem không khả dụng.
> Nguồn chính là Claude-Mem (các memory #102–#107, project `ITLR RAG`, lưu 2026-10-27).
> **Giao thức agent:** đầu mỗi phiên — search Claude-Mem + đọc `AGENTS.md`; sau mỗi thay đổi
> quan trọng — `save_memory` (tìm duplicate trước; **không bao giờ** lưu API key/secret) rồi
> cập nhật file này + `AGENTS.md` + `CHANGELOG.md`.

---

## 1. Kiến trúc & pipeline (trạng thái hoàn thiện 2026-10-27)

- **Stack:** Python 3.14.4 (`.venv`), package `itlr/` (pyproject.toml), FastAPI
  `itlr.api.server:app` + UI tĩnh `/static`.
- **Luồng chính:** query → retrieval song song
  - dense: `intfloat/multilingual-e5-base` 768d qua FAISS IndexFlatIP;
  - từ vựng: TF-IDF + BM25 (k1=1.4, b=0.75); char n-gram TF-IDF chống typo/không dấu;
  → RRF fusion → [tùy chọn] Stage2 rerank cross-encoder `BAAI/bge-reranker-base` + MMR
  diversity → generation grounded (bắt buộc cite `[item_id:ID]`, chống prompt-injection)
  → recommendation CF item-item cosine (top-32/item) cho trang "Dành cho bạn".
- **Tầng LLM duy nhất:** `itlr/chatbot/llm_client.py` — chuỗi DeepSeek → OpenAI → Ollama;
  retry/backoff, timeout, usage tracking, mask key khi log; LLMError báo lỗi rõ ra ngoài.
  `chatbot.py` chỉ delegate (`try_llm_response` / `try_llm_response_stream` /
  `_llm_available`); hợp đồng None/generator rỗng → template offline (log WARNING,
  không nuốt lỗi âm thầm).
- **Cổng off-topic:** chấm `query_relevance_max`. Ngưỡng runtime hiện **0.55**; eval
  2026-10-27 (121 câu) khuyến nghị **0.800** (tối ưu F1) — chưa đổi runtime.
- **Knowledge assets:** 360 khái niệm glossary, 19 career roles.
- **Build một lệnh:** `python scripts/build_all.py` → 11 artifacts `var/artifacts/*.pkl`
  (thời gian đo thật: retrieval ~187.6s, embeddings+ANN ~908.1s, CF ~1s; 5.000 items).
  Artifacts không đưa vào VCS (`.gitignore` loại trừ `var/artifacts/`).
- **Đường dẫn tập trung** `itlr/config.py` (ADR-002): `ARTIFACTS_DIR`, `DATA_DIR`; env
  override `ITLR_ARTIFACTS_DIR` cho sandbox/test.
- **Repo đã là git repo** — đã push lên `origin/main`; `.gitignore`, `pyproject.toml`,
  `Makefile`, `.env.example` đã có sẵn cho tương lai.

## 2. Cấu hình LLM & embeddings (không chứa secret nào)

| Mục | Giá trị |
|---|---|
| LLM chính (chỉ generation) | DeepSeek, OpenAI-compatible SDK |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` (verified docs chính thức 2026-10-27) |
| `DEEPSEEK_MODEL` | `deepseek-flash` — hợp lệ hiện hành, served by DeepSeek-V4.1-Flash-1017 (verified); override được (vd `deepseek-chat`, `deepseek-v4-pro`) |
| Retry/timeout | `DEEPSEEK_RETRIES=3`, `DEEPSEEK_TIMEOUT_S=90`, `DEEPSEEK_STREAM_TIMEOUT_S=240` |
| Giá token | `PRICE_PER_1M` trong `llm_client.py` là **ước tính** (chưa verify trang pricing) |
| Embedding | `intfloat/multilingual-e5-base` (768d), prefix query/passage chuẩn E5; FAISS `set_ef(64)` |
| Bảo mật | key không log (mask `sk-***xxxx`); không commit `.env`; không hardcode key/path |

- `eval_generation.py --llm` **FAIL-FAST rc=2** khi thiếu `DEEPSEEK_API_KEY`
  (không fallback âm thầm gắn nhãn "llm"); env chết `ITLR_FORCE_LLM` đã xóa.
- Đổi `EMBEDDING_MODEL` ⇒ phải `build_all.py --force --step embeddings_ann`.

## 3. Lỗi đã sửa & quyết định kỹ thuật (audit 2026-10-27)

Biên bản review: `docs/review-2026-10-27.md` (9 findings — mọi Required đã đóng).

- `eval_generation.py`: sửa NaN-groundedness; `--llm` fail-fast; JSON NaN → null;
  `run_case` đọc `chat()` trả list item dict trực tiếp (`s.get("item") or s`).
- `itlr/core/ann.py`: `read_index` fail-safe; `set_ef(64)`; đóng pickle bằng
  context-manager (fix cả file-handle CF engine + embeddings).
- `eval/run_all.py`: sửa path traversal (tìm repo-root từ vị trí file); rework
  import-probe template theo sentinel path; đổi tên báo cáo
  `tables_noisy.md` → `tables_kw_noisy.md` (đã đồng bộ tên ở README).
- `scripts/build_all.py`: docstring chính xác (bỏ hứa "engine kiểm nạp", bỏ `plan()` thừa).
- `chatbot/`: dọn imports chết (AST check); adapter dùng `_history_msgs`
  (`chatbot.py` ~line 751); logic Ollama chuyển hết vào `llm_client`.
- Test: fix fake-FAISS return-ordering → **70/70 pytest pass (0 skip)**.
- **ADR-001** DeepSeek là LLM chính (gen-only); **ADR-002** đường dẫn tập trung + env
  `ITLR_ARTIFACTS_DIR`; **ADR-004** thiết kế eval (qrels rule-based từ metadata,
  bootstrap CI, LTR query-level holdout).
- `CONSTRAINTS.md`: sàn floor-only 6 mục (tests passing · không fallback âm thầm ·
  không hardcode secret · không hardcode path · trung thực dữ liệu · ratchet mode).

## 4. Lệnh setup / build / run / test / eval

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                      # điền DEEPSEEK_API_KEY, rồi: set -a; . ./.env; set +a

python scripts/build_all.py               # [--dry-run | --force | --step retrieval|embeddings_ann|collaborative]
uvicorn itlr.api.server:app --host 127.0.0.1 --port 8000     # UI: http://localhost:8000
.venv/bin/python -m pytest -q             # 70/70 pass

python eval/run_all.py [--quick | --with-ltr]        # 8 bước eval đầy đủ
python eval/eval_offtopic.py                         # AUC/F1 ngưỡng cổng off-topic
python eval/eval_generation.py [--llm]               # --llm cần DEEPSEEK_API_KEY
eval/build_ltr.py --no-cross                         # LTR (tùy chọn, chậm)

python -m itlr.pipelines.generate_interactions       # tái sinh interactions 1.800 users (seed=7)
python scripts/build_all.py --force --step collaborative
```

- **Deps đã cài thật** (Linux, Python 3.14.4): torch 2.14.1 · sentence-transformers 6.2.0 ·
  faiss-cpu 1.15.1 (cần pyarrow cho pickle catalog) · lightgbm 4.7.0 · shap 0.54.1 ·
  matplotlib 3.11.2.
- Endpoints: `/health` `/metrics` `/api/search` `/api/chat` `/api/chat/stream` (SSE)
  `/api/personas` `/api/for-you` + UI tĩnh. API integration test: 5/5 TestClient.
- Backup dữ liệu cũ: `var/data/interactions_backup_500users.csv`.

## 5. Datasets & phương pháp đánh giá (trung thực về nguồn nhãn)

- **SYNTHETIC:** catalog 5.000 items; interactions 1.800 users (seed=7). 360 khái niệm,
  19 career roles. KHÔNG phải người thật.
- **Phân loại nhãn (không được báo cáo sai):**
  - qrels retrieval = rule-based từ metadata catalog (không dùng retrieval → không vòng tròn);
  - "human" ở `--simulate-human` = **MÔ PHỎNG** (n=228, Cohen's kappa 0.7190, đồng thuận
    ~88%) — phải thay nhãn thật trước khi dùng làm số liệu chính thức (ADR-003);
  - CF/off-policy = click mô phỏng (reward biết trước).
- Generation: citation/hallucination đo TRỰC TIẾP trên ID nguồn; groundedness/relevancy
  chỉ là proxy rule-based (muốn chuẩn: LLM-as-judge + kiểm tra thủ công).
- Seed cố định mọi nơi (judgments 20240623; interactions 7; bootstrap CI 20240623).
- LTR holdout ở mức query (tránh leakage giữa các câu cùng chủ đề).

## 6. Kết quả benchmark thực đo (nguồn: reports/, ngày 2026-10-27)

| Hạng mục | Số thực đo | File |
|---|---|---|
| Retrieval ablation (clean, 76 queries) | E5 hybrid tốt nhất — **NDCG 0.2555**, CI95 bootstrap | `reports/tables.md` |
| Retrieval robustness (noisy, 78 queries) | Hybrid +L1 — **NDCG 0.5919**, p<0.05 vs mọi baseline | `reports/tables_kw_noisy.md` |
| CF (1.800 users) | **HitRate@10 = 0.4863** vs popularity 0.0288 | `reports/cf_eval.md` |
| Off-policy | SNIPS/DR phủ ground-truth; naive lệch **−0.104**; ESS 4686/6000 | `reports/off_policy.md` |
| Latency (CPU) | FAISS **49.8ms** vs brute 150.5ms; full no-rerank p95 **195ms**; Stage2 rerank p50 **6.18s** | `reports/latency.md` |
| Human eval (MÔ PHỎNG) | n=228, kappa **0.7190** | `reports/human_eval.md` |
| Off-topic gate (121 câu) | **AUC 0.9825**; ngưỡng 0.55 → F1 0.663; tối ưu **0.800 → F1 0.929** (P 0.881, R 0.983) | `reports/offtopic_eval.md` |
| Generation (template, 50 IT + 21 off-topic) | groundedness proxy **0.385**, relevancy proxy **0.929**; citation 0 (hallucination 0% trivial); **refusal off-topic 0/21**; false-refusal IT 0/29 | `reports/generation_eval_template.{csv,md,json}` |

- Eval đầy đủ `eval/run_all.py` chạy thành công **8/8 bước (rc=0)**.
- LTR `reports/ltr.md` **chưa sinh** (chưa chạy `--with-ltr`) — tùy chọn, chậm.
- Số generation **LLM sống** chưa có (thiếu key) — chạy `eval_generation.py --llm` khi có key.

## 7. Hạn chế còn lại & tech debt

1. **Chưa verify:** DeepSeek live (thiếu `DEEPSEEK_API_KEY`) + `--llm`; giá `PRICE_PER_1M`
   là ước tính; LTR chưa build.
2. **Hiệu năng:** Stage2 rerank p50 6.18s là điểm nghẽn chính — hướng: rerank top-k nhỏ hơn,
   batch, cache, hoặc cross-encoder nhỏ/quantized.
3. **Cổng off-topic:** đề xuất đổi ngưỡng 0.55 → 0.800 sau khi mở rộng bộ test (hiện 121 câu);
   runtime chưa đổi vì mẫu còn nhỏ.
4. **Template mode không từ chối câu off-topic** (refusal 0/21) — chỉ đúng khi chạy offline
   template; với LLM sống, SYSTEM_PROMPT grounded + refusal là nét chính.
5. **Repo đã là git** — `.gitignore` chặn `var/artifacts/` và runtime V2, `reports/` giữ
   trong repo; `main` đã đồng bộ với GitHub.
6. **Claude-Mem worker** từng vào quota cooldown (provider codex) — không khởi động lại
   worker bằng tay; nếu `save_memory` lỗi thì báo nguyên nhân gốc, không giả vờ thành công.

## 8. Nhật ký phiên (append khi có thay đổi quan trọng)

| Ngày | Sự kiện |
|---|---|
| 2026-10-27 (sáng) | Nghiên cứu repo, xuất `RESEARCH_ITLR.md`; các note giai đoạn nghiên cứu #1…#23. |
| 2026-10-27 (chiều) | Audit + review 9 findings; sửa eval/ann/paths/chatbot; 70/70 tests; build 11 artifacts thật với 1.800 users; `eval/run_all.py` 8/8 OK; ADR-001…004; CHANGELOG/README/CONSTRAINTS; DeepSeek verified docs chính thức. |
| 2026-10-27 (chìều muộn) | `eval_offtopic.py` rc=0 (AUC 0.9825, ngưỡng tối ưu 0.800); `eval_generation.py` template rc=0; lưu 6 memory #102–#107 + xác minh truy xuất; tạo `AGENTS.md` + `docs/PROJECT_MEMORY.md`. |
| 2026-10-29 | Commit/push V2 data collection, versioning, deployment assets và test suite lên `origin/main`; health item count hardening bổ sung; working tree sạch. |

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
