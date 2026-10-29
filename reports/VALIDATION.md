# Kiểm chứng ITLR–RAG — đồ án sinh viên

Cập nhật 2026-10-30. Đây là bằng chứng theo phạm vi đã chạy, không phải chứng nhận production.

## Phiên tinh gọn và chuẩn hóa

- Baseline chạy lại:256 Python passed/0 skipped (33.04s), kế thừa mốc245 và các regression bổ sung.
- BM25 refit giữ IDF cũ đã tái hiện FAIL; reset state và postings đã sửa. Legacy pickle được hỗ trợ.
- Review phát hiện race lazy postings: request thứ hai đọc trạng thái đang tạo dở; test concurrent
  FAIL trước sửa, sau sửa chỉ công bố dictionary đã hoàn chỉnh.
- Benchmark sparse term:10.000 tài liệu synthetic,100 lần, output scores trước/sau bằng nhau.
  p50=3.748→0.067ms;p95=4.730→0.073ms. Chỉ là BM25 microbenchmark, không phải real-corpus RAG speedup.
  [Raw JSON](bm25_postings_benchmark.json). Postings dùng thêm RAM; chưa đo riêng phần tăng này.
- `npm run build` thiếu EJS/public/schema trong dist đã tái hiện FAIL bằng asset assertion.
  Build mới copy đủ; Dockerfile tái sử dụng cùng quy trình, bỏ ba lệnh copy trùng.
- Compiled web chạy ở cổng tạm3001:Chromium login200,1 form,0 pageerror;CSS200;
  `/ready`200 dùng PostgreSQL local sẵn có. Không migration hoặc ghi dữ liệu để chạy smoke.
  Đã dừng riêng process3001; không dừng web3000 hoặc API8000 đang dùng.
- README và AGENTS viết lại; deployment cập nhật; rà soát toàn bộ Markdown tracked, phân biệt
  lịch sử/ADR/kế hoạch với trạng thái hiện tại. Bảo toàn số đo và bản quyền nguồn.
  Sửa nhãn human_eval thành mô phỏng. Kiểm tra local Markdown file links bằng regression.
- Loại import SentenceTransformer không dùng, biến prev không dùng; giữ normalize_scores vì
  còn callers ở recommender/pipeline/LTR. Không xóa module/dependency chỉ dựa vào phỏng đoán.
- Bỏ khai báo MIT của chính package. Không tạo LICENSE mới. Không tích hợp Claude-Mem;
  các tham chiếu công cụ trong phần lịch sử không còn là giao thức bắt buộc.

## Ponytail Ultra audit / review / technical debt

What this repo does: a student IT learning project with a web interface, PostgreSQL and a Python RAG backend.
Assumed load: local Linux, one worker per service; preserve existing data and artifact compatibility.

Must fix found and addressed: BM25 refit stale vocabulary, partial lazy postings publication,
compiled web missing non-TypeScript assets, and misleading current-vs-historical documentation.
Each code defect has failing execution evidence before the correction. No unexplained High/Critical
finding remains in this changed group. This is a scoped audit extending prior reports, not proof that
all code paths are defect-free. No dependency was removed without use evidence.

Technical debt scan:0 shortcut:/ponytail: comment markers in application/eval/script sources.
A clean marker ledger is not absence of debt. Remaining:real reranker/DeepSeek validation,
independent passage labels, CPU/RAM and latency under full-corpus load, existing20 lint warnings,
and broader authenticated browser/database integration. No semantic faithfulness/hallucination
numbers were fabricated; historical real-snapshot results remain in their original reports.

## Chưa kiểm chứng

Docker image/Compose execution, DeepSeek live (paid calls not authorized), real CrossEncoder,
authenticated multi-step browser E2E, concurrent database transactions under load, device/power-loss
crash durability and full-corpus V3 activation. PostgreSQL readiness/login smoke does not cover
all of these. Active artifacts were not rebuilt or changed in this session. No deletion of runtime
or user data; no Git commit/push performed for this group.


## Kết quả cuối phiên — 2026-10-30

- Python:260 passed/0 skipped,34.22s; baseline đầu phiên256 passed/0 skipped,33.04s.
  Chênh lệch thời gian suite không phải benchmark hiệu năng vì số tests thay đổi.
- Web:59 tests pass; typecheck/build pass; ESLint0 errors/20 cảnh báo cũ; line coverage25.01%.
- Python wheel offline build pass; static API assets có trong wheel, metadata không khai báo MIT.
- compileall,pip check,git diff --check và test local Markdown links pass.
-43/43 Markdown tracked đã được rà soát/cập nhật: hướng dẫn hiện tại viết lại, lịch sử gắn nhãn
  và giữ số liệu. Không xóa giấy phép/bản quyền bên thứ ba.
- Code/config sửa:itlr/retrieval/bm25.py, itlr/pipelines/build_embeddings_v2.py,
  itlr/versioning.py, pyproject.toml, web/package.json, web/Dockerfile.
- Thêm tests/test_bm25_refit.py và tests/test_markdown_links.py;
  raw benchmark reports/bm25_postings_benchmark.json.
- Không đổi tên/xóa file hoặc dependency trong nhóm này. Chỉ bỏ import/biến không dùng và copy
  Docker trùng. normalize_scores vẫn giữ vì có callers thực tế. Không xóa node_modules/runtime.
- Kết quả trên được ghi trước publication; code/tests được lưu trong commit 93993b0.
  Xem lịch sử Git cho trạng thái push. Web3000 và backend8000 không bị sửa index hoặc dừng.

## Lịch sử kiểm chứng được bảo toàn

> **Ngữ cảnh đồ án — 2026-10-30:** Tài liệu lịch sử: giữ số đo, phạm vi và kế hoạch tại thời điểm ghi. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../README.md).

# Validation evidence — 2026-10-29

These are commands run during remediation. No production deployment, paid LLM API,
external crawl, or model download was performed. Historical report numbers are not
used as current evidence.

## Environment

Python 3.14.3; FastAPI 0.162.0, httpx 0.28.1, numpy 2.5.4, pandas 3.1.0,
scikit-learn 1.9.1, pytest 9.2.0. Uvicorn 0.54.0, Bandit 1.9.4 and pip-audit 2.10.1
were installed into the existing venv after approved network escalation.
Node/npm were initially absent from PATH; root agent installed isolated Node under
`/tmp` and handles Node results in FINAL_REMEDIATION.md. PostgreSQL/Redis/Docker
commands are absent from PATH. Torch, sentence-transformers, FAISS model assets,
HF model cache and runtime `var/artifacts` are absent. No DeepSeek key is present.
Only key presence was inspected; no secret value was printed.

## Commands actually run

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

## Actual HTTP smoke

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

## Fixture integration and evaluation

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

## CI additions

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
