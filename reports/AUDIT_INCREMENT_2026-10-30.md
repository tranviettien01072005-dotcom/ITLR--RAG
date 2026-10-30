# ITLR–RAG — correctness và data-integrity increment

## Final continuation — bằng chứng mới, 2026-10-30

**Verdict: NOT READY.** Nhánh `refactor/production-clean-architecture`, HEAD
`885f4113cf681ea40776b6c1f0699f925a8d8589`; `main` local ở `b06edcc`.
Working tree đã có các sửa đổi checkpoint bên dưới trước lượt tiếp nối; giữ nguyên,
không commit/merge/push, không activation/migration hoặc sửa runtime database.

### Sửa mới và review

- P2: timeout LLM nhận NaN/Infinity/0/âm. Regression **10 FAIL → 10 PASS**;
  toàn file LLM **26 PASS**. Giữ defaults/provider, trả `LLMError` khi cấu hình sai.
- P2: video post/message hiểu sai suffix và malformed/multipart Range. Thay regex
  bằng `req.range`, giữ authorization. Unsupported/malformed/multipart trả full 200,
  unsatisfiable bytes trả 416, suffix/open/oversized-end trả đúng bytes 206.
  Regression đầu **8 FAIL/6 PASS → 14 PASS**. Review độc lập phát hiện oversized
  suffix và unknown unit: bổ sung **4 FAIL/14 PASS → 18 PASS** sau sửa.
- Không thêm dependency, không xóa API/shim, không thay qrels hoặc quality floor.
- Ponytail **Ultra là mức của skill**, không phải model cần tìm trong registry.
  Nội dung registry ở checkpoint cũ bên dưới là lịch sử, không phải hạn chế của
  skill hiện có. Đã đọc Ponytail/Ultra, audit, review, TDD, security, performance
  và verification; reviewer độc lập kiểm diff và callers, không chứng nhận toàn repo.

### Gates thực chạy

| Gate | Kết quả mới |
|---|---|
| Full Python | **339 PASS/0 SKIP, 46,44s**, theo lệnh AGENTS, ngoài sandbox |
| LLM targeted | **26 PASS**; reviewer độc lập chạy lại 26 PASS |
| compileall / pip check | PASS / no broken requirements |
| Web typecheck / build | PASS |
| Web lint | 0 errors, 20 warnings |
| Full Web coverage | **94 PASS/18 files, 0 skip**; lines **40,02% (540/1349)** |
| Wheel packaging | PASS, isolated source copy, `pip wheel --no-deps --no-build-isolation`; kiểm shim BM25/static index/LLM file trong wheel |
| Bandit | 0 High, **28 Medium/57 Low**; chưa triage từng finding |
| npm audit / pip-audit | 0 vulnerabilities / no known vulnerabilities (project site-packages) |
| Secret patterns | 0 matches trong tracked text ≤2MB; chỉ private-key/AWS/OpenAI patterns, chưa quét toàn history |
| GitHub Actions đúng HEAD | SUCCESS: https://github.com/tranviettien01072005-dotcom/ITLR--RAG/actions/runs/40988613921 |
| Diff whitespace | PASS sau cập nhật tài liệu |

CI SUCCESS chỉ áp dụng commit HEAD; các thay đổi chưa commit chưa có CI tương ứng.
Web lần đầu lỗi thiếu ADMIN_PASSCODE; lần sau sandbox chặn listen EPERM (74 pass,
4 test không chạy). Không tính hai lượt đó là PASS, không thêm skip. Chạy lại với
secret fixture ngẫu nhiên và HTTP loopback ngoài sandbox mới có full PASS.
Log chi tiết tạm ở `/tmp/itlr-final-external.log`, `/tmp/itlr-web-full.log`,
`/tmp/itlr-range-{red,green}.log`, `/tmp/itlr-range-review-{red,green}.log`,
`/tmp/itlr-timeout-red.log`, `/tmp/itlr-package.log`, scanners `/tmp/itlr-final-*.log`.
Các file /tmp không phải artifact được lưu bền.

### Đo lường có giới hạn

BM25: synthetic 5.000 docs, một query rare-token, 200 serial calls, concurrency=1.
Reference full scan và postings hiện tại cho **exact score equality**.
Full scan p50/p95 **0,680/0,816 ms**, postings **0,0195/0,0201 ms**;
throughput khoảng **1.428/50.197 calls/s**, CPU **0,1395/0,00426 s**;
max RSS chung process **226.240 KiB**, không tách memory theo variant.
Đây là so sánh thuật toán đã có, không phải before/after bản sửa lần này hoặc SLO.
Fixture lexical eval chạy lại cô lập ở `/tmp/itlr-fixture`: 3 synthetic docs/3 queries,
60 requests; Recall@3/MRR@3/nDCG@3 đều 1,0 trên fixture này; latency p50/p95
**7,589/10,108 ms**; không có LLM. Chi tiết ở file tạm fixture_eval.json.
Semantic faithfulness, hallucination, human citation accuracy và full-corpus neural
metrics **null / NOT MEASURED**. Không dùng fixture làm bằng chứng production RAG.

