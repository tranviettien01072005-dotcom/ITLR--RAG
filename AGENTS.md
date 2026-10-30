# Hướng dẫn làm việc với ITLR–RAG

Cập nhật: 2026-10-30. Tên sản phẩm: **ITLR–RAG | Intelligent IT Learning Platform**. Phạm vi là nền tảng hỗ trợ học CNTT, gợi ý tài nguyên và chatbot RAG. Mô tả dựa trên khả năng có trong repository; không suy diễn trạng thái thương mại, giấy phép open-source hoặc production-ready. Không tự gán MIT; bảo toàn bản quyền và license bên thứ ba.

## Tiếp nhận và thực hiện công việc

1. Đọc file này, [memory](docs/PROJECT_MEMORY.md), báo cáo mới nhất và Git diff trước khi sửa. Phân biệt lịch sử với trạng thái hiện hành.
2. Kế thừa kết quả đã có; ghi trạng thái trong repo. Không yêu cầu hoặc tích hợp Claude-Mem.
3. Dùng Ponytail Ultra và skill phù hợp: thay đổi nhỏ nhất giải quyết đầy đủ yêu cầu. Bug phải có bằng chứng FAIL → fix → PASS; review diff sau mỗi nhóm.
4. Giữ thay đổi người dùng, runtime và database; không xóa dữ liệu, che lỗi, bỏ assertions hoặc hạ chất lượng tests để đạt PASS.
5. Không gọi API trả phí nếu chưa được phép. Khi thử local, unset `DEEPSEEK_API_KEY` và `OPENAI_API_KEY`.
6. Khi hành vi thay đổi, cập nhật README, memory, changelog và tài liệu liên quan; ghi riêng kết quả đã chạy, thử nghiệm và phần chưa kiểm chứng.
7. Không commit/push nếu yêu cầu hiện tại không bao gồm việc đó. Kế hoạch lịch sử ghi quyền publish không cấp lại quyền cho phiên mới.

## Ranh giới kiến trúc cần giữ

| Khu vực | Trách nhiệm và ràng buộc |
|---|---|
| `web/` | Giao diện chính Express + TypeScript + EJS + PostgreSQL, cổng 3000 |
| `itlr.api.server:app` | Backend cổng 8000; UI tĩnh chỉ là giao diện phụ |
| `itlr/retrieval/` | Shared service và BM25 cho artifacts có chunk vectors |
| `itlr/core/chunks.py` | FAISS chunk, RRF và passage reranking |
| `itlr/collect/`, `itlr/pipelines/` | Ingestion có robots/rate-limit/SQLite; build artifacts |
| `itlr/chatbot/llm_client.py` | Tầng generation LLM duy nhất: DeepSeek/OpenAI hoặc Ollama |
| `itlr/versioning.py`, `itlr/locking.py` | Staging, probe, atomic pointer/history, rollback, GC và khóa Linux local |

Artifacts cũ giữ đường V2. Không xóa hoặc di chuyển shim `itlr/core/bm25.py`: pickle cũ còn tham chiếu module này. `/admin/reload` yêu cầu `X-Admin-Token` khớp `ITLR_ADMIN_TOKEN`; chưa cấu hình phải 403. CF tùy chọn; thiếu model phải trả 503 tại personas/for-you và không làm hỏng retrieval.

Checkpoint hiện hành và blockers: [restructuring continuation](reports/RESTRUCTURING_CONTINUATION_2026-10-30.md). Baseline hiện tại 414 Python PASS/0 skip và 132 Web PASS; số lịch sử bên dưới không phải lần chạy mới.

## Kiểm chứng trước bàn giao

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  USE_OLLAMA=0 DISABLE_RERANKER=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv/bin/python -m pytest tests/ -o addopts='' -q -ra
.venv/bin/python -m compileall -q itlr scripts eval
cd web
npm run typecheck
npm run lint
npm run build
npm test
```

[Validation](reports/VALIDATION.md) ghi baseline 256 Python pass/0 skip, kết quả cuối checkpoint 260 Python pass/0 skip và 59 Web pass. Không trình bày số cũ như lần chạy mới. Nếu TestClient treo trong sandbox, kiểm tra ngoài sandbox theo quyền được cấp; không skip để làm xanh suite. Chỉ sửa tài liệu thì kiểm tra diff, nội dung, đường dẫn và links phù hợp; không chạy migration/build index để chứng minh một thay đổi văn bản.

## Dữ liệu và bảo mật

- Catalog legacy 5.000 items và interactions CF là synthetic; snapshot thật ở `data/curated_resources.jsonl`. `/health` chỉ cung cấp readiness/items/CF, chưa có loaded-version fingerprint; đối chiếu provenance riêng, không coi CURRENT.json là bằng chứng engine đã reload.
- Qrels metadata/rule-based, nhãn mô phỏng và chẩn đoán bằng luật không thay thế đánh giá độc lập của người dùng thật.
- Citation ID hợp lệ không chứng minh faithfulness. Chỉ tiêu chưa đo ghi `null`, không ghi 0% lỗi.
- Secret giữ trong môi trường hoặc file local bị gitignore; không in key, mật khẩu hay reset token vào log/report.
- Paths qua `itlr/config.py`; artifacts pickle chỉ từ builder tin cậy. Giữ SHA256 inventory; hash không xác nhận tác giả nếu attacker sửa được cả file và manifest.
- Rolling feed mặc định không được suy ra bài đã xóa vì vắng khỏi feed. `listing_is_complete` và `full_text_allowed` phải là JSON boolean.
- Một worker/replica mỗi service, local Linux filesystem. Không suy diễn khóa local/rate limiter RAM thành hỗ trợ nhiều host.

Tra cứu [README](README.md), [deployment](deploy/DEPLOY.md), [sàn chất lượng](CONSTRAINTS.md), [ADR-010](docs/decisions/ADR-010-shared-retrieval-and-atomic-state.md) và [V3 review](reports/V3_RESTRUCTURING_2026-10-30.md) trước thay đổi kiến trúc.

Windows verification: set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` before Python checks; use `npm.cmd` if PowerShell blocks npm.ps1. Latest scoped continuation: [stream hardening](reports/HARDENING_STREAM_2026-10-30.md).

Current structure/documentation verification: [restructuring continuation](reports/RESTRUCTURING_CONTINUATION_2026-10-30.md). Preserve historical reports; distinguish static import inventory from runtime verification.
