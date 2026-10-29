# ADR-005: Collaborative Filtering là tính năng tùy chọn

Sản phẩm: **ITLR–RAG | Intelligent IT Learning Platform**. Accepted, 2026-10-29.
Hợp đồng hiện hành: [README](../../README.md), [ADR-003](ADR-003-synthetic-interactions-policy.md).

## Bối cảnh

`load_engine()` từng bắt buộc `cf_model.pkl`, làm search/chat không khởi động khi thiếu
model phụ trợ. Tương tác CF hiện có là mô phỏng seed 7; retrieval không phụ thuộc dữ liệu này.

## Quyết định

`RecommenderEngine.cf_model` có thể là `None`. Thiếu model phải ghi WARNING và giữ retrieval
hoạt động. `/api/personas` và `/api/for-you` trả **503** với `CFUnavailable`, không che điều kiện
bằng danh sách rỗng. `/health` công khai trạng thái `cf: true|false`.

Build V2 chỉ thêm CF khi chọn `--with-cf`; dữ liệu mô phỏng dùng thử luồng persona được ghi nhãn
riêng và không đi vào kết luận chất lượng retrieval. Bảo vệ reload theo
[ADR-008](ADR-008-admin-token.md).

## Phương án đã cân nhắc

Giữ CF bắt buộc tạo dependency khởi động không cần thiết. Dùng popularity thay thế âm thầm
che mất trạng thái model; popularity từ dữ liệu giả vẫn không phải tín hiệu thật. Thu thập
click thật là hướng riêng, cần luồng lưu event và consent.

## Hệ quả

Search, chatbot và retrieval evaluation có thể chạy khi CF thiếu. UI cần thể hiện trạng thái
không khả dụng từ health/503. Khi có model, `recommend_for_user` và 40 persona archetype giữ
hành vi tương thích. `tests/test_admin_security_cf.py` kiểm engine và API bằng fixtures,
không cần build artifacts runtime; kiểm thử này không đo hiệu quả cá nhân hóa thực tế.
