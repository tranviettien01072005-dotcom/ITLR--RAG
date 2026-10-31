# ITLR–RAG — Bộ nhớ kỹ thuật hiện hành

Cập nhật: 2026-10-31. Thứ tự ưu tiên: yêu cầu phiên hiện tại → AGENTS/CONSTRAINTS →
code và bằng chứng chạy mới → nhật ký lịch sử. Kế hoạch cũ không cấp quyền commit,
publish, migration hoặc gọi provider trả phí.

## Trạng thái đã kiểm chứng

- Resume validation (2026-10-31, phiên nối tiếp, working tree sạch `f14c428…`):
  **494 Python / 146 Web PASS**, coverage **67,63% / 47,05%**; typecheck/lint/build,
  compileall, pip check, pip-audit **0**, npm audit **0**, Bandit 0 High PASS.
  Docker staging fresh `--no-cache` **PASS scoped** qua `sg docker` (user thuộc group
  docker; không cần sudo): project `itlr-resume-1031c`, ports 19081/19444, PG16 +
  Caddy TLS nội bộ + E5 + Qwen thật SSE + Chrome **11/11** + cancel đóng socket
  provider **55ms** + backup/restore 15 bảng + tamper reject + reload/rollback +
  restart; volumes giữ, ports đóng sau stop. A/B `ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET`
  `None` vs `800`: 11/12 và 11/12 positive, 7/8 và 7/8 negative, prompt −7,1% nhưng
  `positive-12` regress → **giữ default `None`**. Benchmark cold sau đó: prefill prompt
  đầy đủ 40–51s (27–34,5 tok/s), flash attention +10,6%, budget 500 chỉ còn 10/12 →
  **SLO 45s FAIL, hardware-bound** (cần prefill ≥65–70 tok/s). Human faithfulness `null`
  nhưng packet + protocol chấm đã sẵn sàng. Reliability: cold start 42s, soak 120s
  45/45 `done`, crash recovery 1s, DB counts không đổi.
  **NO-GO** production. [Certification §11](../reports/FINAL_E2E_CERTIFICATION.md).
- Final E2E certification (2026-10-31, checkpoint trước): **489 Python / 146 Web PASS**,
  coverage **67,37% / 47,05%**; điển hình gates thật: HTTP/DB 36/36, Chrome 9/9,
  backup/restore 15 bảng fingerprint bằng, TLSv1.3 verified-cert smoke, artifact
  lifecycle 9/9, CF-absent 503 đúng, health fingerprint lock/reload PASS.
- Chế độ `llm_extractive` (evidence-bound) là default khi có chunk retrieval: model
  chọn chunk theo JSON schema, engine bind quote nguyên văn byte-verbatim; frozen
  blind eval 20 case (SHA `2a3a98e2d207…`): 11/12 positive accepted valid, 1 timeout
  45s; negative 7/8 không trở thành claim (2 template gate, 1 extractive search,
  3 `no_selected_evidence`, 2 timeout). Uncached full prompt vẫn FAIL (60s không
  xong; prefill CPU-bound). Docker daemon socket root:root, sudo noninteractive bị
  từ chối, thiếu newuidmap → Docker staging **BLOCKED**. Human metrics vẫn null.
  **NO-GO** production. [E2E certification](../reports/FINAL_E2E_CERTIFICATION.md).
- Blocker remediation (2026-10-30 → 2026-10-31): **457 Python / 145 Web PASS**,
  coverage **67,24% / 46,55%**. API SSE dùng async I/O, total generation deadline,
  strict UTF-8 và explicit iterator cleanup; sync public paths vẫn giữ tương thích.
  Real Chrome→Express→API→Qwen Stop đóng socket sau64/77ms, DB không lưu partial;
  request model kế tiếp khoảng0,3s. Chưa có model-internal cancellation ACK.
  Direct uncached prompt vẫn timeout45s; rút context làm giảm quality nên không áp dụng.
  Có counterexample citation passage không hỗ trợ claim. Docker bị socket/uidmap
  block, human metrics null. **NO-GO**, không commit/push/production migration/activation.
  [Báo cáo và evidence mới](../reports/PRODUCTION_BLOCKERS_RESOLUTION.md).
  Các checkpoint dưới là lịch sử, không phải lần chạy mới.
