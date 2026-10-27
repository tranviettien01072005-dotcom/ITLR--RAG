# Kết quả đánh giá — Bảng ablation per-stage (truy vấn NHIỄU (bỏ dấu + lỗi gõ))

*Số truy vấn: 78. Metric macro-average trên nhãn bán-tự-động (`data/eval/relevance_judgments.csv`).*

> Truy vấn bị **bỏ dấu + chèn lỗi gõ**, nhãn liên quan giữ nguyên. Bảng này đo **độ bền** của hệ trước input tiếng Việt đời thực: khớp từ vựng chính xác (TF-IDF/BM25) sụt mạnh, kênh ngữ nghĩa + char n-gram bỏ dấu giữ được chất lượng.

## Bảng ablation (headline metrics)

| Cấu hình | P@5 | R@5 | NDCG@10 | MAP | MRR | R@100 |
|---|---|---|---|---|---|---|
| TF-IDF only | 0.1308 | 0.0066 | 0.1370 | 0.1377 | 0.2280 | 0.1554 |
| BM25 only | 0.1974 | 0.0098 | 0.1801 | 0.1747 | 0.2885 | 0.1890 |
| Hybrid lexical (TF-IDF+BM25) | 0.1769 | 0.0087 | 0.1714 | 0.1687 | 0.2670 | 0.1795 |
| Embeddings (E5) | 0.5026 | 0.0234 | 0.4927 | 0.4281 | 0.6305 | 0.3371 |
| **+ L1 hybrid signals** | 0.6231 | 0.0296 | 0.5919 | 0.4500 | 0.7588 | 0.3558 |
| + Cross-Encoder | 0.6231 | 0.0296 | 0.5919 | 0.4500 | 0.7588 | 0.3558 |
| + RAG-Fusion + MMR (Full) | 0.3590 | 0.0177 | 0.3760 | 0.4957 | 0.6984 | 0.4821 |

## Kiểm định thống kê — **+ L1 hybrid signals** (tốt nhất) vs baseline (NDCG@10)

| Baseline | NDCG@10 (base) | + L1 hybrid signals − base | CI 95% | p (t-test) | p (bootstrap) | Có ý nghĩa? |
|---|---|---|---|---|---|---|
| TF-IDF only | 0.1370 | +0.4549 | [0.3740, 0.5357] | 3.409e-17 | 0 | ✅ p<0.05 |
| BM25 only | 0.1801 | +0.4119 | [0.3257, 0.4972] | 4.183e-14 | 0 | ✅ p<0.05 |
| Hybrid lexical (TF-IDF+BM25) | 0.1714 | +0.4205 | [0.3334, 0.5064] | 2.171e-14 | 0 | ✅ p<0.05 |
| Embeddings (E5) | 0.4927 | +0.0992 | [0.0416, 0.1596] | 0.001582 | 0.0004 | ✅ p<0.05 |
| + Cross-Encoder | 0.5919 | +0.0000 | [0.0000, 0.0000] | 1 | 1 | — |
| + RAG-Fusion + MMR (Full) | 0.3760 | +0.2159 | [0.1482, 0.2828] | 2.495e-08 | 0 | ✅ p<0.05 |

## Beyond-accuracy (cấu hình Full, top-10)

| Metric | Giá trị |
|---|---|
| Coverage | 0.1230 |
| Gini | 0.8987 |
| ILD | 0.0997 |
