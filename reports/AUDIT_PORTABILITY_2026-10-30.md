# Audit và hoàn thiện — 2026-10-30

Phiên Windows/Python 3.12.10/Node 26 (không có WSL, Docker, PostgreSQL). Base sạch
`f977876`; không commit/push, không migration, không sửa database/artifact runtime, không
gọi API trả phí. Tài liệu này thay thế bản portability trước đó trong cùng working tree.

## 1. Inventory và trạng thái audit

`git ls-files`: **352 file** (130 `.py`, 53 `.ts`, 50 `.md`, 30 `.ejs`, 27 `.json`,
13 `.csv`, 6 `.js`, 6 `.example`, 4 `.yml`, 3 `.woff2`, 3 `.log`, 3 `.css`, 3 `.html`,
1 `.sql`, 1 `.jsonl`; còn lại là config Docker/CI/Makefile). Untracked chỉ gồm file mới
của phiên này. Không có submodule.

| Khu vực | Trạng thái |
|---|---|
| `itlr/api/` (9) | Đọc; sửa scheme validation pre-warm, rate limit/health giữ nguyên |
| `itlr/chatbot/` (11) | Đọc luồng LLM/retrieval; sửa base URL scheme, logging fallback |
| `itlr/collect/` (11) | Đọc HTTP/robots/SSRF, store, extract; sửa normalize URL |
| `itlr/core/` (9) | Đọc ANN/embeddings/chunks/rerank; không đổi thuật toán |
| `itlr/eval/` (6) | Sửa assert → ValueError, thêm test thống kê |
| `itlr/pipelines/` (6) | Kiểm tra guard CF/versioning/serialization qua test |
| `web/src/` (92) | Đọc routes/middleware/services/views; sửa type, CSP, Range, log |
| `tests/` (50) | Chạy toàn bộ; thêm 6 file Python + 5 file Web regression |
| `scripts/`, `eval/` | Chạy compile/import probe; sửa portability và assert |
| `configs/`, `deploy/`, CI | Parse YAML; kiểm tra secret; Docker/Postgres **BLOCKED** |
| Docs/reports | 50 `.md`; cập nhật changelog/memory/validation/báo cáo này |

Loại trừ nội dung: `.venv/`, `web/node_modules/`, `web/dist/`, `__pycache__/`,
`.pytest_cache/`, `var/` runtime, font/ảnh và CSV/JSON sinh tự động. Không đọc `.env`
cục bộ (gitignored); không in giá trị secret trong log/báo cáo.

## 2. Findings và cách xử lý

| Mức | Vị trí | Vấn đề | Xử lý |
|---|---|---|---|
| **High (local)** | `.env.example:7` | Working copy chứa API key DeepSeek thật (`sk-…`, 35 ký tự). Không có trong git history/HEAD nhưng là secret thật trong file tracked. | Xóa giá trị, đổi hướng dẫn; thêm test chặn secret trong mọi `.env.example`; khuyến nghị rotate nếu key còn hiệu lực. |
| Medium | `eval/bench_chunks_v3.py` | `import resource` (Unix-only) làm test import fail trên Windows. | Import tùy chọn; RSS = `null` kèm `memory_scope` trung thực; import probe PASS. |
| Medium | `tests/test_api_integration.py`, `test_lifecycle_robustness.py` | Import `sentence_transformers`/torch thật dù đã dùng encoder giả, khiến 11 test API/lifecycle bị chặn. | Chèn module stub qua `sys.modules` như pattern có sẵn; test vẫn chạy engine/versioning thật. |
| Medium | `itlr/collect/url_util.py` | `http://host:80` → `https://host:80`; credential trong URL được giữ. | Bỏ default port theo scheme gốc, từ chối userinfo; regression FAIL → PASS. |
| Medium | `web/src/routes/admin.routes.ts` | So sánh passcode admin bằng `!==` (không constant-time); redirect sau thao tác lấy nguyên `Referer` (open redirect). | `passcodeMatches` dùng SHA-256 + `timingSafeEqual`; `safeRefererPath` chỉ cho same-origin; 6 test mới. |
| Medium | `web/src/views/course.ejs` | Link `javascript:` bị CSP `script-src 'self'` chặn. | Link tĩnh theo trạng thái đăng nhập; test quét toàn bộ view. |
| Medium | `api.routes.ts`, `social.routes.ts` | Logic Range trùng lặp, dễ lệch. | Tách `services/http-range.ts`; 18 test Range chạy qua cả hai route. |
| Medium | `pages.routes.ts` | 3 fallback `catch {}` không log. | `console.warn` có ngữ cảnh. |
| Low | `llm_client.py`, `api/server.py` | `urlopen` nhận base URL không giới hạn scheme. | Chỉ cho `http(s)`, raise `LLMError`; 1 regression test. |
| Low | `itlr/eval/significance.py`, scripts | `assert` trong thư viện/CLI bị bỏ khi `python -O`. | `ValueError`/`RuntimeError`; thêm 4 test thống kê. |
| Low | `itlr/locking.py`, `itlr/versioning.py` | `fcntl`/`os.O_DIRECTORY` chỉ có trên POSIX. | Fallback `msvcrt` + bỏ fsync thư mục khi nền tảng không hỗ trợ; Linux không đổi. |
| Low | 20 ESLint warning | `any` tường minh ở error handler, DB row, check script. | Type hẹp (`unknown`, Express types, `QueryResultRow`, `Record<string, unknown>`); lint 0 warning. |
| Low | `query_understanding.py`, `refresh_pipeline.py`, `bench_latency.py` | Fallback im lặng. | Ghi debug/warning hoặc đưa lỗi vào summary. |