- Release validation mới: **445 Python / 145 Web PASS**, coverage **66,70% / 46,55%**.
  Sửa UI báo success trước EOF/done và PDF Buffer/parser incompatibility bằng RED→GREEN.
  Bộ nguồn mới Recall@5 83,33%, EN6/6 VI4/6; không tuning, AI labels chưa phải human.
  PostgreSQL18 native cô lập: migration2 lần, HTTP/DB36 checks, Chrome9, backup/restore15 bảng.
  Real E5 artifact copy load/reload/rollback/tamper rejection PASS trên temporary root.
  Qwen smoke thật hoàn tất, RAG requests budget45s timeout/fallback trên máy dùng chung;
  chưa chứng minh cancellation upstream, token budget, capacity/faithfulness. **NO-GO**.
  [Release report](../reports/RELEASE_READINESS_FINAL.md); các số phía dưới là checkpoint trước.
- Engineering review hiện tại: **445 Python PASS/0 skip**, statements **66,70%**;
  **140 Web PASS**, lines **46,48%**. [Báo cáo](../reports/FINAL_ENGINEERING_REVIEW.md).
- Search default **84**, chọn trên dev; giữ explicit overrides, RRF weights và gate
  chatbot 0,80. Query không có typo/abbreviation giữ nguyên; chỉ mở rộng bare alias.
  Raw release Recall@5 4,76% → 92,86%; engine holdout 83,33%, confirmation 62,50%.
  Negatives đều bị loại trong các tập cuối; labels không phải human panel độc lập.
- Đã sửa Web final-before-done persistence, EOF thiếu done, giới hạn message/history
  khớp FastAPI mà không sửa DB, JSON NaN trong recommendations. Giữ strict citation.
- Ollama elapsed budget kiểm tại NDJSON boundaries; test thật 2 s dừng sau 2,14 s.
  Live API HTTP404 chat/stream khoảng 6 s, citation hợp lệ nhưng entailment chưa đo.
  Prompt/sampling experiments chưa đủ chất lượng nên không đưa vào runtime.
- Re-pickle dùng atomic replacement, giữ original khi lỗi, từ chối sklearn mismatch;
  runtime không còn che warning version. Không chạy migration vào artifacts thực.
- Baseline/full-system audit trước: **431 Python PASS/0 skip**, coverage statements
  **66,13%**; **132 Web PASS**, lines **45,31%**. E5 768d inference offline và Qwen2.5
  3B generation/stream/truncation/cancellation thật đã chạy; public login/register
  qua Chrome ở 390/1280px PASS. [Full-system audit](../reports/FULL_SYSTEM_AUDIT_2026-10-30.md)
  phân biệt các gate và dữ liệu staging. Không activation/migration/commit/push.
- Bốn lỗi Ollama đã sửa: explicit model bị thay, non-stream thiếu completion
  validation, bỏ history budget, bỏ `OLLAMA_TIMEOUT`; Vitest đã cô lập credentials.
- Sửa first-flat-probe integrity mismatch do `.activation.lock` sinh sau inventory;
  giữ hash checks. E5 staging riêng 118 docs/1576 chunks probe PASS, không activation.
  Raw-query neural Recall@5 với floor 0,90 chỉ 4,76%; diagnostic floor 0 đạt
  Recall@10 100% nhưng trả cả negatives. Giữ defaults, NO-GO chờ calibration độc lập.
- API staging HTTP/SSE/reload PASS protocol nhưng generation không đạt: non-stream
  61,15 s thiếu citation, SSE 533,73 s bị cắt, final đánh dấu insufficient_evidence.
  Có một loky semaphore warning lúc shutdown; chưa có bằng chứng soak/leak đã sạch.
- Số 414/132 Windows dưới đây là checkpoint trước phiên Linux này.
- Python: **414 PASS/0 skip**, 86,51s; 5603 statements / 1920 missed, khoảng 65,73%.
- Web: **132 PASS/25 files**, line coverage 45,31%; typecheck/lint/build PASS.
- Compileall và pip check PASS. Lệnh, log và inventory:
  [restructuring continuation](../reports/RESTRUCTURING_CONTINUATION_2026-10-30.md).
