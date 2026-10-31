# Sàn chất lượng ITLR–RAG

Đây là mức tối thiểu để bàn giao; **không hạ ngưỡng, không bỏ kiểm tra, không che lỗi** để
đạt PASS. Quy trình làm việc: [AGENTS](AGENTS.md). Cách chạy: [TESTING](docs/TESTING.md).
Metric và giới hạn: [EVALUATION](docs/EVALUATION.md). Bảo mật: [SECURITY](docs/SECURITY.md).

## 1. Kiểm thử và hồi quy

Mốc hiện hành (local, Linux, commit `f14c428`, không thay đổi code runtime): **510 Python PASS/0 skip**, coverage
statements **68,27%**; **166 Web PASS**, lines **52,41%**. Đây là số đo, không phải threshold
CI enforce; so sánh cùng phạm vi đo sau thay đổi.

| Ràng buộc | Cách kiểm |
|---|---|
| Suite không có failure/error trước bàn giao | chạy đầy đủ pytest + Web checks |
| Giữ phạm vi test; không rút `testpaths`/`addopts` để bỏ ca lỗi | review diff cấu hình/test |
| Bug phải có regression tái hiện FAIL trước fix, PASS sau fix | ghi lệnh + kết quả |
| Không thêm skip/xfail để che lỗi | review diff; ngoại lệ lịch sử phải nêu trong docstring |
| Không xóa test mà không thay bằng test mạnh hơn cùng phạm vi | review diff |
| Không giảm coverage/lint/type để xanh | review diff + log |

Checkpoint cũ (256/260/387/414/457/489) là lịch sử; không trình bày như lần chạy mới.
**Verdict hiện hành: NO-GO production** — SLO 45s FAIL trên CPU hiện tại và human
faithfulness `null`; xem [certification](reports/FINAL_E2E_CERTIFICATION.md).

## 2. Lỗi và fallback phải quan sát được

- Fallback có chủ đích (LLM → template, FAISS → brute-force) phải log WARNING/ERROR và giữ
  đúng nhãn mode. Cấm `except` nuốt lỗi không báo.
- `llm_client.chat/stream` raise `LLMError` khi hết retry; adapter log trước khi trả
  `None`/template. Giữ regression `test_try_llm_response_none_on_llmerror`.
- `eval/eval_generation.py --llm` thiếu key phải fail-fast rc=2; không chạy template rồi ghi
  nhãn LLM. Pipeline/orchestrator trả mã khác 0 khi bước bắt buộc lỗi.
- SSE phải phân biệt lỗi với thành công; provisional không phải câu trả lời đã kiểm; `done`
  không chứng minh thành công. Web chỉ lưu final khi đủ `final` + `done` + EOF sạch.
- Client disconnect phải đóng upstream; request bị hủy không lưu partial response.

## 3. Bảo mật và trust boundary

- Không có secret thật trong code/log/report. Khi cần dấu hiệu key, dùng
  `llm_client.mask_key`; giữ `test_exhausted_retries_raise_llmerror_no_key_leak`.
- `.env` bị gitignore; chỉ `.env.example` với key rỗng được theo repo. Web yêu cầu JWT/admin/
  database credentials riêng trong mọi mode.
- Catalog, nội dung người dùng và output LLM là dữ liệu không tin cậy. Giữ quy tắc chống
  prompt injection của SYSTEM_PROMPT và `test_system_prompt_has_injection_guard`.
- Validate REST bằng Pydantic; không nối SQL/HTML từ input. Upload cần kiểm chữ ký/quyền;
  mô tả đúng là kiểm định dạng, không phải antivirus.
- `/admin/reload` fail-closed khi token trống/sai. Một worker/replica khi limiter còn trong
  RAM; proxy trust phải tường minh.

## 4. Đường dẫn, artifacts và tái lập

- I/O artifacts/data đi qua `itlr.config` (`ARTIFACTS_DIR`, `DATA_DIR`); không hardcode path
  tương đối. Giữ `tests/test_ann.py`, `tests/test_eval_scripts_paths.py`.
- Dùng context manager khi pickle load/dump; cấm `pickle.load/dump(open(...))` trong engine,
  ANN và pipelines (`tests/test_pickle_handles.py`).
- Qrels/eval dùng seed `20240623`; interactions dùng seed `7`. Mọi nguồn ngẫu nhiên phải ghi
  seed.
- `scripts/build_all.py` idempotent, chỉ rebuild khi `--force`; `scripts/build_all_v2.py` tạo
  staging mới, phải probe trước activate. Không suy ra hai builder cùng cơ chế ghi.
- `eval/run_all.py [--quick]` là entrypoint đánh giá; chỉ chạy có chủ đích. Giữ train/
  validation/test độc lập, không đổi qrels để nâng điểm.
- Không rebuild artifacts đang phục vụ; không activation/migration production khi chưa được
  phê duyệt.

## 5. Tính trung thực của dữ liệu và kết luận

- Mọi số liệu phải nêu loại nhãn: `rule-based (metadata)`, `synthetic`, `hand-curated`,
  `AI-drafted` hoặc `human`. CF/off-policy là synthetic; `--simulate-human` là mô phỏng.
- Groundedness/relevancy đo bằng luật phải gọi là proxy. Citation membership/verbatim không
  phải entailment. Chỉ tiêu chưa đo ghi `null`, không ghi 0%.
- README/báo cáo phải ghi phần chưa kiểm chứng; không gọi staging PASS là production-ready,
  không bịa benchmark/SLA/scalability/human evaluation.
- Số liệu lịch sử giữ nguyên dataset, thời điểm và giới hạn; ghi rõ khi không phải lần chạy mới.
- Evidence mới vào `reports/final-e2e-evidence/` kèm SHA256; không sửa log/hash/báo cáo cũ.

## 6. Ngưỡng đề xuất (chưa enforce)

| Chiều đo | Hiện trạng | Mục tiêu cần xác lập |
|---|---|---|
| Search p95 | báo cáo latency lịch sử, không phải SLO runtime | ≤1,5s cho `/api/search` |
| Chat template p95 | cùng nguồn | ≤2,0s |
| Chat LLM p95 | **SLO 45s; FAIL trên CPU hiện tại** | đạt trên hardware mới + cold/warm |
| Python coverage | 67,63% statements trên `itlr/` (gồm pipelines) | ≥60% trên `itlr/` không tính pipelines |
| Web line coverage | 52,41% | chưa chốt floor |
| Kích thước file | chatbot 991 dòng, recommender 884 dòng | file mới ~≤800 dòng |

Đây là đề xuất, không phải ngưỡng đã đạt. Thay đổi sàn phải sửa tài liệu này, ghi lý do và
bằng chứng; không áp dụng hồi tố để thông qua thay đổi đang review.
