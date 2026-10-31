# Kiểm thử và chiến lược kiểm chứng

Tài liệu chuẩn cho test, coverage và bằng chứng. Số đo mới nhất nằm ở
[VALIDATION](../reports/VALIDATION.md) và [certification](../reports/FINAL_E2E_CERTIFICATION.md);
đừng chép số cũ vào README hay báo cáo mới.

## 1. Lệnh chạy

Backend (từ repo root, không gọi provider trả phí):

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  USE_OLLAMA=0 DISABLE_RERANKER=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv/bin/python -m pytest tests/ -o addopts='' -q -ra
.venv/bin/python -m compileall -q itlr scripts eval
.venv/bin/python -m pip check
.venv/bin/python -m pip_audit --progress-spinner off
.venv/bin/python -m bandit -r itlr scripts -lll
```

Web (từ `web/`):

```bash
npm run typecheck
npm run lint
npm run build
npm test            # vitest run --coverage
npm audit --audit-level=moderate
npm ls minimatch --all
```

`pytest.ini` đặt `testpaths = tests` và `addopts = -q`; `-o addopts=''` chỉ dùng khi muốn
tắt quiet, không phải để bỏ phạm vi test. Web test dùng env giả lập trong
`web/vitest.config.ts`, không đọc `.env` của người vận hành.

## 2. Kết quả mới nhất (máy Linux, commit `f14c428`, không thay đổi code runtime)

| Suite | Kết quả | Coverage |
|---|---|---|
| Python `pytest tests/` | **494 passed / 0 failed / 0 skipped**, ~51s | statements **3946/5835 = 67,63%** (`itlr/`, gồm cả pipelines) |
| Web `vitest` | **146 passed / 26 file** | lines **648/1377 = 47,05%**; statements 44,24%; branches 36,15% |
| Typecheck / ESLint / build | PASS | — |
| compileall / pip check | PASS | — |
| pip-audit / npm audit | **0 advisory / 0 vulnerability** | — |
| Bandit | **0 High** (27 Medium, 46 Low — đã triage) | — |

Coverage là số đo local, không phải ngưỡng CI enforce. Không giảm coverage, không bỏ
assertion, không thêm `skip`/`xfail` để làm xanh suite ([CONSTRAINTS](../CONSTRAINTS.md)).

## 3. Phạm vi từng nhóm test (58 file Python)

| Nhóm tiêu biểu | Nội dung |
|---|---|
| `test_api_*`, `test_admin_security_cf` | contract HTTP, validation, rate limit, health/fingerprint, admin gate |
| `test_chunks_v3`, `test_retrieval_service`, `test_ann` | FAISS/BM25/RRF, ngưỡng, ANN fallback, thứ tự kết quả |
| `test_evidence_binding*`, `test_citations*` | bind quote, citation id/verbatim, refusal |
| `test_llm_*`, `test_stream*` | provider adapter, SSE frames, cancellation, strict UTF-8 |
| `test_versioning`, `test_index_probe`, `test_pipeline_fixture` | staging/probe/activate/rollback, builder parity |
| `test_collect_runner`, `test_collect_policy` | robots/rate limit/license flag ingestion |
| `test_pickle_handles`, `test_eval_scripts_paths`, `test_env_example` | đường dẫn artifacts, không đọc/ghi pickle thiếu context, không lộ secret trong `.env.example` |

Web test phủ middleware (auth, CSRF, security headers, upload signature), route handlers,
service (chat adapter, catalog CSV), DB helper với pool mock.

## 4. Test **không** chứng minh gì

- Model/fixture giả không chứng minh chất lượng neural, generation hay faithfulness.
- `citation_validation=valid` không phải entailment. Human metric chỉ có giá trị khi có
  người chấm thật ([EVALUATION](EVALUATION.md)).
- Unit/integration test không thay Docker/PostgreSQL/HTTPS/browser/backup/soak.
- Coverage cao không chứng minh đúng đặc tả; assertion yếu vẫn xanh.

## 5. Kỷ luật bằng chứng

1. Bug phải có test tái hiện **FAIL trước** khi sửa, **PASS sau** khi sửa; ghi lệnh + kết quả.
2. Không sửa test/kỳ vọng để hợp thức hóa hành vi sai; không nới timeout/coverage/lint.
3. Không chạy test ghi vào database/artifacts thật. Test chỉ dùng fixture tạm hoặc DB cô lập.
4. Không đưa key vào môi trường; luôn `env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY` khi thử local.
5. Log evidence mới vào `reports/final-e2e-evidence/`, kèm SHA256
   (`SHA256SUMS.txt`); không sửa log/hash cũ.

## 6. CI

`.github/workflows/ci.yml` chạy 4 job: `python` (pip check, compileall, full pytest,
integration subset), `web` (typecheck, lint, vitest, build, npm audit), `security`
(pip-audit, Bandit `-lll`), `web-integration` (PostgreSQL service tạm + migrate + login
smoke). Không có `continue-on-error` hay ignore list lỗ hổng. CI chỉ chứng minh cây đã
commit; working tree chưa commit phải tự chạy lại lệnh trên.

## 7. Gate ngoài unit test

| Gate | Cách chạy | Trạng thái gần nhất |
|---|---|---|
| Docker staging single-host | compose cô lập + `scripts/verify_staging_browser.cjs` | PASS scoped (§11.3) |
| Chrome E2E 11 check | driver CDP, TLS CA nội bộ | PASS 11/11, cancel 55ms |
| Backup/restore | `pg_dump` + `pg_restore` DB mới, so row hash | PASS 15 bảng |
| Artifact lifecycle | activate/reload/rollback/tamper | PASS |
| Frozen generation eval | `frozen_eval_ab.py` trên 20 case | 11/12 positive, 7/8 negative |
| Reliability/soak | `load.py` (cold, conc, soak, cancel) | PASS scoped; soak dài NOT VERIFIED |

Test treo trong sandbox không được skip: kiểm tra ngoài sandbox theo quyền được cấp và ghi
rõ giới hạn.