- Đây là kết quả local Windows; không chứng nhận production-ready.

## Ranh giới và quyết định hiện hành

- Web/Express/PostgreSQL là giao diện chính; FastAPI phục vụ engine RAG.
- Shared retrieval cho chunk artifacts; V2 và BM25 pickle shim được giữ.
- Display formatting ở core/display.py; provider history/fallback ở chatbot/llm_adapter.py;
  chat HTTP/SSE ở web/src/routes/chat.handlers.ts. Export/import cũ được giữ tương thích.
- Builders offline, staging/probe/activate/rollback; không tự rebuild hay migrate khi serve.
- Một worker/replica, filesystem Linux local. Deferred config/versioning/locking cycle
  được giữ vì gắn với cấu hình lazy; graph top-level không có cycle được phát hiện.
- Nguồn thật, interactions synthetic và qrels metadata/hand-authored phải ghi riêng.
  Citation identity chưa chứng minh faithfulness.

## Blockers

Docker/PG16/Caddy lifecycle trong staging đã chạy thật (2026-10-31 resume: PASS scoped,
single-host CPU-only, artifacts dùng một lần), nhưng chưa phải deployment production
nhiều host. Còn mở: uncached full prompt >45s (prefill CPU ~30s/case, timeout thật
45,124s), independent human faithfulness/entailment (`null`), model-internal
cancellation ACK/capacity/soak/cold start. Transport cancellation đã đo thật
(socket provider đóng 55ms trong staging). Không production DB/index changes,
paid API, commit/push. Xem [certification §11](../reports/FINAL_E2E_CERTIFICATION.md)
và evidence trong `reports/final-e2e-evidence/`.

## Nhật ký lịch sử

Phần sau bảo toàn nguyên nội dung checkpoint trước; các từ “mới nhất/hiện hành”
trong nhật ký chỉ có nghĩa tại thời điểm ghi.

Release validation: 23 frozen engineer-authored queries over 118 real snapshots; lexical versus MMR measured, neural/generation NOT MEASURED. No ranking/threshold change. See [release evidence](../reports/RELEASE_VALIDATION_2026-10-30.md).

<details>
<summary>Mở nhật ký checkpoint trước</summary>

# ITLR–RAG | Intelligent IT Learning Platform — Trạng thái dự án

Current verification entrypoint: [restructuring continuation](../reports/RESTRUCTURING_CONTINUATION_2026-10-30.md). Baseline 386 Python / 124 Web; older checkpoint paragraphs below are historical.

Historical checkpoint (superseded by the verification entrypoint above): Checkpoint mới: Windows dev host **384 Python pass/0 skip**, coverage 64,96%; Web **124 pass/25 files**, lines 45,01%; lint 0 warning, Bandit 0 High, npm audit/pip-audit sạch. Đã xóa API key thật khỏi `.env.example` working copy (không có trong git history), sửa normalize URL default port/credential, passcode admin constant-time/open redirect, portability `resource`/torch test, HTTP Range dedup và toàn bộ ESLint warning. Production vẫn Linux local; Docker/PostgreSQL/HTTPS và human/neural RAG gates chưa xác minh; **NOT READY**. Xem [audit](../reports/AUDIT_PORTABILITY_2026-10-30.md).

Cập nhật: 2026-10-30. Đây là bộ nhớ kỹ thuật trong repository; không cần dịch vụ memory ngoài.
Hướng dẫn hiện hành: [README](../README.md), [AGENTS](../AGENTS.md),
[Deployment](../deploy/DEPLOY.md). Bằng chứng theo lần chạy: [Validation](../reports/VALIDATION.md).
Tài liệu chuẩn theo chủ đề: [RAG](RAG.md), [API](API.md), [Testing](TESTING.md),
[Evaluation](EVALUATION.md), [Security](SECURITY.md), [ADR-013](decisions/ADR-013-evidence-excerpt-budget.md).

## Trạng thái hiện hành

