# ADR-002: Tập trung đường dẫn dữ liệu và artifacts

## Status

Accepted. Historical decision; current runtime evidence is maintained in reports/VALIDATION.md.


Sản phẩm: **ITLR–RAG | Intelligent IT Learning Platform**. Accepted, 2026-10-27.
Hướng dẫn hiện hành: [README](../../README.md), [deployment](../../deploy/DEPLOY.md).

## Context

ANN từng dùng mặc định `artifacts/` tương đối với CWD. Một số script `eval/` tính root bằng
ba lần `dirname`, trỏ ra ngoài repository sau khi đổi layout. Engine có thể không tìm thấy
artifacts dù chúng tồn tại trong `var/artifacts/`; chạy từ thư mục khác làm lộ lỗi này.

## Decision

`itlr/config.py` quản lý `ROOT`, `ARTIFACTS_DIR`, `DATA_DIR`, `artifact()` và `data_file()`.
Mặc định là `ROOT/var/artifacts` và `ROOT/var/data`; environment là đầu vào của config,
bao gồm `ITLR_ARTIFACTS_DIR`, `ITLR_ITEMS_CSV`, `ITLR_INTERACTIONS_CSV`.

ANN nhận `artifacts_dir=None` rồi đọc config khi gọi, cho phép test thay đường dẫn.
Loader/builder dùng context manager khi mở pickle. Script evaluation xác định repo root từ
vị trí file, dùng layout `eval/` thay tham chiếu `scripts/eval/` đã hết hiệu lực.

## Alternatives

Truyền tay `--artifacts` qua mọi tầng dễ bỏ sót caller. Đọc environment riêng ở mỗi module
làm phân tán chính sách. Config tập trung hỗ trợ cả mặc định và môi trường cô lập.

## Consequences

Các entrypoint dùng cùng quy tắc đường dẫn, độc lập với CWD. Regression tại
`tests/test_ann.py` và `tests/test_eval_scripts_paths.py` kiểm tình huống chạy ngoài repo.
Đường dẫn version đang active và tương thích artifacts legacy được mở rộng trong
[ADR-007](ADR-007-artifact-versioning.md) và [ADR-010](ADR-010-shared-retrieval-and-atomic-state.md).
Quyết định này không cho phép loader nhận pickle từ nguồn không tin cậy.