Bandit còn **31 Medium / 61 Low**, 0 High; phân loại ở mục 5. Không suppress rule nào.

## 3. Thay đổi theo nhóm

- **Security/trust boundary:** xóa secret khỏi example + test; giới hạn scheme LLM; validate
  `course.link`; CSP-safe view; so sánh passcode admin constant-time; chặn open redirect
  qua `Referer`; giữ nguyên SSRF/robots/manifest hiện có.
- **RAG/ingestion:** sửa chuẩn hóa URL (default port, credential); thêm benchmark lexical
  trên snapshot thật; không đổi BM25/RRF/chunking/threshold vì chưa có benchmark chứng minh
  lợi ích.
- **Clean code:** gom Range vào một helper; bỏ `any`; assert → exception; log fallback;
  bỏ import nặng khỏi test fixture.
- **Portability:** `resource`, `fcntl`, `O_DIRECTORY`; test chạy được trên Windows dev.
- **Docs:** cập nhật validation/memory/changelog; báo cáo này thay bản trước.

## 4. Kiểm chứng thực chạy

| Gate | Kết quả |
|---|---|
| Python full | **384 passed / 0 skipped / 0 failed**, 77,75s |
| Python coverage | **64,96%** statements (3.621/5.574), `--cov=itlr` |
| compileall / pip check | PASS / no broken requirements |
| Web tests | **124 passed / 25 files**, 0 skip |
| Web typecheck / build | PASS |
| Web lint | **0 errors / 0 warnings** |
| Web coverage | lines **45,01%** (609/1.353) |
| npm audit | **0 vulnerabilities** |
| pip-audit | **No known vulnerabilities found** |
| Bandit | **0 High**, 31 Medium / 61 Low |
| YAML (Compose + CI) | parse OK |
| Secret scan (tracked) | 0 giá trị secret sau sửa |
| `git diff --check` | PASS |

Lệnh Python dùng `PYTHONUTF8=1` và unset key/`USE_OLLAMA=0`/`DISABLE_RERANKER=1`;
không có lần chạy nào gọi LLM hoặc API trả phí.

### Coverage trước/sau ở module trọng yếu

| Module | Trước | Sau |
|---|---:|---:|
| `itlr/eval/metrics.py` | 35,6% | **97,3%** |
| `itlr/eval/diversity.py` | 16,4% | **93,4%** |
| `itlr/eval/significance.py` | 83,6% | 83,6% |
| `itlr/core/rag.py` | 15,7% | **30,7%** |
| `itlr/versioning.py` | 90,9% | 90,9% |
| `itlr/retrieval/bm25.py` | 96,6% | 96,6% |
| Python tổng | 62,94% | **64,96%** |
| Web lines | 43,97% | **45,01%** |

### Benchmark tái lập

**Lexical trên snapshot thật** (`eval/eval_lexical_real.py`): 118 tài liệu curated, 8
query/qrels do kỹ sư soạn (một annotator, **không phải human panel**), 160 request,
MMR tắt, không neural/LLM. Recall@5 **1,0**, MRR@5 **0,9375**, nDCG@5 **0,9539**;
latency p50/p95/p99 **52,1 / 62,0 / 83,3 ms**; throughput **18,7 query/s** đơn luồng.
Đây là baseline lexical, không chứng minh chất lượng neural/generation.

