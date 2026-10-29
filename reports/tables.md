# ITLR–RAG | Intelligent IT Learning Platform

## Retrieval ablation: clean queries

Historical record: 2026-10-27. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

The experiment macro-averaged 76 queries against metadata/rule-based semi-automatic labels in `data/eval/relevance_judgments.csv`, using the historical synthetic legacy catalog. Labels were not supplied by human assessors. See [noisy-query results](tables_kw_noisy.md) for a separate 78-query condition.

E5 has the highest reported NDCG@10, 0.2555. Cross-Encoder and L1 rows are identical; the Full configuration has lower accuracy and separate diversity statistics. The original prose claimed lexical saturation and a Cross-Encoder accuracy maximum, which the recorded table does not support. These claims are not used to interpret this run. The table alone does not prove that reranking executed or improved results. Human assessment through `evaluate_human.py` was proposed; simulated agreement is documented separately in [human_eval.md](human_eval.md).

### Ablation metrics

| Configuration | P@5 | R@5 | NDCG@10 | MAP | MRR | R@100 |
|---|---|---|---|---|---|---|
| TF-IDF only | 0.2237 | 0.0081 | 0.1985 | 0.0901 | 0.3078 | 0.1139 |
| BM25 only | 0.1974 | 0.0068 | 0.1835 | 0.1111 | 0.2702 | 0.1169 |
| Hybrid lexical (TF-IDF+BM25) | 0.2211 | 0.0082 | 0.2018 | 0.1145 | 0.3363 | 0.1250 |
| **Embeddings (E5)** | 0.2684 | 0.0102 | 0.2555 | 0.1546 | 0.4499 | 0.2097 |
| + L1 hybrid signals | 0.2289 | 0.0093 | 0.2168 | 0.1688 | 0.3291 | 0.2157 |
| + Cross-Encoder | 0.2289 | 0.0093 | 0.2168 | 0.1688 | 0.3291 | 0.2157 |
| + RAG-Fusion + MMR (Full) | 0.1579 | 0.0066 | 0.1428 | 0.1321 | 0.2557 | 0.1359 |

### E5 versus baselines: NDCG@10 differences

| Baseline | Baseline NDCG@10 | Embeddings (E5) − base | CI 95% | p (t-test) | p (bootstrap) | Significant? |
|---|---|---|---|---|---|---|
| TF-IDF only | 0.1985 | +0.0570 | [-0.0110, 0.1289] | 0.124 | 0.1022 | — |
| BM25 only | 0.1835 | +0.0720 | [-0.0008, 0.1460] | 0.06501 | 0.0528 | — |
| Hybrid lexical (TF-IDF+BM25) | 0.2018 | +0.0537 | [-0.0195, 0.1276] | 0.1645 | 0.1482 | — |
| + L1 hybrid signals | 0.2168 | +0.0388 | [-0.0099, 0.0896] | 0.1354 | 0.1194 | — |
| + Cross-Encoder | 0.2168 | +0.0388 | [-0.0099, 0.0896] | 0.1354 | 0.1194 | — |
| + RAG-Fusion + MMR (Full) | 0.1428 | +0.1127 | [0.0457, 0.1815] | 0.001782 | 0.0006 | ✅ p<0.05 |

### Full configuration: top-10 diversity and distribution

| Metric | Value |
|---|---|
| Coverage | 0.1108 |
| Gini | 0.9135 |
| ILD | 0.0982 |

Confidence intervals and t-test/bootstrap outputs retain the original run's precision. Statistical comparisons are conditional on this query set and rule-based labels; they are not human-rated quality or current-runtime evidence. No multiple-comparison correction is established by this record.