### Release blockers và cách kiểm chứng tiếp

- **P1, NOT VERIFIED:** Docker/Compose, HTTPS proxy, PostgreSQL migration/concurrency,
  backup/restore, persistence và full account/search/chat/SSE/progress browser journey.
  `docker`, `psql`, `postgres` không có trên PATH. Trên staging cô lập có toolchain:
  làm theo `deploy/DEPLOY.md` và `deploy/PRODUCTION.md`; dùng env/volume/database
  fixture riêng, chạy migration/sync và journey qua HTTPS, diễn tập backup/restore
  và rollback. Không chạy các lệnh đó vào dữ liệu production.
- **P1, NOT MEASURED:** độc lập passage/human labels, generation entailment và tải
  neural/reranker thực. Cần corpus/labels độc lập và model đã được cấp phép; không
  gọi API trả phí/tải model lớn trong lượt này. Tham khảo `eval/bench_chunks_v3.py`
  và quy trình labeling/evaluation hiện có; không thay ground truth để nâng metric.
- **P2:** triage 28 Medium Bandit và 20 lint warnings; scanner gate không thay review.
  Chunker còn chuẩn hóa whitespace/indentation code; snapshot exporter chưa atomic
  cùng CSV, direct legacy builders chưa immutable chung. Đây là giới hạn đã nhận diện,
  chưa có sửa đổi/bằng chứng đủ để tuyên bố đã giải quyết.


## Phạm vi và trạng thái

Nhánh `refactor/production-clean-architecture`, base `885f411`; kế thừa `main`
(`b06edcc`) và năm commits refactor, không merge/commit/push/deploy. Working tree đầu
phiên sạch. Đây là checkpoint triển khai thực chất, **không phải hoàn tất toàn bộ
audit production**. Không thay database, pointer/index active hoặc dữ liệu runtime.

Đã đọc retrieval/chat flow, chunking, API, CF builder, crawler store và các báo cáo
hiện hành; hai agent read-only khảo sát thêm lifecycle, crawler, LLM và Web. Findings
từ agent là đầu mối cần kiểm chứng, không tự động được coi là lỗi đã chứng minh.

## Findings đã xử lý

Không xác nhận P0 trong phạm vi sửa. Các mức dưới là ưu tiên xử lý, không phải cam kết
không còn lỗi ngoài phạm vi.

| Mức | File | Nguyên nhân / tác động | Sửa và bằng chứng |
|---|---|---|---|
| P1 | `scripts/export_web_catalog.py` | `open('w')` truncate catalog chứa uploads cộng đồng | Exclusive creation (`x`): từ chối đích đã tồn tại, không ghi đè cả khi file xuất hiện trước lúc open; regression trên file tạm giữ nguyên byte |
| P1 | `itlr/pipelines/build_cf.py`, `itlr/engine.py` | Ghi CF trực tiếp vào version có manifest phá SHA256; hướng dẫn cũ dẫn operator tới đường này | Refuse manifest-bearing destination; hướng dẫn staging `--with-cf`; pin input/output vào cùng directory để activation đồng thời không chuyển đích ghi |
| P2 | `itlr/collect/chunk.py` | Tail merge và overlap có thể vượt max; `[-0:]` lặp cả chunk trước | Chỉ merge khi vừa bound, giới hạn overlap theo dung lượng còn lại, zero overlap thực sự rỗng, reject limits không hợp lệ |
| P2 | `itlr/chatbot/chatbot.py`, `itlr/retrieval/service.py` | Gate, search và retry type encode cùng query ba lần | Tái dùng vector trong phạm vi request; không cache shared mutable query; giữ đường legacy và cách gọi không truyền vector |
| P2 | `itlr/chatbot/chatbot.py` | Filter hụt bị bỏ ngầm; khoảng tháng đảo chiều; không phân biệt graph hết cạnh; regex `top` khớp `topic`; roadmap rỗng gây IndexError | Giữ filter, sửa handler và guards, có positive-control tests |
| P2 | `itlr/api/server.py` | VersionError thoát ra 500 hoặc làm startup thất bại | Missing/integrity-invalid artifacts → 503; reload vẫn giữ engine cũ nếu nạp candidate lỗi |
| P2 | `itlr/api/server.py` | `compare_digest(str,str)` không nhận non-ASCII; reload không có bucket riêng | So sánh bytes, reject token sai 403, rate ADMIN mặc định 10/IP/phút, ghi auth failure không ghi token |
| P2 | `itlr/core/rerank.py` | Lazy init đồng thời có thể tạo hai model | Lock + double check; log fallback load/predict; test dùng encoder giả, không tải CrossEncoder |
| P2 | `itlr/collect/store.py` | Event new thiếu `row_id` như docstring | Bổ sung `row_id`, giữ `row` cũ để tương thích |
| P2 | `tests/test_pickle_handles.py` | Guard không theo dõi builder V2 | Thêm `build_embeddings_v2.py`, không bỏ assertion |
| P2 | `itlr/chatbot/llm_client.py` | Numeric env malformed thoát ValueError ngoài hợp đồng LLMError | Wrap lỗi parse timeout/retries thành LLMError, không thay provider hoặc gọi live API |
| P2 | `web/src/routes/api.routes.ts`, `social.routes.ts` | Range end vượt buffer khiến Content-Length lớn hơn bytes gửi | Clamp end tới total−1; hai regression HTTP thật qua Express với DB/auth fixtures |

