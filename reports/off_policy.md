> **Ngữ cảnh đồ án — 2026-10-30:** Tài liệu lịch sử: giữ số đo, phạm vi và kế hoạch tại thời điểm ghi. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../README.md).

# Đánh giá off-policy / counterfactual (D)

*Mô phỏng bandit ngữ cảnh GROUNDED trên 5000 item thật; 6000 vòng; reward known-truth.*

## So sánh ước lượng vs giá trị THẬT

| Đại lượng | Giá trị | CI 95% | Phủ giá trị thật target? |
|---|---|---|---|
| **Giá trị thật — policy MỚI** | **0.5465** | — | (mốc) |
| Giá trị thật — policy CŨ | 0.4289 | — | — |
| Naive (CTR quan sát) | 0.4425 | — | lệch -0.1040 |
| IPS | 0.5703 | [0.5518, 0.5880] | không |
| SNIPS | 0.5585 | [0.5440, 0.5721] | có |
| DR | 0.5540 | [0.5400, 0.5673] | có |

- **Effective Sample Size** = 4686/6000 (ESS thấp -> trọng số lệch -> ưu tiên SNIPS/DR + clip).
- **Kết luận:** estimator off-policy ước lượng đúng giá trị policy MỚI **chỉ từ log của policy cũ**, trong khi naive lệch — đúng tinh thần đánh giá counterfactual chuẩn công nghiệp.

*Đây là MÔ PHỎNG để kiểm chứng tính không thiên lệch của estimator (vì cần biết ground-truth). Khi có log click thật từ web app, dùng `itlr/eval/off_policy.py` y nguyên.*