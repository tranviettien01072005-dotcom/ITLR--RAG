# ADR-003: Provenance của tương tác CF mô phỏng

Sản phẩm: **ITLR–RAG | Intelligent IT Learning Platform**. Accepted, 2026-10-27.
Chính sách dữ liệu hiện hành: [CONSTRAINTS](../../CONSTRAINTS.md), [data](../../data/README.md).

## Bối cảnh

CF item-item cần lịch sử đủ dày nhưng repository chưa có hành vi người dùng thật được
thu thập có sự đồng ý. Snapshot ban đầu có 500 users / 12.342 clicks, được lưu ở
`var/data/interactions_backup_500users.csv`. Lấy mẫu ngẫu nhiên đều không tạo cấu trúc
cộng tác hữu ích để kiểm thử mô hình.

## Quyết định

`itlr/pipelines/generate_interactions.py` sinh **1.800 users, seed=7** với latent personas:
1–3 chuyên mục ưa thích/user, khoảng 80% click trong persona, phần còn lại khám phá với
`EXPLORATION_CAP=1/user`. Số click theo phân phối gamma quanh 25, P90≈46; item được chọn theo
power-law popularity. Lọc lịch sử với `MIN_HISTORY=5` sau khi sinh.

Mọi báo cáo phải ghi **synthetic / mô phỏng, seed=7**. Click và reward off-policy được tạo
trong môi trường mô phỏng; kết quả không chứng minh hiệu quả đối với người dùng thật.
Không nhập dữ liệu cá nhân vào tập này hoặc trình bày nó như dữ liệu vận hành.

## Phương án đã cân nhắc

Hoãn CF sẽ bỏ khả năng thử luồng “Dành cho bạn”. Random-uniform không kiểm được tín hiệu
persona; rating giả 1–5 không phù hợp schema binary-click hiện có. Chọn bộ tương tác
có cấu trúc, công khai nguồn nhãn và tách CF khỏi retrieval.

## Hệ quả

Seed cố định hỗ trợ tái lập. `tests/test_generate_interactions.py` so share chuyên mục top-1
với baseline xáo trộn, yêu cầu cao hơn ít nhất 0.15. Kiểm tra này xác nhận cấu trúc mô phỏng,
không xác nhận hành vi thật.

Dữ liệu thật sau này cần consent và provenance phù hợp, schema `(user_id, item_id)`, cấu hình
`ITLR_INTERACTIONS_CSV` rồi rebuild collaborative. Không ghi đè dữ liệu runtime khi chỉ sửa tài liệu.
CF là tùy chọn theo [ADR-005](ADR-005-cf-optional-decoupling.md).