Checkpoint trước trên nhánh refactor: **329 Python pass/0 skip (50,19s)** so với
baseline nhánh **288/0**. Sửa chunk bounds/zero overlap, request-local vector reuse,
handler/filter bugs, integrity 503/admin guard, CF target pinning, reranker init lock,
store row_id, exporter no-clobber, LLM numeric env contract và oversized media Range.
Không đổi GC/active artifacts/database. Sau bổ sung toolchain cô lập: **78 Web pass**,
typecheck/build PASS, lint 0 lỗi/20 cảnh báo, npm audit/pip-audit không có advisory đã
biết; Bandit 0 High (28 Medium/57 Low). Ponytail Ultra không có trong model
registry. Chi tiết và backlog: [audit increment](../reports/AUDIT_INCREMENT_2026-10-30.md).
Các số 280/64 bên dưới là checkpoint trước, không phải lượt chạy mới này.

- **Implemented:** Web Express/TypeScript/EJS (3000), PostgreSQL; API FastAPI (8000).
  SQLite lưu nội dung thu thập; artifacts pickle/FAISS được version hóa trên filesystem Linux local.
- **Implemented:** chunk dense + BM25 + RRF và reranker tùy chọn qua shared retrieval service;
  artifacts legacy vẫn dùng đường V2. Giữ shim `itlr/core/bm25.py` để unpickle bản cũ.
- **Implemented:** citation kiểm ID item/chunk trong evidence đã chọn, SSE provisional rồi final;
  thiếu bằng chứng trả trạng thái rõ ràng. Kiểm ID không đo entailment/faithfulness.
- **Verified trước phiên:** 260 Python/0 skip, 59 Web tests. **Verified trong phiên:** baseline Python
  260/0 skip (48.90s) ngoài sandbox; final **280/0 skip (57.36s)**; Web **64 pass**, line coverage **27.06%**, lint 0 lỗi/20 cảnh báo.
- **Experimental:** real E5 trên 8 snapshot/98 chunk, nhãn item-level. Không suy rộng sang corpus lớn,
  generation hoặc tải nhiều người dùng. Metric chưa đo giữ `null`.
- **Planned:** passage qrels độc lập, calibration V3/off-topic, benchmark reranker và capacity,
  browser E2E có đăng nhập, diễn tập backup/restore và triển khai đầy đủ.

## Thay đổi phiên audit sản phẩm

1. Top-K V3, đa dạng item trước giới hạn ứng viên và sai số cosine: đã tái hiện FAIL rồi sửa PASS.
2. RRF không cộng điểm trùng trong một ranking; pipeline không tính nền hai lần.
3. Evaluation tái sử dụng model trong engine để tránh trộn version; CF thiếu không làm hỏng retrieval eval.
4. Probe không nội suy path thành Python code và yêu cầu subprocess thoát thành công.
5. Web xác thực user/role hiện tại trong PostgreSQL; redirect login không chấp nhận backslash.
6. Crawler kiểm HTTP status, robots trên redirect và rate-limit từng request; policy/license mới được
   ghi vào bản refetch, thu hồi full-text chặn export tiếp theo mà không xóa snapshot.
7. Markdown được viết lại theo thương hiệu sản phẩm, giữ giới hạn thực nghiệm và provenance lịch sử.

Không thay index active, không migration database đang chạy, không gọi LLM trả phí, không commit/push.
Thu hồi quyền nội dung không tự xóa bằng chứng trong artifacts đã active: operator cần rebuild/probe/activate.
Untracked `node_modules/` đầu phiên được giữ nguyên. Không xóa dependency hoặc shim khi chưa chứng minh an toàn.

Thử nghiệm E5 offline sau sửa: 8 snapshot/98 chunk, 8 qrels item-level tự soạn; cả hai cấu hình
Recall@5/MRR@5/nDCG@5=1.0, p95 114.30/115.33ms, CPU 106.80/107.68ms/query, peak process RSS
1486.51MiB. Không generation/reranker; không kết luận cải thiện toàn corpus.
Raw: [chunks_v3_audit_experiment.json](../reports/chunks_v3_audit_experiment.json).

## Các quy tắc tiếp nối

