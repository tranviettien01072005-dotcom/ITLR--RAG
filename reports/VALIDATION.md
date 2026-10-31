# ITLR–RAG | Intelligent IT Learning Platform — Validation

Latest blocker remediation: **489 Python PASS/0 skip**,~50s, statements **67,37%**;
**146 Web PASS**, lines **47,05%**. Typecheck/lint/build/compileall/pip check PASS,
pip-audit 0 advisory, Bandit 0 High (26 Medium dev-rủi ro đã triage), npm audit chỉ
còn 14 advisory moderate chuỗi dev (eslint/ejs-minimatch), không advisory runtime.
Frozen blind eval 20 case với Qwen2.5:3b thật: 11/12 positive được chấp nhận
`llm_extractive` với citation valid và quote byte-verbatim theo nguồn, 1 case
timeout 45s; negative 7/8 không đạt thành câu trả lời (2 off-topic gate tức thời,
1 extractive search-intent, 3 explicit no_selected_evidence, 2 timeout). Real
Chrome→Express→PostgreSQL journey 36/36 HTTP-DB + 9/9 browser PASS; backup/restore
15 bảng (fingerprint bằng), TLSv1.3 verified-cert smoke PASS; artifact lifecycle
build/probe/reload/rollback/tamper 9/9 PASS. Uncached full prompt vẫn FAIL trên 60s
(bottleneck prefill CPU provider). Docker daemon socket quyền root:root bị chặn →
Docker production staging BLOCKED. Human faithfulness/score chỉ tiêu vẫn null.
[Blocker resolution evidence](PRODUCTION_BLOCKERS_RESOLUTION.md),
[E2E certification](FINAL_E2E_CERTIFICATION.md).

## Checkpoint trước — refactor trách nhiệm module

| Gate | Kết quả thực chạy |
|---|---|
| Python | 414 PASS / 0 skip, 86,51s, coverage statements 65,73% |
| Web | 132 PASS / 25 files, line coverage 45,31% |
| Typecheck / lint / build | PASS |
| Compileall / pip check | PASS |

Raw logs: release-python.log, release-web.log. Không suy ra tốc độ tốt hơn từ
thời gian suite. [Inventory và Before/After](RESTRUCTURING_CONTINUATION_2026-10-30.md)
ghi rõ phạm vi static review và các gate staging chưa chạy.

## Các checkpoint lịch sử


Current verification entrypoint: [restructuring continuation](RESTRUCTURING_CONTINUATION_2026-10-30.md). Baseline 386 Python / 124 Web; older checkpoint paragraphs below are historical.

Historical checkpoint (superseded by the verification entrypoint above): Checkpoint mới: Windows dev host **384 Python pass/0 skip** (coverage statements **64,96%**), Web **124 pass/25 files**, lines **45,01%**; typecheck/build PASS, lint **0 warning**, Bandit 0 High (31 Medium/61 Low), npm audit/pip-audit sạch. Đã xóa API key thật khỏi `.env.example` working copy (không có trong git history), sửa normalize URL, passcode admin constant-time/open redirect, `resource`/torch portability, HTTP Range dedup và toàn bộ ESLint warning. Docker/PostgreSQL/HTTPS và human/neural RAG gates chưa xác minh; **NOT READY**. Xem [portability audit](AUDIT_PORTABILITY_2026-10-30.md).

## Checkpoint tiếp nối trên nhánh refactor

Full suite mới **329 passed/0 skip (50,19s)**, baseline nhánh **288/0 (48,26s)**;
compileall/pip check PASS. Web **78 pass/18 files**, coverage lines **39,13%**;
typecheck/build PASS, lint 0 lỗi/20 cảnh báo, npm audit 0 vulnerabilities.
Bandit 0 High (28 Medium/57 Low); pip-audit trên 105 distributions trong venv không có
advisory đã biết. Xem [audit increment](AUDIT_INCREMENT_2026-10-30.md)
cho FAIL → PASS, phần chưa hoàn thành và giới hạn đo lường. Nội dung bên dưới lưu
checkpoint trước; neural metrics không được chạy lại ở lần này.