## Bằng chứng FAIL → PASS

- Chạy chính các regression đã sửa harness trên bản sao **HEAD chưa sửa** dưới
  `/tmp/opencode/itlr-red-o93f7ubx`: **23 failed / 10 passed (11,25s)**. Log tạm
  `/tmp/opencode/itlr-audit-red.log`. Không checkout/revert code trong working tree để
  tái hiện. Một số failures xác nhận interface vector còn thiếu; pipeline fixture thật
  xác nhận **3 lần encode thay vì 1**, không chỉ test signature.
- Exporter: **1 failed / 1 passed** trước exclusive creation → **2 passed** sau sửa;
  toàn bộ thao tác dùng file tạm, không chạy export catalog runtime.
- Review độc lập tìm thấy CF guard đọc lại pointer sau kiểm tra. Tiny pandas fixture
  tái hiện **1 failed** trước pin directory → targeted tests PASS sau sửa.
- LLM numeric env: **4 failed / 12 passed** trước sửa → **16 passed** sau sửa bằng
  SDK giả; media Range HTTP: **2 failed** trước clamp → **2 passed** sau sửa.
- Không xóa test, không skip/xfail mới, không hạ threshold.

## Kiểm chứng thực chạy ở checkpoint này

| Gate | Kết quả | Phạm vi |
|---|---|---|
| Python baseline | **288 passed / 0 skip, 48,26s** | Base refactor, không lấy số lịch sử làm kết quả mới |
| Python final | **329 passed / 0 skip, 50,19s** | Full `tests/`, gồm fixture/API integration và regression |
| compileall | **PASS** | `itlr scripts eval` |
| `pip check` | **PASS** | Venv hiện tại |
| `git diff --check` | **PASS** | Sau cập nhật tài liệu checkpoint đầu; kiểm lại sau bổ sung gates |
| Web typecheck / build | **PASS** | Node 22.23.4, dependency đúng package-lock |
| Web lint | **0 errors / 20 warnings** | Không suppress rule, cảnh báo typing còn lại |
| Web tests | **78 tests / 18 files PASS, 3,24s** | Lines 39,13% (524/1339), statements 36,6%, branches 27,38%, functions 28,62% |
| npm audit | **0 vulnerabilities** | `--audit-level=high` |
| Bandit High gate | **0 High** | Vẫn còn **28 Medium / 57 Low**, không suppress |
| pip-audit | **No known vulnerabilities found** | Quét site-packages venv (105 distributions), không audit nhầm venv của tool |

Lệnh full suite dùng `env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY USE_OLLAMA=0
DISABLE_RERANKER=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
.venv/bin/python -m pytest tests/ -o addopts='' -q -ra`.

Thời gian full suite không phải benchmark trước/sau: số tests khác nhau. Ban đầu Node,
npm và scanners thiếu; đã tải Node 22.23.4 chính thức, xác minh SHA256 archive và giải
nén dưới `/tmp/opencode`; cài Bandit 1.9.4/pip-audit 2.10.1 vào venv tool riêng tại đó.
Chạy `npm ci` theo lockfile; không sửa dependency declarations/lockfile hoặc venv dự án.

Web test run đầu thiếu JWT_SECRET làm một suite lỗi (74 tests pass, không được tính là
full PASS). Lượt đầy đủ sau đó dùng NODE_ENV=test, secrets ngẫu nhiên sinh trong process,
DATABASE_URL fixture; không in secrets và không tạo file .env. DB trong các test này
được mock, không chứng minh kết nối PostgreSQL runtime. Web baseline với cấu hình hợp
lệ **76 tests pass**, trước hai regression media. Có warning Vite config loader và PDF
fixture parsing; không tắt warning để làm đẹp log.