- Đọc Git diff và Validation trước khi sửa; không dùng test count cũ làm bằng chứng mới.
- Dùng Ponytail Ultra; mỗi bug có RED → GREEN → review. Không bỏ/skip/làm yếu assertion.
- Khi test local, unset DeepSeek/OpenAI keys và tắt Ollama nếu không chủ đích kiểm local inference.
- Giữ nguyên thông báo bản quyền nguồn; không gán giấy phép cho toàn dự án.
- API admin fail-closed; CF là tùy chọn; một worker/service, filesystem Linux local.

## Các checkpoint lịch sử

Các đoạn dưới là snapshot trước đây, không phải giao thức hiện hành; số liệu, phiên bản môi trường
và các tham chiếu công cụ cũ chỉ có giá trị tại thời điểm ghi. Hướng dẫn hiện hành không yêu cầu
Claude-Mem; không thực hiện các chỉ dẫn memory trong lịch sử.

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

## 4. Lệnh tại checkpoint 2026-10-27 (tham khảo lịch sử)

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
6. **Dịch vụ memory ngoài** từng gặp quota cooldown. Đây là lịch sử công cụ, không phải
   dependency hay bước vận hành hiện hành; không khởi động hoặc tích hợp lại.

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


## Production hardening checkpoint ? 2026-10-30 (Windows)

Read Ponytail skill directly; applied Ultra per AGENTS. Preserved V3/V2 boundaries and runtime data.
Fixed incomplete UTF-8 acceptance in server/browser SSE and complete-frame size bypass in browser,
with observed RED ? GREEN regressions. Current session is Windows/Python3.12/Node26, not the
historical Linux environment. See reports/PRODUCTION_CHECKPOINT_2026-10-30.md for actual checks
and unresolved release gates; do not infer production readiness or fresh neural benchmarks.


## Deployment-first steering - 2026-10-30

User stopped further installation and requested deployment/code structure work, deferring tests.
Added compose.production.yml and deploy/PRODUCTION.md: single Linux host, Caddy HTTPS,
private API/Web/PostgreSQL, explicit migration/catalog sync, backup/restore and rollback procedure.
Split Web Express composition into app.ts and lifecycle into server.ts; added bounded SIGTERM drain.
Web entrypoint no longer migrates/seeds automatically. Existing API-only Compose is preserved.
No paid calls, cloud resources, database migrations or runtime artifact changes performed.
Latest deployment/lifecycle changes are NOT runtime-verified; user will test later.
Earlier Python full suite failed collection on Windows fcntl (4 errors); selected 46 tests passed.
Earlier SSE Web checks passed; they predate the app/lifecycle split and are not fresh verification.

## Architecture refactoring verification - 2026-10-30

Latest request reinstated verification using installed dependencies; no installation performed.
Extracted 27 unchanged presentation definitions from chatbot.py (1516 -> 951 lines)
into presentation.py (595 lines), preserving legacy helper imports and 5 Markdown fingerprints.
Fixed Web 10/16-column append mismatch with a shared catalog header reader/whitelist;
regressions reproduced 2 FAIL -> PASS. Fixed missing streaming WARNING log with 1 FAIL -> PASS.
Added Web app HTTP liveness/readiness contracts using a stub database.
Fresh results: selected Python 90 PASS; full Python FAIL (4 fcntl collection errors on Windows).
Web 75 PASS, typecheck/build PASS, lint 0 errors/20 existing warnings; line coverage 35.42%.
Compileall, Bandit high-severity gate and pip check PASS. No quality gates weakened.
Template benchmark: identical output; p95 before/after 3.654/3.662ms, no speedup claim.
Static graph: no top-level Python/static Web cycles; deferred config/versioning/locking cycle remains.
No migrations, real data/index changes, paid calls, cloud deployment, commits or pushes.
Evidence and remaining release gates: reports/ARCHITECTURE_REFACTOR_2026-10-30.md and ADR-011.

## Final audit increment - 2026-10-30 (Windows)

Removed a real-looking DeepSeek key from the tracked `.env.example` working copy (not in
git history) and added an env-example secret guard. Fixed URL normalization (default port,
credentials), `resource` portability in the benchmark, and test-fixture imports that pulled
torch unnecessarily, unblocking 11 API/lifecycle tests. Extracted shared HTTP Range logic,
removed the CSP-blocked `javascript:` link, limited LLM base URLs to http(s), replaced
library asserts with exceptions, and removed all 20 explicit-any lint warnings.

