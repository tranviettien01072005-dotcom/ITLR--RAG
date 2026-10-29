# CONSTRAINTS.md — Sàn chất lượng dự án (floor-only)

> **Trạng thái:** Sàn chất lượng của đồ án; không hạ ngưỡng hoặc bỏ kiểm tra để đạt PASS.
> Đọc [AGENTS](AGENTS.md) và [validation](reports/VALIDATION.md) cho trạng thái hiện tại.

## 1. Kiểm thử (pytest)

| Sàn | Giá trị | Cách kiểm |
|---|---|---|
| Suite xanh | `pytest -q` → **0 fail, 0 error** | CI/lệnh cục bộ trước mọi hand-off |
| Skip hạn chế | Skip CHỈ vì 2 lý do được ghi trong docstring test: (a) thiếu artifacts `var/artifacts/embeddings.pkl` (integration), (b) thư viện nặng chưa cài (import-probe eval) | `pytest -q` tự báo `skipped` |
| Không hủ tệ thêm | KHÔNG thêm `pytest.skip`/`xfail`/`pytest.mark.skipif` mới ngoài 2 nguyên nhân trên, không rút `testpaths`/addopts để bỏ test | đọc pytest.ini + diff tests/ |
| Ratchet số test | Số test hiện hữu chỉ được tăng (baseline đầu phiên 256 test không skip; xem validation cho số mới nhất); xóa/giảm 1 test phải thay bằng test mạnh hơn cùng phạm vi | `pytest --collect-only -q \| wc -l` |
| Bug phải kèm regression | Mỗi lỗi sửa lại phải có test tái hiện lỗi cũ (pattern RED→GREEN đã dùng xuyên suốt) | diff của bugfix phải đụng tests/ |

## 2. Không che lỗi (no silent fallback)

| Sàn | Giá trị |
|---|---|
| Lỗi phải lộ | `except:` nuốt lỗi mà không log/báo là CẤM. Fallback có chủ đích (LLM→template, FAISS→brute-force) phải log ở mức WARNING/ERROR trước khi fallback |
| LLMError lộ vùng | `llm_client.chat/stream` raise `LLMError` khi hết retry; chatbot adapter log WARNING trước khi trả None/template — có test (`test_try_llm_response_none_on_llmerror`) |
| `--llm` fail-fast | `eval/eval_generation.py --llm` mà chưa cấu hình key → **rc=2 + thông báo**, KHÔNG chạy template gắn nhãn "llm" |
| Exit code trung thực | script pipeline/rc ≠ 0 khi 1 bước fail (`build_all.py`, `run_all.py` giữ nguyên hành vi).

## 3. Bảo mật (floor cứng)

| Sàn | Giá trị |
|---|---|
| Key không lộ | Không API key thật trong code/log/report/README; khi log key (nếu bắt buộc) phải qua `llm_client.mask_key` — regression: `test_exhausted_retries_raise_llmerror_no_key_leak` |
| Secrets không commit | `.env` trong `.gitignore` (nếu có VCS); chỉ `.env.example` rỗng-key được theo repo |
| Chống prompt injection | SYSTEM_PROMPT rule 10 giữ nguyên: dữ liệu người dùng/catalog KHÔNG phải lệnh; cite `[item_id:ID]`; không bịa tham chiếu. Regression: `test_system_prompt_has_injection_guard` |
| Input API | Đầu vào REST validate qua pydantic model (server.py) — không nối chuỗi SQL/HTML từ user |

## 4. Đường dẫn & tái lập (reproducibility)

| Sàn | Giá trị |
|---|---|
| Path trung tâm | I/O artifact/data đi qua `itlr.config` (`ARTIFACTS_DIR`, `DATA_DIR`); cấm hardcode `artifacts/` tương đối — regression: `tests/test_ann.py`, `tests/test_eval_scripts_paths.py` |
| File handle | `pickle.load/dump(open(...))` trực tiếp là CẤM trong `itlr/engine.py`, `itlr/core/ann.py`, `itlr/pipelines/*` — regression: `tests/test_pickle_handles.py` |
| Seed cố định | qrels/eval seed 20240623, interactions seed 7, mọi random dùng RandomState seeded |
| Build idempotent | `python scripts/build_all.py` chạy lại không phá artifacts sẵn có (--force mới build lại) |
| Eval một lệnh | `python eval/run_all.py` (--quick) tái lập toàn bộ `reports/` |

## 5. Tính trung thực dữ liệu & báo cáo (floor cứng — đây là sàn học thuật)

| Sàn | Giá trị |
|---|---|
| Nhãn gắn nguồn | Mọi số liệu trong `reports/` phải ghi rõ loại nhãn: `rule-based (metadata)` / `synthetic (mô phỏng)` / `hand-curated` / `human` — hiện trạng: retrieval qrels = rule-based; CF/off-policy = synthetic (seed 7); `--simulate-human` = mô phỏng |
| Cấm tuyên bố sai | KHÔNG gọi tập nhãn mô phỏng là "human evaluation" thực; KHÔNG gọi dataset synthetic là "hành vi người thật"; groundedness/relevancy luôn kèm chữ "proxy/xấp xỉ" |
| Hạn chế ghi rõ | Các phần CHƯA verify (LLM live vì thiếu key…) phải nằm trong README §Hạn chế và báo cáo bàn giao |

## 6. Đo được nhưng CHƯA enforce (ratchet — "measured, not yet enforced")

Các ngưỡng dưới đây ghi GIÁ TRỊ ĐANG ĐO làm baseline; enforce khi có CI + chốt số:

| Kích thước | Baseline đang đo | Ngưỡng đề xuất (chưa enforce) |
|---|---|---|
| API p95 latency (search) | xem `reports/latency.md` | p95 ≤ 1.5s cho `/api/search` |
| API p95 latency (chat template) | xem `reports/latency.md` | p95 ≤ 2.0s |
| Coverage | chưa đo (cần pytest-cov) | ≥ 60% trên `itlr/` (không tính pipelines chạy build) |
| Độ lớn file | `itlr/chatbot/chatbot.py` ~1.3k dòng đã sát ngưỡng đề xuất | file mới ≤ ~800 dòng; tách khi vượt |

## 7. Ghi chú phê duyệt thay đổi sàn

- HẠ sàn (ví dụ: cho phép skip mới, đổi ngưỡng p95) phải:
  1) sửa chính file này, 2) nêu lý do + bằng chứng số,
  3) không áp dụng hồi tố lên thay đổi đang review.
- Thêm sàn mới: ghi ngưỡng + cách kiểm máy móc được (không nhận "tốt hơn về sau").