Ngày kiểm chứng: 2026-10-30. Tài liệu phân biệt kết quả thực chạy trong phiên audit với
checkpoint lịch sử. [README](../README.md) là cổng tài liệu; [Deployment](../deploy/DEPLOY.md)
ghi điều kiện vận hành. Không suy ra production-ready từ kết quả unit tests.

## Kết quả phiên audit sản phẩm

| Kiểm tra | Kết quả thực chạy | Phạm vi / giới hạn |
|---|---|---|
| Python baseline | **260 passed, 0 skipped**, 48.90s | Ngoài sandbox; chưa áp nhóm sửa mới |
| Python final | **280 passed, 0 skipped**, 57.36s | Toàn bộ `tests/`, gồm API/fixture integration và regression |
| Python compileall | **PASS** | `itlr`, `scripts`, `eval` |
| `pip check` | **PASS** | Không có dependency requirement bị hỏng trong venv |
| Wheel offline | **PASS** | Có static assets, shared retrieval và BM25 pickle shim; không có MIT metadata |
| Bandit High gate | **PASS: 0 High** | Còn **28 Medium, 58 Low**; không tắt rule hoặc bỏ finding |
| pip-audit | Không tìm thấy advisory đã biết trong package quét được | `torch 2.15.0+cpu` không có trên PyPI nên **NOT AUDITED** |

Web đã chạy với Node 22.16.0 từ `/tmp/node-v22.16.0-linux-x64/bin`:

| Kiểm tra Web | Kết quả |
|---|---|
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS: 0 errors / 20 warnings** |
| `npm run build` | **PASS**; có views/public/schema trong dist |
| `npm test` | **64 tests / 15 files passed**, 4.04s |
| V8 coverage | Lines **27.06% (350/1293)**; statements **25.74%**, branches **20.72%**, functions **24.5%** |
| `npm audit --audit-level=high` | **0 vulnerabilities**, chạy ngoài sandbox sau lỗi DNS |

Không hạ threshold coverage; coverage còn thấp là giới hạn cần xử lý theo rủi ro.
Mỗi request có auth cookie hợp lệ nay đọc user hiện tại từ PostgreSQL; chưa đo chi phí dưới tải.
Thời gian suite không phải benchmark: baseline và final có số lượng tests khác nhau.