Fresh: Python 384 pass/0 skip, coverage 64.96% statements (metrics 97.3%, diversity
93.4%); Web 124 pass/25 files, lines 45.01%, typecheck/build PASS, lint 0 warnings.
Bandit 0 High/31 Medium/61 Low (pickle and operator-configured URLopen remain accepted
risks; full triage in reports/BANDIT_TRIAGE_2026-10-30.md); npm audit and pip-audit clean.
Added a real-snapshot lexical benchmark (118 items, 8 single-annotator qrels):
Recall@5 1.0, MRR@5 0.9375, nDCG@5 0.9539, p50/p95 52.1/62.0 ms, 18.7 qps; neural and
generation metrics remain null. Admin passcode comparison is constant-time and
post-action redirects are same-origin.
Still BLOCKED/NOT MEASURED: Docker/PostgreSQL/HTTPS/browser E2E, migrations, Linux flock
runtime, neural/reranker/human evaluation. NOT READY.
Details: reports/AUDIT_PORTABILITY_2026-10-30.md.

## Stream hardening continuation - 2026-10-30

Shared client ignores terminal chunks with empty choices; 2 reproduced failures to PASS, 34 client tests PASS. Initial main f8ad595 clean. No paid calls, data/index changes, commits or pushes. Fresh Web 124 PASS, lines 45.01%; Python default Windows encoding baseline 378 PASS/6 FAIL. See reports/HARDENING_STREAM_2026-10-30.md for fresh verification and limitations.

Final fresh full Python verification: 386 PASS / 0 skip, coverage 65% rounded, 188.40s, UTF-8 environment; reports/hardening-utf8.log. Outside-sandbox diagnostic failed on temporary-directory permissions (4 FAIL / 129 setup errors); retained separately. Focused portability 21 PASS; client/link review 35 PASS.

Restructuring verification: 387 Python PASS/0 skip (91.94s), coverage 65% rounded; 124 Web PASS, line coverage 45.01%; typecheck/lint/build/compileall/pip check PASS. One usage snapshot isolation regression added (observed FAIL to PASS). No runtime data/index changes. See restructuring continuation report for scope and remaining gates.

</details>

## Resume validation — 2026-10-31 (A/B char budget + Docker staging thật)

Nối tiếp handoff 2026-10-31 trên checkout `main` sạch `f14c428…`, không audit lại,
không commit/push, không đổi active artifacts hay dữ liệu thật. WIP `budget=800`
được đánh giá rồi revert có bằng chứng.

- Ứng viên `generation-eval-budget800` cũ **không dùng được làm bằng chứng**: code sửa
  lúc 11:22:45 sau khi run 20 case kết thúc 11:20, runner không set env, không launch
  record. Đã chạy A/B có kiểm soát (`frozen_eval_ab.py`, arm ghim trong process,
  `prompt_chars` từng case): `None` 11/12 positive + 7/8 negative; `800` 11/12 + 7/8;
  prompt p50 4926 → 4578 (−7,1%). `positive-06` timeout 45,124s được cứu nhưng
  `positive-12` regress thành `no_selected_evidence`; latency p50 không dùng được vì
  prompt-prefix cache. **Quyết định: default giữ `None`**, revert code+test RED→GREEN
  (ImportError → 28 passed); bản promote lưu `/tmp/opencode/itlr-e2e/reverted-800/`.
- Fresh gates (`run_quality_gates.sh` qua `sg docker`): 494 Python / 146 Web PASS,
  coverage 67,63% / 47,05%; typecheck/lint/build/compileall/pip check PASS; pip-audit 0;
  npm audit 0 (minimatch 11.0.3 deduped); Bandit 0 High / 27 Medium / 46 Low.
