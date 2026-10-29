> **Ngữ cảnh đồ án — 2026-10-30:** Tài liệu lịch sử: giữ số đo, phạm vi và kế hoạch tại thời điểm ghi. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../README.md).

# Kết quả đánh giá — Bảng ablation per-stage (truy vấn sạch)

*Số truy vấn: 76. Metric macro-average trên nhãn bán-tự-động (`data/eval/relevance_judgments.csv`).*

> Lưu ý: nhãn tự động ≈ khớp topic chính xác nên các cấu hình từ vựng (TF-IDF/BM25) gần chạm trần — bảng sạch chủ yếu xác nhận **recall** của tầng sinh ứng viên. Khác biệt phương pháp thể hiện rõ ở bảng **truy vấn nhiễu** (`tables_kw_noisy.md`) và trên **nhãn người gán** (`evaluate_human.py`). Cấu hình **Full** thêm MMR -> đánh đổi một phần độ chính xác lấy **đa dạng** (xem mục beyond-accuracy); **+ Cross-Encoder** là mốc độ-chính-xác cao nhất.

## Bảng ablation (headline metrics)

| Cấu hình | P@5 | R@5 | NDCG@10 | MAP | MRR | R@100 |
|---|---|---|---|---|---|---|
| TF-IDF only | 0.2237 | 0.0081 | 0.1985 | 0.0901 | 0.3078 | 0.1139 |
| BM25 only | 0.1974 | 0.0068 | 0.1835 | 0.1111 | 0.2702 | 0.1169 |
| Hybrid lexical (TF-IDF+BM25) | 0.2211 | 0.0082 | 0.2018 | 0.1145 | 0.3363 | 0.1250 |
| **Embeddings (E5)** | 0.2684 | 0.0102 | 0.2555 | 0.1546 | 0.4499 | 0.2097 |
| + L1 hybrid signals | 0.2289 | 0.0093 | 0.2168 | 0.1688 | 0.3291 | 0.2157 |
| + Cross-Encoder | 0.2289 | 0.0093 | 0.2168 | 0.1688 | 0.3291 | 0.2157 |
| + RAG-Fusion + MMR (Full) | 0.1579 | 0.0066 | 0.1428 | 0.1321 | 0.2557 | 0.1359 |

## Kiểm định thống kê — **Embeddings (E5)** (tốt nhất) vs baseline (NDCG@10)

| Baseline | NDCG@10 (base) | Embeddings (E5) − base | CI 95% | p (t-test) | p (bootstrap) | Có ý nghĩa? |
|---|---|---|---|---|---|---|
| TF-IDF only | 0.1985 | +0.0570 | [-0.0110, 0.1289] | 0.124 | 0.1022 | — |
| BM25 only | 0.1835 | +0.0720 | [-0.0008, 0.1460] | 0.06501 | 0.0528 | — |
| Hybrid lexical (TF-IDF+BM25) | 0.2018 | +0.0537 | [-0.0195, 0.1276] | 0.1645 | 0.1482 | — |
| + L1 hybrid signals | 0.2168 | +0.0388 | [-0.0099, 0.0896] | 0.1354 | 0.1194 | — |
| + Cross-Encoder | 0.2168 | +0.0388 | [-0.0099, 0.0896] | 0.1354 | 0.1194 | — |
| + RAG-Fusion + MMR (Full) | 0.1428 | +0.1127 | [0.0457, 0.1815] | 0.001782 | 0.0006 | ✅ p<0.05 |

## Beyond-accuracy (cấu hình Full, top-10)

| Metric | Giá trị |
|---|---|
| Coverage | 0.1108 |
| Gini | 0.9135 |
| ILD | 0.0982 |
