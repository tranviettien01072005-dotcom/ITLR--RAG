# ITLR–RAG | Intelligent IT Learning Platform

## Collaborative filtering evaluation (B6)

Historical record: 2026-10-27. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

The legacy experiment used synthetic interactions, including the historical 1,800-user generation described in project memory. Each reported evaluation used 800 users: 800 leave-one-out and 800 temporal-split users. These are offline recommendation measurements, without real-user effectiveness evidence.

### Leave-one-out: item-based CF versus popularity

| Metric | CF item-based | Popularity baseline |
|---|---|---|
| HitRate@1 | 0.2200 | 0.0037 |
| HitRate@5 | 0.3825 | 0.0112 |
| HitRate@10 | 0.4863 | 0.0288 |
| MRR | 0.2903 | 0.0081 |

### Temporal split: past training, future holdout

| Metric | Retrained, no holdout leakage | All-data model, leaking reference |
|---|---|---|
| Recall@1 | 0.0000 | 0.0023 |
| Recall@5 | 0.0001 | 0.0130 |
| Recall@10 | 0.0041 | 0.0425 |
| NDCG@10 | 0.0023 | 0.0442 |
| MAP | 0.0006 | 0.0136 |

The non-leaking column retrains item similarity only on every user's past partition; held-out interactions do not enter co-occurrence. It is the preferred result for reporting. The leaking column uses a model trained on all interactions and is optimistically biased. Leave-one-out also used the original CF model and therefore contains leakage.

`interactions.csv` has no timestamps. Row order is a proxy for time, as assumed in `itlr/eval/cf_eval.py`; this limits interpretation of the temporal split. Synthetic interactions and proxy time cannot establish future behavior of actual learners.
