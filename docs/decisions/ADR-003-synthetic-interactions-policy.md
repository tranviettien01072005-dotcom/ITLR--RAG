> **Ngữ cảnh đồ án — 2026-10-30:** Quyết định kiến trúc theo thời điểm. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../../README.md).

# ADR-003: Interactions cho CF là dữ liệu MÔ PHỎNG (latent-persona, seed=7) kèm chính sách ghi nhãn trung thực

## Trạng thái
Accepted

## Ngày
2026-10-27

## Bối cảnh
CF item-item cosine cần ma trận tương tác user×item dày đủ (≥5 item/user). Repo chỉ có bản cũ
500 users / 12.342 clicks (đã backup `var/data/interactions_backup_500users.csv`). Không có nguồn
data người thật — dùng data thu thập không có sự đồng ý là không khả thi trong phạm vi bài toán.
Vấn đề: nếu mô phỏng "trắng" (chọn ngẫu nhiên đều), CF chỉ học phổ biến → mọi con số eval CF
(Off-policy, HitRate) vô nghĩa nhưng trông vẫn đẹp.

## Quyết định
`itlr/pipelines/generate_interactions.py` sinh **1.800 users, seed=7** với cấu trúc latent:
- Mỗi user 1–3 "persona" (chuyên mục ưa thích, sampling theo tần suất chuyên mục catalog).
- ~80% click nằm trong persona (còn lại khám phá, cap EXPLORATION_CAP=1/user).
- Số click/user ~ gamma quanh 25 (P90≈46); chọn item trong pool theo power-law phổ biến.
- MIN_HISTORY=5 — lọc sau khi sinh.

**Chính sách trung thực (ràng buộc học thuật, xem CONSTRAINTS.md §5):**
- Dataset này KHÔNG phải hành vi người thật; mọi report phải gắn nhãn `synthetic (mô phỏng, seed=7)`.
- Off-policy eval coi click là reward đã biết trước — khung demo phương pháp, không phải số ship.
- Khi có data thật chỉ cần thay `var/data/interactions.csv` (env `ITLR_INTERACTIONS_CSV`) rồi
  `python scripts/build_all.py --force --step collaborative` — schema chỉ cần `(user_id, item_id)`.

## Phương án đã cân nhắc
- **Chưa xây CF đến khi có data thật**: hủy luôn trang "Dành cho bạn" — trái yêu cầu e2e — bị loại.
- **Mô phỏng ngẫu nhiên đều**: CF thành bảng xếp hạng phổ biến trá hình — bị loại vì eval ảo.
- **Score giả lập (rating 1–5.pred)**: build_cf chỉ hiểu binary click; thêm thang rating là sửa
  mô hình mà không có bằng chứng — bị loại.

## Hệ quả
- Tái lập được tuyệt đối (seed 7, deterministic): cùng seed → cùng CSV.
- Latent_structure bị chặn hồi quy: `tests/test_generate_interactions.py` so share top-1 chuyên
  mục với baseline xáo trộn (phải ≥ baseline+0.15).
- Con số CF trong reports hợp lệ **chi trong thế giới mô phỏng**; không suy rộng ra người dùng thật.