Các lệnh Python đã chạy:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  USE_OLLAMA=0 DISABLE_RERANKER=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv/bin/python -m pytest tests/ -o addopts='' -q -ra
.venv/bin/python -m compileall -q itlr scripts eval
.venv/bin/python -m pip check
.venv/bin/python -m bandit -r itlr scripts -lll
.venv/bin/python -m pip_audit --progress-spinner off --cache-dir /tmp/itlr-pip-audit
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation --no-index -w /tmp/itlr-platform-wheel
```

TestClient treo trong sandbox; lần chạy đó được dừng, không tính là PASS. Baseline/final
chạy ngoài sandbox sau khi được cấp quyền. pip-audit cũng chạy lại ngoài sandbox do DNS.
Không skip tests để che giới hạn môi trường. Logs phiên này nằm trong `/tmp/itlr-platform-*.log`;
đây là log tạm của workspace, không phải artifact CI được lưu lâu dài.

## Integration Web với PostgreSQL local

Bản compiled được khởi chạy riêng ở cổng **13001**, dùng cấu hình local bị gitignore và database
sẵn có, không migration hoặc seed. Bind trong sandbox gặp EPERM; smoke chạy ngoài sandbox:

| Request | Kết quả |
|---|---|
| `GET /health` | **200** |
| `GET /ready` | **200**, PostgreSQL truy cập được |
| `GET /login` | **200**, 1 form, CSP hiện diện |
| CSS được liên kết từ trang login | **200** |
| `GET /api/chat` với signed token của user ID không tồn tại | **401** |

Token kiểm thử tự tạo cho ID không tồn tại, không phải tài khoản thật; không ghi database.
Paid keys để rỗng, `USE_OLLAMA=0`; process tạm được dừng sau smoke. Đây là HTTP integration,
không phải browser E2E hoặc xác minh toàn bộ luồng người dùng có đăng nhập.

Compose và hai workflow YAML parse **PASS**; không có Docker CLI để build/run.
Mermaid đã đối chiếu luồng kiến trúc trong mã; renderer riêng **NOT VERIFIED**.

## Findings và bằng chứng RED → GREEN

| Mức | Lỗi tái hiện trước sửa | Thay đổi và regression |
|---|---|---|
| P1 | JWT 7 ngày vẫn giữ role cũ hoặc user đã xóa | Sau xác minh token, lấy user/role hiện tại bằng SQL parameterized; tests demotion/deletion |
| P1 | Login chấp nhận `/\\evil.example` dẫn ra host khác | Chặn backslash trong return path; test request qua router |
| P1 | Redirect crawler bỏ kiểm robots; retry/hop không throttle riêng | HTTPX request hook kiểm policy và rate trước mỗi request; MockTransport chứng minh URL bị chặn không được gọi |
| P1 | Listing 404 vẫn reconcile và đánh dấu bài mất; body 401/418 thành nội dung | Chỉ chấp nhận 2xx, listing lỗi không được xem là inventory hoàn chỉnh; regression RSS/API/web và bài lỗi |
| P1 | Policy/license cũ tồn tại sau cập nhật; full text bị thu hồi vẫn export | Cập nhật provenance khi refetch; thu hồi chặn reuse/export nguồn, giữ snapshot để đối chiếu; tests refetch/recheck/revocation |
| P2 | Top-K V3 40 chỉ trả tối đa 32 | Candidate budget tối thiểu bằng Top-K; regression 40 tài liệu |
| P2 | Nhiều chunk một tài liệu lấn hết item search | Chế độ unique item trước candidate truncation cho search/quick resources; semantic evidence vẫn chunk-level |
| P2 | Vector giống nhau bị loại tại cosine threshold 1.0 | Clip [-1,1], tolerance 1e-6 cho float32; test vector [1,2,3] |
| P2 | RRF cộng nhiều lần khi một ranking lặp item | Mỗi item xuất hiện một lần trong từng ranking; test không thổi phồng trọng số |
| P2 | Pipeline tính điểm nền hai lần | Truyền điểm đã tính vào candidate generation; test gọi một lần |
| P2 | Eval đọc lại artifact từ pointer mới và crash khi thiếu CF | Dùng model từ engine đang nạp, CF optional; regression không đọc lại file/version |
| P2 | Probe path có dấu nháy làm hỏng Python; sentinel bỏ qua exit code | Truyền path qua env, cwd cố định; yêu cầu exit=0 và sentinel; hai regression |

Không đưa số cải thiện chất lượng hay tốc độ mới khi chưa đo. Việc sắp xếp dense theo điểm
và row ID giúp tie ổn định nhưng cần O(n log n) trên tập được phép; FAISS vẫn materialize toàn
bộ chunk scores. Cần benchmark RAM/latency toàn corpus trước khi mở rộng.

Thu hồi full-text áp dụng cho collection-store export tiếp theo, không sửa artifacts đang active.
Operator cần rebuild → probe → activate; pipeline refresh không phải cơ chế thu hồi runtime tức thời.
Archived documents giữ license tại thời điểm thu nhận; metadata mới được ghi khi refetch.

## Thử nghiệm neural offline sau sửa

[Raw JSON của phiên audit](chunks_v3_audit_experiment.json). Model E5-base thật từ cache local,
8 snapshot đã check-in, **98 chunks**, **8 item-level qrels tự soạn**, không có distractor ngoài
8 tài liệu, không reranker, không generation/API trả phí. HF offline được giữ bật; thông báo
không truy cập Hub dẫn tới dùng cached commit, không tải model mới.

| Cấu hình | Recall@5 | MRR@5 | nDCG@5 | p95 ms | Mean CPU ms/query |
|---|---|---|---|---|---|
| Item-mean dense | 1.0 | 1.0 | 1.0 | 114.30 | 106.80 |
| Chunk hybrid RRF | 1.0 | 1.0 | 1.0 | 115.33 | 107.68 |

Whole-process peak RSS **1486.51 MiB**, gồm model và cả hai cấu hình; không phải RAM riêng từng
cấu hình. Query encoding được dùng chung cho hai phép đo. Candidate pool trong benchmark bao gồm
mọi chunk, không đại diện cấu hình bounded pool khi phục vụ. Không kết luận cải thiện tốc độ hay
chất lượng từ bộ nhỏ hoặc so thời gian với checkpoint khác. Faithfulness/hallucination/citation
accuracy vẫn **null** do không chạy generation.

Đã chạy `eval.bench_chunks_v3.main()` với OMP/MKL/OpenBLAS=1, paid keys unset, `USE_OLLAMA=0`;
`ROOT` của module được trỏ tới thư mục tạm chứa bản sao input snapshot, output sau đó được copy
sang tên JSON mới ở trên. Model cache vẫn là `var/hf` của repo. Cách này giữ nguyên JSON benchmark
lịch sử; chạy script trực tiếp mặc định sẽ ghi `chunks_v3_unified_experiment.json`.

## Phạm vi audit và quyết định giữ tương thích

- Retrieval/shared service/chunk/ranking: lần theo search, semantic chat, off-topic và quick resources;
  giữ API keys và đường artifacts V2. Item-search chọn đại diện chunk theo ranking trước rerank;
  không phải max CrossEncoder trên mọi chunk của mỗi tài liệu.
- Chatbot/citation/LLM: kiểm source contract, stream/final và regressions hiện có. ID hợp lệ không
  đo entailment; generation faithfulness/hallucination/citation accuracy mới vẫn **chưa đo**.
- Collection/HTTP/SQLite: xem policy, reconciliation, refetch, redirect và export; regression dùng fixture,
  không thay bằng bằng chứng live crawl. Snapshot không bị xóa.
- API/Web/PostgreSQL: kiểm validation, auth/authorization, SQL boundaries và build assets.
  Các kiểm thử mock không thay thế concurrency/database E2E.
- Lifecycle/build/config/eval/CI/Docker: giữ khóa local, atomic pointer/history và compatibility shim;
  kiểm regressions probe/reload/rollback và cấu hình đã có. Không migrate hay activate index đang chạy.
- Không xóa module/dependency chỉ dựa vào tìm kiếm tên; shim và các đường legacy còn callers.
  Bỏ dedup item thừa ở adapter search sau khi shared retrieval đã đảm bảo uniqueness.

Review diff theo correctness, readability, architecture, security và performance đã thực hiện.
Audit tìm lỗi có thể chứng minh trong phạm vi repository; không xác nhận mọi code path không có lỗi.

## Mức sẵn sàng và phần NOT VERIFIED

**Có bằng chứng regression local; chưa đủ điều kiện tuyên bố production-ready.**

- DeepSeek/OpenAI live: **NOT VERIFIED**, không gọi API trả phí.
- Real CrossEncoder và tải neural toàn corpus: **NOT VERIFIED** trong phiên này.
- Citation entailment, generation faithfulness/hallucination và đánh giá người học thật: **NOT MEASURED**.
- Docker image/Compose và GitHub-hosted CI: **NOT VERIFIED**; không có Docker CLI trong PATH.
- Authenticated browser E2E, tải đồng thời DB, backup/restore và power-loss/storage failure: **NOT VERIFIED**.
- Runtime giới hạn một worker/replica mỗi service, filesystem Linux local; không có bằng chứng distributed safety.

Không commit/push, không thêm LICENSE, không tích hợp Claude-Mem, không thay hoặc xóa runtime/database/index.
`node_modules/` untracked đầu phiên được giữ nguyên; secrets không đưa vào log hoặc tài liệu.

## Kiểm chứng tài liệu

**43/43 Markdown được Git quản lý đã được viết lại/cập nhật nội dung**, gồm README, AGENTS,
CONSTRAINTS, changelog, memory, nghiên cứu, ADR, deployment, reports, plans/tasks và Web security.
README dẫn tới tài liệu chi tiết; số liệu và phạm vi lịch sử được giữ riêng, không đổi thành kết quả mới.
Scan toàn bộ tracked Markdown không còn định vị bị cấm theo yêu cầu sản phẩm.

- Regression file links: **1 passed (0.04s)**.
- Kiểm tra riêng toàn bộ local file links, heading anchors và code fences: **43 files, 0 issues**.
- `git diff --check`: **PASS**; đối chiếu API routes/schema, module responsibilities và lệnh build/runtime.
- Không kiểm reachability toàn bộ external links, không xác minh lại quyền nguồn bên ngoài hoặc pricing.
- Mermaid đã review cấu trúc; chưa chạy renderer. Không dùng YAML parse làm bằng chứng container chạy được.

## Checkpoint 260/59 trước phiên (2026-10-30)

Baseline checkpoint **256/0 skip (33.04s)**; final **260/0 skip (34.22s)**;
Web **59 pass**, lint **0 error/20 warnings**, coverage lines **25.01%**. Wheel/typecheck/build,
compileall, pip check và file links đã PASS tại checkpoint đó, không thay kết quả mới ở đầu trang.

BM25 refit stale IDF và race công bố postings đã có FAIL → fix → PASS. Microbenchmark
10.000 tài liệu synthetic, 100 lượt: p50 **3.748 → 0.067ms**, p95 **4.730 → 0.073ms**,
output scores bằng nhau; [raw JSON](bm25_postings_benchmark.json). Chưa đo RAM tăng do postings;
không suy ra RAG speedup. Web build copy views/public/schema và bỏ copy Docker trùng.

Compiled Web cổng 3001 với PostgreSQL local: Chromium login **200**, **1 form**, **0 pageerror**,
CSS **200**, `/ready` **200**; process tạm được dừng. Không suy ra authenticated E2E.
Đã bỏ import SentenceTransformer/biến `prev` không dùng; giữ `normalize_scores` vì còn callers.
Kiểm marker debt tìm thấy **0** `shortcut:`/`ponytail:` comments, không chứng minh không có debt.
Code/tests checkpoint được ghi trong commit `93993b0`; đây là lịch sử, không phải commit phiên này.

## Bằng chứng 2026-10-29 (lưu lịch sử)

> Phạm vi lịch sử: môi trường và số đo dưới đây thuộc checkpoint 2026-10-29; không thay thế kết quả mới ở đầu tài liệu.

### Phạm vi lần kiểm chứng trước

These are commands run during remediation. No production deployment, paid LLM API,
external crawl, or model download was performed. Historical report numbers are not
used as current evidence.

### Môi trường lịch sử

Python 3.14.3; FastAPI 0.162.0, httpx 0.28.1, numpy 2.5.4, pandas 3.1.0,
scikit-learn 1.9.1, pytest 9.2.0. Uvicorn 0.54.0, Bandit 1.9.4 and pip-audit 2.10.1
were installed into the existing venv after approved network escalation.
Node/npm were initially absent from PATH; root agent installed isolated Node under
`/tmp` and handles Node results in FINAL_REMEDIATION.md. PostgreSQL/Redis/Docker
commands are absent from PATH. Torch, sentence-transformers, FAISS model assets,
HF model cache and runtime `var/artifacts` are absent. No DeepSeek key is present.
Only key presence was inspected; no secret value was printed.

### Các lệnh đã chạy

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/ --tb=short` | **PASS: 200 passed, 5 skipped, 1 warning in 29.40s** (outside sandbox; test count includes concurrent remediation edits available at run start) |
| `.venv/bin/python -m pytest tests/test_collect_utils.py tests/test_pipeline_fixture.py` | **PASS: 14 passed in 2.50s** |
| `.venv/bin/python -m pip check` | **PASS: No broken requirements found** |
| `.venv/bin/python -m compileall -q itlr scripts eval` | **PASS: rc=0** |
| `.venv/bin/python -m pip_audit --progress-spinner off --cache-dir /tmp/itlr-pip-audit` | **PASS: No known vulnerabilities found**, installed environment only |
| `.venv/bin/python -m bandit -r itlr scripts -lll` | Initially **FAIL** on SHA1 URL identity use. After declaring `usedforsecurity=False`, **PASS: 0 High**; 52 Low and 26 Medium remain scanner findings requiring context/triage. No rules or findings suppressed. |
| `.venv/bin/python eval/eval_fixture.py` | **PASS**, measured report `reports/fixture_eval.json` |
| PyYAML parsing `.github/**/*.yml` | **PASS**, syntax parse only; GitHub-hosted workflow execution **NOT VERIFIED** |

