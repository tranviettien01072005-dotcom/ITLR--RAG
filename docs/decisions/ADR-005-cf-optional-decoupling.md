# ADR-005: Tách Collaborative Filtering thành tính năng tùy chọn (optional)

## Trạng thái
Accepted

## Ngày
2026-10-29

## Bối cảnh
CF (item-based co-occurrence) train từ `interactions.csv` — dữ liệu tương tác hiện có là
**giả lập** (`generate_interactions.py`, seed 7) vì không có dữ liệu người dùng thật. Tính năng
hỗ trợ này từng là bước bắt buộc trong `load_engine()`: thiếu `cf_model.pkl` ⇒ server không
khởi động được (lỗi FileNotFoundError) dù search/chatbot — phần lõi — hoàn toàn không cần CF.

Sàn dự án V2: trung thực dữ liệu; không dùng tương tác giả làm dữ liệu thật trong báo cáo;
API không được chết chỉ vì một tính năng phụ thiếu.

## Quyết định
- `RecommenderEngine.cf_model` cho phép **None**; `load_engine()` thiếu `cf_model.pkl` ⇒ log
  WARNING (không nuốt lặng lẽ), engine vẫn chạy.
- Endpoint CF (`/api/personas`, `/api/for-you`) khi không có CF: trả **503** kèm lời giải thích
  (`CFUnavailable`) — không 500, không trả danh sách rỗng để che giấu điều kiện thực tế.
- `/health` thể hiện trạng thái: `"cf": true|false` — giám sát thấy được.
- Build CF thành bước tùy chọn: `build_all_v2 --with-cf` (generate_interactions + build_cf);
  KHÔNG build nếu không có yêu cầu demo persona — dữ liệu tương tác vẫn là giả lập, chỉ dùng
  demo UI, rõ ràng nằm ngoài mọi báo cáo đánh giá chất lượng retrieval.
- Bảo vệ `/admin/reload` bằng token quản trị được chốt riêng ở ADR-008.

## Phương án đã cân nhắc
- **Giữ CF bắt buộc**: đơn giản nhưng server phụ thuộc dữ liệu giả — vi phạm nguyên tắc trung
  thực và SPOF vô nghĩa. Bị loại.
- **Thay CF bằng nơi giữ chỗ biến popularity-only** (không cần interactions.csv): che giấu điều
  kiện thực tế; popularity từ dữ liệu giả vẫn là giả. Bị loại — chọn phơi rõ trạng thái 503.
- **CF từ event thật của API (log click)**: đúng hương hướng nhưng chưa có luồng lưu event; để
  tương lai (cần bảng interactions thật + consent).

## Hệ quả
- Không có CF: search/, chatbot, evaluation retrieval hoạt động đủ; FE persona cần ẩn khi
  `/health` báo `cf:false`.
- Có CF: như cũ — `recommend_for_user`, personas 40 archetype.
- Tests: `tests/test_admin_security_cf.py` — unit (engine raise) + API (503 với fake engine,
  không cần artifacts build).