Lệnh scanner: `/tmp/opencode/audit-tools/bin/python -m bandit -r itlr scripts -lll`
và `... -m pip_audit --path /home/trantien/ITLR--RAG/.venv/lib/python3.14/site-packages
--progress-spinner off`. Web dùng PATH của Node tạm, chạy typecheck → lint → build →
test → npm audit với `subprocess.run(check=True)` để không che exit code gate trước.

## Đo lường và những thay đổi đã loại bỏ

Fixture 3 tài liệu synthetic, vector 2D cố định, một query `docker`, không human labels:
semantic chat có type không tồn tại đi qua gate → filtered search → unfiltered retry.
Số encoder invocation **3 → 1**; reranker initialization trong test hai thread **2 → 1**.
Đây là đo lượng công việc, **không** phải benchmark E5/CPU/RAM hoặc chất lượng RAG.
Recall@K/MRR/nDCG, p50/p95, throughput, RSS, semantic faithfulness/hallucination mới
đều **null / NOT MEASURED**; không sao chép metric lịch sử thành kết quả phiên này.

- Loại bỏ đề xuất GC tự xóa thư mục thiếu manifest: đó có thể là build đang chạy,
  không phải failed staging. Implementation GC **không đổi**; thêm test bảo vệ staging.
  Cleanup failed builds vẫn cần thiết kế ownership/completion policy an toàn.
- Loại bỏ việc ánh xạ cosine thành 90–100%: không có bằng chứng calibration; giữ
  nguyên điểm hiện hành. Display semantics vẫn là vấn đề cần xử lý riêng.
- Không đổi FAISS index, BM25/RRF, reranker model, off-topic threshold hoặc qrels vì
  chưa có benchmark/nhãn độc lập chứng minh lợi ích.

## Review và giới hạn còn lại

Model registry không có **Ponytail Ultra** (`models(query='Ponytail')` trả 0 kết quả).
Đã review diff theo correctness/readability/architecture/security/performance và dùng
agent độc lập mặc định; **không gọi đây là Ponytail review**. Reviewer yêu cầu sửa CF
pointer race; đã sửa và reviewer kiểm lại targeted tests, không còn required finding
trong phần CF fix. Không coi verdict này là chứng nhận toàn repository.
Reviewer cũng kiểm phần LLM/Range sau sửa: 16 LLM tests và 2 HTTP Range tests PASS,
không có required correction trong phạm vi này; không coi là full RFC/live SDK review.

Các đầu mối chưa hoàn thành / cần regression và implementation tiếp theo:

1. Course back link `javascript:` xung đột CSP; Range parser còn cần kiểm suffix,
   malformed và multi-range riêng. Oversized-end fix không chứng minh full RFC compliance.
2. LLM stream usage/cost accounting chưa sửa; numeric config đã wrap parse failures
   nhưng validation finite/positive và bounds còn cần bổ sung. Paid APIs/generation live
   không được gọi.
3. Exporter đã fail-closed với catalog hiện hữu, **chưa** có atomic cross-process
   merge/sync community rows. Muốn refresh catalog phải xuất file mới và duyệt merge;
   không xóa file hiện hữu để vượt guard. Snapshot output riêng chưa transactional với CSV.
4. Direct legacy builders khác chưa được bổ sung cơ chế immutable-version chung;
   không chạy chúng vào version active. CF guard không thay thế pipeline write lock.
5. Docker/HTTPS/browser E2E, PostgreSQL concurrency, backup/restore, full-corpus
   neural/reranker benchmarks và độc lập passage labels còn NOT VERIFIED/NOT MEASURED.
   Scanners không có High/advisory không chứng minh code an toàn tuyệt đối.

## Rollback và vận hành

Không có schema/artifact migration hoặc activation trong checkpoint; rollback code
chỉ cần quay lại bản base đã lưu sau khi lưu riêng mọi thay đổi chưa commit. Không dùng
`git reset --hard` hoặc discard toàn working tree. Không cần rollback database/index.

`POST /admin/reload` thêm bucket `ITLR_RATE_ADMIN_PER_MIN` (mặc định 10, `0` tắt),
429 có Retry-After theo limiter hiện có. Token vẫn bắt buộc khi bucket tắt.
`build_cf` phải dùng staging chưa stamp manifest; version mới qua probe/activate.
Catalog export đích tồn tại nay fail-closed, không còn silently overwrite như trước.