The five pre-existing artifact-dependent API tests are skipped because artifacts
are absent. This is not evidence that real dense retrieval or CF succeeds.
FastAPI emits a Starlette warning that httpx TestClient support is deprecated.

Sandboxed TestClient hangs were reproduced with faulthandler showing an AnyIO
blocking portal wait during TestClient startup. The same suite completes outside
the sandbox. No tests were skipped or weakened to conceal this environmental issue.

### HTTP smoke

Ran `USE_OLLAMA=0 .venv/bin/python -m uvicorn itlr.api.server:app --host 127.0.0.1 --port 18000 --no-proxy-headers`
outside sandbox, then sent urllib HTTP requests to that loopback listener.

| Endpoint | Observed result |
|---|---|
| GET `/` | 200, 7401 bytes, CSP present, `X-Content-Type-Options: nosniff` |
| GET `/health` | 503, explicit missing-artifacts response |
| POST `/api/search` with `{"query":"docker"}` | 503, explicit missing-artifacts response |
| POST `/admin/reload` with no token | 403, admin API disabled |

API process shut down cleanly after smoke. UI delivery and fail-closed behavior
PASS; engine readiness and a real neural RAG query remain **NOT VERIFIED**.

### Fixture integration và evaluation

`tests/test_pipeline_fixture.py` exercises RSS fixture → extraction/quality →
SQLite → normalized catalog with license/origin → chunking → TF-IDF/BM25 model →
artifact write/reload → ranked retrieval, including expected item ID and URL.
HTTP fetching is a deterministic fixture, not a live crawl. Embeddings and LLM
are deliberately outside this test.