- Docker staging lần đầu chạy được trên máy này: user **thuộc group docker (972)** nhưng
  shell thiếu supplementary group → `sg docker` là đường hợp lệ, không cần sudo/pkexec.
  Project `itlr-resume-1031c`, subnet 172.29.234.0/24, ports 19081/19444, image
  `--no-cache` (`api sha256:3dac1619…`, `web sha256:23e1a8ab…`), artifacts staging
  docker-a/docker-b, HF/model read-only, volumes riêng, không `down -v`. Kết quả:
  27/28 driver check PASS (check thứ 28 sai tham số probe `num_predict=8`, chạy lại
  đúng → PASS); Chrome 11/11, cancel socket provider 55ms, backup/restore 15 bảng,
  tamper reject, reload/rollback `docker-a↔docker-b`, restart giữ dữ liệu, ports đóng.
- Blocker còn lại: uncached 45s (FAIL, không nới), human faithfulness/entailment
  (`null`), capacity/soak/cold start, multi-host. Verdict **NO-GO** production.
- Evidence + SHA256: `reports/final-e2e-evidence/SHA256SUMS.txt`,
  `docker-resume-1031c/`; chi tiết trong [certification §11](../reports/FINAL_E2E_CERTIFICATION.md).

## Pipeline audit — 2026-10-31 (catalog sync, link audit, 404 root cause)

Root cause 404: index 178 item thật đã build/activate nhưng PostgreSQL Web chưa sync; CSV
`web_items.csv` bị no-clobber nên không refresh được. Sửa: export `--refresh` (merge giữ row
cộng đồng, atomic), `verify_web_catalog.py`, `audit_source_links.py`, tích hợp export+verify
vào `refresh_pipeline.py` (`--sync-web` tùy chọn), `appendCatalogRow` lấy id max. Kiểm chứng
thật: 178 row; trước sync `/courses/5129`=404 → sau sync 200, id lạ 404; audit mẫu 6 link MDN
200/robots OK. Tests 503 Python / 163 Web PASS, coverage 67,63%/51,45%, security 0.
[Pipeline audit](../reports/PIPELINE_AUDIT_2026-10-31.md). Production **NO-GO**.

## Final maintainability review — 2026-10-31

Refactor bảo toàn hành vi: prewarm Ollama dùng `llm_client.base_url/default_model`, thêm
`_history_payload`; Web gom rule SMTP về `isMailConfigured()`; thêm 2 test mailer; ARCHITECTURE
có mục trace request. 494 Python / **162 Web** PASS, coverage 67,63% / 51,42%, security 0.
Không đổi API/schema/model/ranking, không xóa file. [Review](../reports/FINAL_MAINTAINABILITY_REVIEW.md).

## Final codebase freeze — 2026-10-31

Cleanup cuối: bỏ import `content_hash` không dùng, đổi 2 tham số `req` không dùng thành `_req`;
`tsc --noUnusedLocals --noUnusedParameters` sạch; 39 cảnh báo pyflakes còn lại là re-export/noqa
có chủ ý (compat pickle/legacy). Không xóa file, không đổi dependency/API/schema/model. Gates:
494 Python / 160 Web PASS, coverage 67,63% / 51,42%, pip-audit 0, npm audit 0, Bandit 0 High,
secret scan 0. Verdict: **CODE FREEZE READY**, **PRODUCTION NO-GO** (cold SLO 49,80s, human
`null`). [FINAL_CODEBASE_FREEZE](../reports/FINAL_CODEBASE_FREEZE.md).

## Final release hardening — 2026-10-31 (business rules, cold/warm benchmark)

Đóng nốt các quyết định business: xóa lesson đã duyệt chỉ admin; `/account/logout-all` thu hồi
mọi JWT; `/forgot` dọn token cũ >1 ngày. Xác minh AUD-01→06 trên PostgreSQL 16 (rollback giữ
`old-hash/tv=0`; migration fresh/re-apply/legacy; recompute idempotent 50%→50%). Benchmark
cold/warm: cold 49,80s (prefill 43,42s @31,9 tok/s, load 6,21s), warm 0,33s; retrieval p50
145ms; stream warm p50 3,69s. **SLO 45s vẫn FAIL** trên CPU này. Gates: 494 Python / 160 Web,
coverage 67,63% / 51,42%, pip-audit 0, npm audit 0, Bandit 0 High; Docker staging 25/25 check
trước khi server restart cắt, Chrome 11/11, cancel 78ms, load conc1/2/4 + soak 120s. Human
scoring sheet 40 case sẵn sàng nhưng **NOT VERIFIED**. Verdict **NO-GO**.
Chi tiết: [FINAL_RELEASE_READINESS](../reports/FINAL_RELEASE_READINESS.md).

