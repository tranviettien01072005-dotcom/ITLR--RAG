# Hướng dẫn làm việc với ITLR–RAG

Cập nhật: 2026-10-31. Sản phẩm: **ITLR–RAG | Intelligent IT Learning Platform** — nền tảng
học CNTT tiếng Việt: tìm tài nguyên, hỏi đáp RAG có trích dẫn, lộ trình và tiến độ. Mô tả
dựa trên khả năng có trong repo; không suy diễn trạng thái thương mại, license hay
production-ready. Không tự gán MIT; giữ license/attribution bên thứ ba.

## Tiếp nhận công việc

1. Đọc file này, [CONSTRAINTS](CONSTRAINTS.md), [memory](docs/PROJECT_MEMORY.md), báo cáo mới
   nhất và `git status`/diff trước khi sửa. Phân biệt lịch sử với trạng thái hiện hành.
2. Kế thừa kết quả đã có; ghi trạng thái trong repo. Không yêu cầu/tích hợp Claude-Mem.
3. Thay đổi nhỏ nhất giải quyết đầy đủ yêu cầu. Bug phải có bằng chứng **FAIL → fix → PASS**;
   review diff sau mỗi nhóm thay đổi.
4. Giữ thay đổi người dùng, runtime và database; không xóa dữ liệu, che lỗi, bỏ assertion
   hoặc hạ chất lượng test để đạt PASS.
5. Không gọi API trả phí nếu chưa được phép. Khi thử local: unset `DEEPSEEK_API_KEY` và
   `OPENAI_API_KEY`.
6. Khi hành vi thay đổi, cập nhật README/tài liệu liên quan, CHANGELOG và memory; ghi rõ phần
   đã chạy, đã thử và chưa kiểm chứng.
7. Không commit/push nếu yêu cầu hiện tại không bao gồm việc đó. Quyền publish của phiên cũ
   không cấp lại quyền cho phiên mới.

## Ranh giới kiến trúc

| Khu vực | Trách nhiệm / ràng buộc |
|---|---|
| `web/` | Giao diện chính Express + TypeScript + EJS + PostgreSQL, cổng 3000 |
| `itlr.api.server:app` | Backend FastAPI cổng 8000; UI tĩnh chỉ là giao diện phụ |
| `itlr/retrieval/` | Retrieval service dùng chung, BM25, ngưỡng `min_pct` |
| `itlr/core/chunks.py` | FAISS chunk, RRF, passage reranking |
| `itlr/collect/`, `itlr/pipelines/` | Ingestion có robots/rate-limit/SQLite; build artifacts |
| `itlr/chatbot/llm_client.py` | Tầng generation LLM duy nhất: DeepSeek/OpenAI/Ollama |
| `itlr/versioning.py`, `itlr/locking.py` | Staging, probe, pointer/history atomic, rollback, GC, khóa Linux local |

- Artifacts cũ giữ đường V2. Không xóa/đổi tên shim `itlr/core/bm25.py`: pickle cũ tham chiếu
  module này.
- `/admin/reload` yêu cầu `X-Admin-Token` khớp `ITLR_ADMIN_TOKEN`; chưa cấu hình phải 403.
- CF tùy chọn: thiếu model trả 503 ở personas/for-you, không làm hỏng retrieval.
- Một worker/replica mỗi service trên local filesystem; không suy diễn khóa local/limiter RAM
  thành hỗ trợ nhiều host.

## Checkpoint hiện hành

**510 Python PASS/0 skip** (coverage statements **68,27%**), **166 Web PASS** (lines
**52,41%**); typecheck/lint/build, compileall, pip check, pip-audit 0, npm audit 0, Bandit
0 High PASS. Docker staging single-host + Chrome **11/11** PASS trong phạm vi đã kiểm
([certification](reports/FINAL_E2E_CERTIFICATION.md)). A/B char budget 800/500 suy giảm theo
case nên default giữ `None` ([ADR-013](docs/decisions/ADR-013-evidence-excerpt-budget.md)).
Qwen CPU-only **không đạt SLO 45s** cho prompt uncached; human faithfulness **NOT VERIFIED**.
**Verdict: NO-GO production.**

Số 489/146, 457/145, 414/132... là lịch sử; không trình bày như lần chạy mới. Chi tiết và
evidence SHA256: [VALIDATION](reports/VALIDATION.md), `reports/final-e2e-evidence/`.

## Kiểm chứng trước bàn giao

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  USE_OLLAMA=0 DISABLE_RERANKER=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv/bin/python -m pytest tests/ -o addopts='' -q -ra
.venv/bin/python -m compileall -q itlr scripts eval
cd web
npm run typecheck && npm run lint && npm run build && npm test
```

Thêm `pip check`, `pip-audit`, Bandit, `npm audit` khi bàn giao release. Chỉ sửa tài liệu thì
kiểm tra diff, nội dung, đường dẫn và link; không chạy migration/build index để "chứng minh"
thay đổi văn bản. Test treo trong sandbox: chạy ngoài sandbox theo quyền được cấp, không skip.
Chi tiết suite và coverage: [TESTING](docs/TESTING.md).

## Dữ liệu và bảo mật

- Catalog legacy 5.000 item và interactions CF là **synthetic**; snapshot thật ở
  `data/curated_resources.jsonl` (118 trang). `/health` gồm readiness/items/CF và fingerprint
  artifacts đã nạp (`version` + `manifest_sha256`); fingerprint chỉ đổi sau reload thành công;
  không dùng `CURRENT.json` làm bằng chứng engine đã reload.
- Qrels metadata/rule-based, nhãn mô phỏng và chẩn đoán bằng luật không thay thế đánh giá
  độc lập của người thật. Citation id hợp lệ không chứng minh faithfulness; chỉ tiêu chưa đo
  ghi `null`, không ghi 0% lỗi.
- Secret chỉ ở env/file local bị gitignore; không in key, mật khẩu hay reset token vào
  log/report.
- Paths qua `itlr/config.py`; pickle chỉ từ builder tin cậy. Giữ SHA256 inventory; hash không
  xác nhận tác giả nếu attacker sửa được cả file và manifest.
- Rolling feed không suy ra bài đã xóa chỉ vì vắng mặt; `listing_is_complete` và
  `full_text_allowed` phải là JSON boolean.

## Tài liệu

[README](README.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [RAG](docs/RAG.md) ·
[API](docs/API.md) · [TESTING](docs/TESTING.md) · [EVALUATION](docs/EVALUATION.md) ·
[SECURITY](docs/SECURITY.md) · [DEPLOY](deploy/DEPLOY.md) · [PRODUCTION](deploy/PRODUCTION.md) ·
[CONSTRAINTS](CONSTRAINTS.md) · [ADR](docs/decisions/ADR-001-deepseek-primary-llm.md).
Đọc [ADR-010](docs/decisions/ADR-010-shared-retrieval-and-atomic-state.md) và
[V3 review](reports/V3_RESTRUCTURING_2026-10-30.md) trước thay đổi kiến trúc.

Windows: đặt `PYTHONUTF8=1` và `PYTHONIOENCODING=utf-8` trước lệnh Python; dùng `npm.cmd`
nếu PowerShell chặn `npm.ps1`. Giữ báo cáo lịch sử nguyên trạng; phân biệt static inventory
với runtime verification.