`eval/eval_fixture.py` uses three synthetic catalog items and three authored queries,
20 repeats each (60 requests). Labels are authored expected IDs, not human evaluation.
Recall@3, MRR@3, nDCG@3 each measured 1.0 on this trivial fixture.
Measured lexical latency p50=5.48ms, p95=7.81ms, p99=9.29ms.
Zero LLM calls/tokens means measured API spend $0. Groundedness, citation accuracy
and hallucination are null/unmeasured. This report cannot justify production RAG
quality, live DeepSeek correctness, CPU reranker changes or capacity claims.

### CI được bổ sung

`.github/workflows/ci.yml` runs Python compilation/dependency consistency/pytest,
API and fixture pipeline integration, Node lint/typecheck/test/build/npm audit,
pip-audit, Bandit High gate, and a PostgreSQL migration + login HTTP smoke job.
`.github/dependabot.yml` requests weekly Python, Node and Actions updates.
No `continue-on-error` or vulnerability ignore list exists.
The PostgreSQL service uses trust auth **only for its disposable CI database on a
runner loopback port**; no production credentials or repository secrets are required.
Application JWT/admin/database strings are generated per job. Never copy CI trust
authentication to production. Hosted Actions run and branch protection settings
remain unverified; no remote settings or public deployment were changed.

Sources for CI/security tool use:
[GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[pip-audit](https://github.com/pypa/pip-audit),
[Bandit](https://github.com/PyCQA/bandit).

## Stream hardening continuation ? 2026-10-30

[Fresh evidence](HARDENING_STREAM_2026-10-30.md): terminal usage-only chunk regression 2 FAIL ? PASS; 34 client tests and 124 Web tests PASS. Initial full Python run: 378 PASS/6 encoding failures; do not replace this result with historical counts.

Final fresh full Python verification: 386 PASS / 0 skip, coverage 65% rounded, 188.40s, UTF-8 environment; reports/hardening-utf8.log. Outside-sandbox diagnostic failed on temporary-directory permissions (4 FAIL / 129 setup errors); retained separately. Focused portability 21 PASS; client/link review 35 PASS.

Restructuring verification: 387 Python PASS/0 skip (91.94s), coverage 65% rounded; 124 Web PASS, line coverage 45.01%; typecheck/lint/build/compileall/pip check PASS. One usage snapshot isolation regression added (observed FAIL to PASS). No runtime data/index changes. See restructuring continuation report for scope and remaining gates.