## Final production audit — 2026-10-31 (web correctness/security fixes)

Audit 824 file Git-tracked (manifest: `reports/audit-file-manifest-2026-10-31.tsv`), sửa 6 lỗi
có test RED→GREEN: (1) lesson chưa duyệt vẫn complete được và bị tính vào progress;
(2) approve/delete lesson không đồng bộ enrollment của người học khác; (3) reset password
không transaction nên có thể đốt token mà không đổi mật khẩu; (4) JWT cũ vẫn dùng được sau
khi đổi/reset mật khẩu; (5) spam email reset theo tài khoản; (6) race giữa hai lần đọc khi
tính progress. Thêm `users.token_version` (ALTER idempotent) + `withTransaction` và SQL
progress một câu. Không đổi API/schema cũ khác, không đổi RAG model/threshold/prompt.
Kết quả: 494 Python / 157 Web PASS, coverage 67,63% / 50,67%; npm audit 0; Bandit 0 High;
pip-audit BLOCKED (PyPI timeout) trong lượt này. SLO 45s vẫn FAIL, human `null`. NO-GO.
Chi tiết: [FINAL_PRODUCTION_AUDIT](../reports/FINAL_PRODUCTION_AUDIT.md).

## Final production remediation — 2026-10-31 (latency SLO, human packet, reliability)

Không sửa code runtime, không đổi model/SLO/hardware, không commit/push. Mục tiêu là đo
và kết luận trung thực thay vì hợp thức hóa PASS.

- **SLO 45s**: prompt thật 4893 chars / 1387 token. Sweep container Ollama cô lập:
  prefill cold 40–51s (27–34,5 tok/s), baseline 31,2; flash attention **34,5 (+10,6%)**;
  `num_batch=256` 34,0; `num_thread=6` 31,5; KV q8_0 26,9 (chậm hơn). Cache hit 0,14s.
  Compression `800` 11/12 (mất `positive-12`), `500` 10/12 (mất `positive-07`,`positive-11`)
  → giữ `None`. Kết luận: **SLO không đạt trên CPU này**; cần prefill ≥65–70 tok/s
  (CPU P-core mới hoặc GPU) và phải chạy lại frozen + cold/warm. Không nới SLO.
- **Human eval**: `human_eval_supplement.jsonl` (20 case: 8 positive, 6 hard-negative,
  3 multi-hop, 3 injection; VI 11/EN 9; SHA `818e3b35…`, frozen SHA không đổi) +
  `HUMAN_REVIEW_PROTOCOL.md` (SHA `f8a72a21…`, thang 0–3, quy ước human/AI/heuristic/judge,
  công thức unsupported-claim rate, citation precision, refusal accuracy).
  Chưa có reviewer → `human_* = null`, **NOT VERIFIED**.
- **Reliability/capacity** (staging single-host, volumes giữ): cold start 42s; chat cold
  đầu 40,25s; conc 2/4 max 4,13/9,16s (warm cache, 1 LLM worker); search conc 8
  1,69–1,84s so với 0,28s; soak 120s 89 vòng/45 chat, tất cả terminal `done`,
  p50 2,22s; cancel dừng ở `meta`, không `final/done`, health sau 5ms; kill -9 api →
  healthy 1s, DB counts users 1/messages 8/conversations 4/courses 3 không đổi;
  RSS api 921 MiB → 1,125 GiB, ollama 2,135 → 2,164 GiB. Soak dài, cold concurrency >1,
  multi-host **NOT VERIFIED**.
- Gates không đổi (không sửa code): 494 Python / 146 Web PASS, coverage 67,63%/47,05%,
  pip-audit 0, npm audit 0, Bandit 0 High. Verdict **NO-GO** với blocker ưu tiên
  hardware SLO, human labels, soak/HA. Evidence: `reports/final-e2e-evidence/bench-latency/`,
  `reliability-load/`, `SHA256SUMS.txt`; chi tiết §12 trong certification.
