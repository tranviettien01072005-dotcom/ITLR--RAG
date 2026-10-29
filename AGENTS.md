# Hướng dẫn làm việc với ITLR–RAG

Cập nhật: 2026-10-30. Đây là đồ án sinh viên về gợi ý tài nguyên học CNTT và chatbot RAG.
Không mô tả đồ án là sản phẩm thương mại, open-source hoặc production-ready khi chưa có căn cứ.
Không tự gán giấy phép MIT; giữ nguyên thông báo bản quyền và giấy phép của nguồn bên thứ ba.

## Quy trình

1. Đọc file này, [trạng thái dự án](docs/PROJECT_MEMORY.md), báo cáo mới nhất và Git diff.
2. Kế thừa kết quả cũ. Không tích hợp hoặc yêu cầu Claude-Mem; ghi trạng thái trong repo.
3. Dùng Ponytail Ultra và skill phù hợp. Bug phải có FAIL → fix → PASS; review diff sau mỗi nhóm.
4. Không ghi đè thay đổi người dùng, xóa runtime/database, che lỗi hoặc hạ chất lượng tests.
5. Không gọi API trả phí khi chưa được phép. Khi thử local, unset key DeepSeek/OpenAI.
6. Cập nhật README, memory, changelog và tài liệu liên quan khi hành vi thay đổi.
7. Không push/commit nếu yêu cầu hiện tại không bao gồm việc đó.

## Kiến trúc hiện tại

- Giao diện chính: `web/`, Express + TypeScript + EJS + PostgreSQL, cổng 3000.
- Backend: `itlr.api.server:app`, cổng 8000; UI tĩnh tại đây chỉ là giao diện phụ.
- `itlr/retrieval/`: service dùng chung và BM25; `itlr/core/chunks.py`: FAISS chunk + RRF + reranking.
- `itlr/collect/`: ingestion, robots, rate-limit, SQLite; `itlr/pipelines/`: build artifacts.
- `itlr/chatbot/llm_client.py`: tầng LLM duy nhất; DeepSeek/OpenAI hoặc Ollama local.
- `itlr/versioning.py`: staging, probe, atomic pointer/history, rollback, GC; `itlr/locking.py`: khóa Linux local.
- Chunk artifacts mới dùng service chung. Artifacts cũ vẫn dùng đường V2. Không di chuyển/xóa pickle shim `itlr/core/bm25.py`.
- `/admin/reload` cần `X-Admin-Token` khớp `ITLR_ADMIN_TOKEN`; chưa cấu hình phải 403.
- CF tùy chọn; thiếu model trả 503 ở personas/for-you, không làm hỏng retrieval.

## Kiểm chứng

```bash
USE_OLLAMA=0 DISABLE_RERANKER=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest tests/ -o addopts='' -q -ra
.venv/bin/python -m compileall -q itlr scripts eval
cd web
npm run typecheck
npm run lint
npm run build
npm test
```

Baseline kiểm chứng lại đầu phiên: 256 Python pass/0 skip, 59 Web pass ở checkpoint trước.
Kết quả cuối phiên:260 Python pass/0 skip,59 Web pass. Số đo và giới hạn đọc trong [validation](reports/VALIDATION.md).
Nếu TestClient treo trong sandbox, kiểm tra ngoài sandbox theo quyền được cấp; không skip để đạt PASS.

## Quy tắc dữ liệu và bảo mật

- 5.000 catalog legacy và interactions CF là synthetic. Snapshot tài liệu thật nằm ở `data/curated_resources.jsonl`.
- Không dùng số item lịch sử làm số item runtime; đọc `/health` và provenance của version thực tế.
- Qrels metadata/rule-based và nhãn mô phỏng không phải đánh giá người dùng thật.
- Citation ID hợp lệ không chứng minh faithfulness. Metric chưa đo ghi null, không ghi 0% lỗi.
- Giữ bí mật trong môi trường hoặc file local bị gitignore; không log/report key hoặc mật khẩu.
- Paths qua `itlr/config.py`; không unpickle artifacts không đáng tin. Giữ inventory SHA256.
- Crawler rolling feed mặc định không được suy luận bài đã xóa chỉ vì vắng khỏi feed.
- Một worker mỗi service, local Linux filesystem; không tự quảng bá hỗ trợ distributed deployment.

## Tài liệu cần biết

[README](README.md) · [Deployment](deploy/DEPLOY.md) · [Sàn chất lượng](CONSTRAINTS.md) ·
[ADR-010](docs/decisions/ADR-010-shared-retrieval-and-atomic-state.md) · [V3 review](reports/V3_RESTRUCTURING_2026-10-30.md).
