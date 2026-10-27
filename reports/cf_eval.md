# Đánh giá Collaborative Filtering (B6)

*Số user đánh giá: 800 (leave-one-out), 800 (temporal split).*

## Leave-one-out — CF vs Popularity baseline

| Metric | CF item-based | Popularity baseline |
|---|---|---|
| HitRate@1 | 0.2200 | 0.0037 |
| HitRate@5 | 0.3825 | 0.0112 |
| HitRate@10 | 0.4863 | 0.0288 |
| MRR | 0.2903 | 0.0081 |

## Temporal split (train quá khứ → test tương lai)

| Metric | KHÔNG rò rỉ (train lại) | Có rò rỉ (tham khảo) |
|---|---|---|
| Recall@1 | 0.0000 | 0.0023 |
| Recall@5 | 0.0001 | 0.0130 |
| Recall@10 | 0.0041 | 0.0425 |
| NDCG@10 | 0.0023 | 0.0442 |
| MAP | 0.0006 | 0.0136 |

*Cột **KHÔNG rò rỉ** train lại item_sim CHỈ trên phần quá khứ của mọi user (held-out không tham gia đồng-xuất-hiện) — đây là con số đáng tin để báo cáo. Cột có rò rỉ dùng cf_model train trên TOÀN bộ tương tác nên lạc quan quá mức.*

*Lưu ý: interactions.csv không có timestamp -> temporal split dùng thứ tự dòng làm proxy thời gian (đã nêu giả định trong itlr/eval/cf_eval.py). Leave-one-out ở trên dùng cf_model gốc nên CŨNG có rò rỉ — diễn giải thận trọng, ưu tiên cột không rò rỉ.*