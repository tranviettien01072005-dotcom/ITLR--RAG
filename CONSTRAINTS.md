# Sàn chất lượng ITLR–RAG

Các ràng buộc sau là mức tối thiểu cho **ITLR–RAG | Intelligent IT Learning Platform**. Không hạ ngưỡng hoặc bỏ kiểm tra để đạt PASS. [AGENTS](AGENTS.md) quy định quy trình; [validation](reports/VALIDATION.md) cung cấp bằng chứng theo checkpoint.

## Kiểm thử và hồi quy

Baseline hiện hành: **445 Python PASS/0 skip**, **145 Web PASS**, coverage Python
statements khoảng **66,70%**, Web lines **46,55%**, theo
[release validation](reports/RELEASE_READINESS_FINAL.md). Đây là số đo local, không phải
coverage threshold đã được CI enforce. So sánh cùng phạm vi đo sau refactor; không
giảm coverage hoặc bỏ assertion để đạt PASS. Các checkpoint 256/260/414 bên dưới là lịch sử.

| Ràng buộc | Cách kiểm |
|---|---|
| Suite không có failure/error trước bàn giao | Chạy đầy đủ pytest và Web checks theo README |
| Giữ phạm vi test; không rút testpaths/addopts để bỏ ca lỗi | Review diff cấu hình và tests |
| Bug phải có regression tái hiện FAIL trước fix, PASS sau fix | Ghi lệnh và kết quả trong báo cáo liên quan |
| Không thêm skip/xfail để che lỗi | Kiểm tra diff; ngoại lệ lịch sử chỉ gồm thiếu artifacts integration hoặc thiếu thư viện nặng import-probe, phải nêu trong docstring |
| Không giảm năng lực kiểm chứng | Xóa test phải thay bằng test mạnh hơn cùng phạm vi; checkpoint baseline 256 tests/0 skip, sau đó 260/0 |

Artifacts integration đã có fixtures để chạy đủ suite ở checkpoint hiện tại. Ngoại lệ lịch sử không phải lý do thêm skip vào những ca đã có thể chạy. Không nới lint/type/coverage hoặc bỏ assertion để làm xanh kết quả.

## Lỗi và fallback phải quan sát được

Fallback có chủ đích, như LLM → template hoặc FAISS → brute-force, phải log WARNING/ERROR và giữ nhãn chế độ đúng. Cấm `except` nuốt lỗi mà không báo. `llm_client.chat/stream` raise `LLMError` khi hết retry; adapter log trước khi trả `None`/template. Regression gồm `test_try_llm_response_none_on_llmerror`.

`eval/eval_generation.py --llm` thiếu key phải fail-fast rc=2; không chạy template rồi ghi nhãn LLM. Pipeline/orchestrator phải trả mã khác 0 khi bước bắt buộc lỗi. Kết thúc SSE phải phân biệt lỗi với thành công; token provisional không phải câu trả lời đã kiểm tra.

## Bảo mật và ranh giới tin cậy

- Không có secret thật trong code/log/report. Khi cần ghi dấu hiệu key, dùng `llm_client.mask_key`; giữ `test_exhausted_retries_raise_llmerror_no_key_leak`.
- `.env` bị gitignore; chỉ `.env.example` với key rỗng được theo repo. Web yêu cầu JWT/admin/database credentials riêng trong mọi mode.
- Dữ liệu catalog, người dùng và LLM là dữ liệu không tin cậy. Giữ quy tắc chống prompt injection của SYSTEM_PROMPT và `test_system_prompt_has_injection_guard`.
- Validate input REST bằng Pydantic; không nối SQL/HTML từ input. Upload cần signature/access checks; không mô tả chúng như antivirus.
- `/admin/reload` phải fail-closed khi token trống/sai. Giữ một worker/replica khi limiter còn trong RAM; proxy trust phải tường minh.

## Đường dẫn, artifacts và tái lập

I/O artifacts/data đi qua `itlr.config` (`ARTIFACTS_DIR`, `DATA_DIR`); không hardcode đường `artifacts/` tương đối. Giữ regression `tests/test_ann.py` và `tests/test_eval_scripts_paths.py`. Dùng context manager khi pickle load/dump; cấm `pickle.load/dump(open(...))` trong engine, ANN và pipelines, theo `tests/test_pickle_handles.py`.

Qrels/eval dùng seed 20240623; interactions dùng seed 7. Mọi nguồn ngẫu nhiên cần seed ghi rõ. `scripts/build_all.py` giữ tính idempotent, chỉ rebuild khi `--force`; CLI versioned `scripts/build_all_v2.py` tạo staging mới, cần probe trước activate. Không suy ra hai builder có cùng cơ chế ghi.

`eval/run_all.py [--quick]` là entrypoint đánh giá và ghi các báo cáo thuộc pipeline; không cam kết tái sinh mọi file lịch sử trong `reports/`. Giữ dữ liệu nhãn và chia train/validation/test độc lập, không đổi qrels để nâng điểm.

## Tính trung thực của dữ liệu và kết luận

Mọi số liệu phải nêu loại nhãn: `rule-based (metadata)`, `synthetic (mô phỏng)`, `hand-curated` hoặc `human`. Retrieval qrels legacy là rule-based; CF/off-policy là synthetic seed 7; `--simulate-human` là mô phỏng. Không gọi dữ liệu mô phỏng là hành vi hoặc đánh giá người thật.

Groundedness/relevancy đo bằng luật phải gọi là proxy/xấp xỉ. Citation membership không phải semantic entailment; chỉ tiêu chưa đo phải `null`. README và báo cáo bàn giao phải ghi phần chưa kiểm chứng. Số liệu lịch sử giữ nguyên dataset, thời điểm và giới hạn; không dùng làm chứng cứ runtime mới.

## Ngưỡng đề xuất, chưa được enforce

| Chiều đo | Baseline / tình trạng | Mục tiêu cần xác lập bằng CI và môi trường đo |
|---|---|---|
| Search p95 | [Latency lịch sử](reports/latency.md), không phải SLO runtime | ≤1,5 s cho `/api/search` |
| Chat template p95 | Cùng báo cáo lịch sử | ≤2,0 s |
| Python coverage | 66,70% statements trên `itlr/`, gồm pipelines; khác phạm vi với mục tiêu bên phải | ≥60% trên `itlr/`, không tính pipelines build |
| Web line coverage | 46,48% ở checkpoint engineering hiện hành | Chưa chốt floor mới |
| Kích thước file | Chatbot 932 dòng, recommender 884 dòng sau extraction | File mới khoảng ≤800 dòng; tách theo trách nhiệm khi cần |

Đây là đề xuất, không phải ngưỡng đã đạt hoặc đã bật trong CI. Thay đổi sàn phải sửa tài liệu này, ghi lý do và bằng chứng; không áp dụng hồi tố để thông qua thay đổi đang review. Sàn mới cần ngưỡng và cách kiểm máy móc rõ ràng.