**Fixture synthetic** (`eval_fixture.py`, chạy trong thư mục tạm): 3 tài liệu/3 query/60
request; Recall@3/MRR@3/nDCG@3 = **1,0**; p50/p95/p99 **5,07 / 7,69 / 10,26 ms**.
Neural/reranker/faithfulness/answer relevance/human labels **NOT MEASURED**.

## 5. Bandit triage

Chi tiết từng rule/vị trí và quyết định: [BANDIT_TRIAGE_2026-10-30](BANDIT_TRIAGE_2026-10-30.md).
Tóm tắt: **0 High**, 31 Medium / 61 Low; B301 pickle và B310 urlopen là rủi ro được
chấp nhận có kiểm soát, không suppress rule.

| Rule | SL | Kết luận |
|---|---|---|
| B301 pickle | 26 | Chấp nhận có kiểm soát: artifact local, manifest SHA256 + path confinement + builder tin cậy; pickle vẫn là RCE nếu attacker ghi được artifact. Production phải mount read-only và bật `ITLR_REQUIRE_ARTIFACT_MANIFEST=1`. |
| B310 urlopen | 5 | URL do operator cấu hình; đã validate `http(s)` tại `llm_client.base_url`/pre-warm; crawler dùng `_validate_public_url`. |
| B311 random | 23 | Jitter/sampling, không dùng cho bảo mật. |
| B403/B404/B603/B607 | 30 | `subprocess` argv cố định, `shell=False` trong script build/verify. |
| B110/B112 | 8 | Phần lớn là fallback có chủ đích (encoding console, warning import, JSON-LD hỏng); đã log thêm ở các điểm có ngữ cảnh. |
| B101 assert | 0 | Đã thay bằng exception. |

Scanner không thay thế review; không có High không chứng minh code an toàn tuyệt đối.

## 6. Production gates

| Gate | Trạng thái | Ghi chú |
|---|---|---|
| Docker build / Compose up | **BLOCKED** | `docker`/`podman` không có trên PATH; chỉ parse YAML và kiểm tra HEALTHCHECK/health dependency tĩnh |
| PostgreSQL migration/concurrency | **BLOCKED** | không có `psql`/server |
| HTTPS/browser E2E, backup/restore | **BLOCKED** | không có staging |
| Linux `flock`/artifact activation | **NOT RUN** | chỉ chạy fallback Windows; logic Linux giữ nguyên |
| Neural/reranker/human eval | **NOT MEASURED** | thiếu model/low labels; không gọi API trả phí |
| Static/YAML/secret/dependency audit | **PASS** | xem bảng trên |

## 7. Còn tồn tại

- Key từng nằm trong working copy: nếu là key thật, **rotate ngay**; không cần purge git
  history vì `git log -S`/HEAD không chứa key.
- Pickle vẫn là trust boundary; deployment phải giữ artifact read-only/trusted.
- Docker/PostgreSQL/HTTPS/migration và neural quality chưa xác minh → **NOT READY**.
- Web coverage 43,97% còn thấp; các route admin/social/upload chưa phủ đầy đủ.
- 20 warning cũ đã hết, nhưng Bandit Medium/Low vẫn cần review định kỳ.

## 8. Rollback

Chỉ thay đổi code/test/docs; không có migration/activation. Rollback bằng cách hoàn các
thay đổi working tree sau khi lưu; không cần rollback database/index. Không commit/push.

## 9. Kết luận: NO-GO

Không tuyên bố production-ready. Các gate bắt buộc còn **BLOCKED/NOT MEASURED**: Docker
image/Compose runtime, PostgreSQL migration/concurrency, HTTPS/browser E2E và
backup/restore, Linux `flock`/activation, neural/reranker/human RAG evaluation. Phần đã
PASS chỉ chứng minh chất lượng mã nguồn, lexical retrieval và các boundary security đã
được test trong môi trường Windows hiện tại.

Điều kiện tối thiểu để chuyển sang GO: chạy `deploy/PRODUCTION.md` trên staging Linux cô
lập (build image, migrate, activate artifact có manifest, smoke HTTPS/SSE, backup/restore,
rollback, một worker/replica) và đo lại neural retrieval/generation trên bộ nhãn độc lập.

