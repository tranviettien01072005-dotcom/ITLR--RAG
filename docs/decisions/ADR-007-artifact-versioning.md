# ADR-007: Staging, probe, activate và rollback artifacts

## Status

Accepted. Historical decision; current runtime evidence is maintained in reports/VALIDATION.md.


Sản phẩm: **ITLR–RAG | Intelligent IT Learning Platform**. Accepted, 2026-10-29;
độ bền pointer/history được mở rộng bởi [ADR-010](ADR-010-shared-retrieval-and-atomic-state.md).
Vận hành hiện hành: [deployment](../../deploy/DEPLOY.md).

## Context

Ghi đè artifacts đang phục vụ có thể để lại file thiếu, dimension sai hoặc dữ liệu không hợp lệ.
Cần kiểm phiên bản mới trước activation, giữ bản trước để rollback và tương thích layout legacy.

## Decision

`itlr/versioning.py` quản lý `var/artifacts/`:

```text
CURRENT.json                       # version, dir và (từ ADR-010) transition history
CURRENT.json.history.json          # mirror tương thích; history giới hạn 200 entries
versions/<version-id>/             # artifacts và MANIFEST.json
```

Builder ghi vào version staging riêng. Probe của `itlr/indexv2.py` gồm:

1. Kiểm file bắt buộc, số hàng items/embeddings/char matrix, dimension, NaN/Inf,
   L2 norm≈1, item IDs unique và khóa của retrieval model.
2. Self-retrieval TF-IDF: ngưỡng top-5 ít nhất 80%, tối đa 30 mẫu với seed cố định,
   điều chỉnh theo kích thước catalog.
3. Engine thật trong subprocess với `ITLR_ARTIFACTS_DIR` trỏ staging; truy vấn thành công
   và rc=0 mới qua. Lưu `probe: ok|fail` cùng chi tiết vào manifest.

Chỉ activate phiên bản probe thành công. `config.current_dir()` đọc pointer mỗi lần gọi;
không có pointer thì giữ đường legacy ở root artifacts. Rollback ghi pointer về phiên bản
hợp lệ trước đó; reload/restart nạp lại. GC mặc định `keep=3`, giữ active, mục tiêu rollback
và staging đang được bảo vệ. Khóa Linux local tuần tự hóa writers; không hỗ trợ nhiều host.

## Alternatives

Ghi đè rồi backup vẫn có cửa sổ đọc file dở dang. Symlink đơn giản nhưng JSON cho trạng thái
và lịch sử dễ kiểm tra. Cơ chế version không đòi database hoặc hai index phục vụ đồng thời;
reload hiện nạp candidate trước khi thay engine theo các kiểm tra tiếp nối.

## Consequences

Probe thất bại ngăn activation và giữ pointer trước đó; không chứng minh phiên bản đã đủ chất
lượng cho mọi truy vấn. Manifest có SHA256 inventory theo [ADR-009](ADR-009-security-runtime-boundaries.md),
không xác nhận tác giả nếu attacker sửa cả manifest và file. Chỉ nạp pickle từ builder tin cậy.

Pointer ghi qua temp + replace; fsync và embedded history theo ADR-010 giảm cửa sổ mất lịch sử.
Không xóa pointer như một thao tác reset thông thường: việc đó chuyển sang layout legacy và
có thể thay dữ liệu được nạp. Dung lượng tăng theo số versions giữ lại. Các bảo đảm áp dụng
filesystem Linux local, một replica/service; không suy rộng sang distributed storage.
