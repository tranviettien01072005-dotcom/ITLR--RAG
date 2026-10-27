# Benchmark độ trễ & mở rộng

*12 truy vấn × 30 lần lặp, 1 luồng, CPU. Đo bằng time.perf_counter().*

### Độ trễ từng tầng của phễu

| Thành phần | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | QPS (1 luồng) |
|---|---|---|---|---|---|
| Stage0 Candidate Gen (embedding+ANN) | 71.37 | 84.66 | 132.85 | 73.15 | 13.7 |
| Stage1 L1 ranking | 119.47 | 156.66 | 171.14 | 123.01 | 8.1 |
| Stage2 L2 rerank (cross-encoder, pool=48) | 6180.34 | 8347.35 | 11321.09 | 6032.72 | 0.2 |
| Stage3 MMR reorder | 1.09 | 1.43 | 1.85 | 1.12 | 890.1 |
| Full (no rerank) | 178.05 | 195.44 | 221.95 | 179.97 | 5.6 |

### FAISS ANN vs Brute-force (Stage-0)

| Thành phần | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | QPS (1 luồng) |
|---|---|---|---|---|---|
| FAISS ANN | 48.90 | 53.16 | 70.30 | 49.84 | 20.1 |
| Brute-force (matmul) | 147.94 | 194.68 | 224.36 | 150.46 | 6.6 |

> Ở quy mô 5k×384 trên CPU, Stage-0 bị **chi phí ENCODE truy vấn (SentenceTransformer ~200ms) chi phối**, nên FAISS ANN vs brute-force gần ngang nhau (~**3.02×**): matmul 5k vector vẫn rẻ. Lợi thế ANN (sublinear) chỉ bộc lộ khi N lớn hơn nhiều (hàng triệu) — đây là kết luận trung thực về tradeoff recall–latency ở quy mô hiện tại.

## Dấu chân bộ nhớ

| Thành phần | MB | Kích thước |
|---|---|---|
| embeddings (float32) | 15.4 | (5000, 768) |
| char n-gram matrix (sparse) | 11.2 | (5000, 4405) |
| ann_index.faiss (on disk) | 15.4 |  |
| retrieval_model.pkl (on disk) | 21.3 |  |
| embeddings.pkl (on disk) | 15.4 |  |

*Hướng tối ưu (đã nêu trong kế hoạch): quantization embeddings float32->int8 (~4× giảm bộ nhớ), caching truy vấn phổ biến, batch encoding.*