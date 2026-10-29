# ITLR–RAG | Intelligent IT Learning Platform

## CPU retrieval latency and memory

Historical record: 2026-10-27. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

The historical benchmark used 12 queries × 30 repetitions, one CPU thread and `time.perf_counter()`. QPS describes this sequential run rather than concurrent service capacity. Generation was outside the measurements.

### Retrieval stages

| Component | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | QPS (1 luồng) |
|---|---|---|---|---|---|
| Stage0 Candidate Gen (embedding+ANN) | 71.37 | 84.66 | 132.85 | 73.15 | 13.7 |
| Stage1 L1 ranking | 119.47 | 156.66 | 171.14 | 123.01 | 8.1 |
| Stage2 L2 rerank (cross-encoder, pool=48) | 6180.34 | 8347.35 | 11321.09 | 6032.72 | 0.2 |
| Stage3 MMR reorder | 1.09 | 1.43 | 1.85 | 1.12 | 890.1 |
| Full (no rerank) | 178.05 | 195.44 | 221.95 | 179.97 | 5.6 |

### FAISS versus brute-force candidate search

| Component | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | QPS (1 luồng) |
|---|---|---|---|---|---|
| FAISS ANN | 48.90 | 53.16 | 70.30 | 49.84 | 20.1 |
| Brute-force (matmul) | 147.94 | 194.68 | 224.36 | 150.46 | 6.6 |

Mean timings imply approximately 3.02× for the FAISS/brute-force comparison (49.84ms versus 150.46ms). Cross-encoder pool=48 is the dominant measured stage, with p50 6180.34ms and p95 8347.35ms. No sublinear scaling or million-item performance was measured.

The original narrative cited a 5k×384 problem and approximately 200ms query encoding, while the artifact table below gives `(5000, 768)` and the stage table reports different end-to-end timings. It also described a 3.02× difference as near parity. These are unresolved historical reporting inconsistencies; the tables are preserved without combining the incompatible descriptions into a new benchmark claim.

### Artifact memory and disk footprint

| Component | MB | Shape |
|---|---|---|
| embeddings (float32) | 15.4 | (5000, 768) |
| char n-gram matrix (sparse) | 11.2 | (5000, 4405) |
| ann_index.faiss (on disk) | 15.4 |  |
| retrieval_model.pkl (on disk) | 21.3 |  |
| embeddings.pkl (on disk) | 15.4 |  |

Proposed optimizations were float32→int8 embedding quantization (approximately 4× storage reduction), common-query caching and batched encoding. They were proposals, without measured quality, latency or process-RAM results in this record. Later hardware, model or catalog changes require a new comparable run.
