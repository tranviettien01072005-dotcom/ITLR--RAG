# ITLR–RAG | Intelligent IT Learning Platform

## Off-topic relevance gate calibration

Historical record: 2026-10-27. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

The gate used `query_relevance_max` on 121 authored questions: 60 IT and 61 outside the domain. ROC AUC was 0.9825. Mean relevance score was 0.834 for IT and 0.786 outside the domain.

### Operating points

| Threshold | Precision | Recall | F1 |
|---|---|---|---|
| 0.55 (historical runtime) | 0.496 | 1.000 | 0.663 |
| **0.800 (best observed F1)** | 0.881 | 0.983 | 0.929 |

The 0.55 threshold was the runtime setting at this historical checkpoint. The observed F1 optimum, 0.800, was a recommendation rather than an applied runtime change. Current runtime calibration must be checked separately, especially for the later V3 cosine path.

### Threshold sweep excerpt

| Threshold | P | R | F1 |
|---|---|---|---|
| 0.40 | 0.496 | 1.000 | 0.663 |
| 0.45 | 0.496 | 1.000 | 0.663 |
| 0.50 | 0.496 | 1.000 | 0.663 |
| 0.55 | 0.496 | 1.000 | 0.663 |
| 0.60 | 0.496 | 1.000 | 0.663 |
| 0.65 | 0.496 | 1.000 | 0.663 |
| 0.70 | 0.496 | 1.000 | 0.663 |

The same small dataset selected and evaluated the threshold. Its optimum does not establish generalization to other workloads; a larger independent question set is needed before adopting it as a platform-wide setting.
