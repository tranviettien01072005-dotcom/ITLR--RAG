# ITLR–RAG | Intelligent IT Learning Platform

## Off-policy estimator simulation (D)

Historical record: 2026-10-27. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

A contextual-bandit simulation used the 5,000-item legacy synthetic catalog for 6,000 rounds with known reward truth. The original report called these items real; catalog provenance establishes synthetic data. No production clicks or real learner outcomes were measured.

### Estimates against known policy values

| Quantity | Value | 95% CI | Covers target truth? |
|---|---|---|---|
| **New policy truth** | **0.5465** | — | Reference |
| Old policy truth | 0.4289 | — | — |
| Naive observed CTR | 0.4425 | — | Bias -0.1040 |
| IPS | 0.5703 | [0.5518, 0.5880] | No |
| SNIPS | 0.5585 | [0.5440, 0.5721] | Yes |
| DR | 0.5540 | [0.5400, 0.5673] | Yes |

Effective sample size was 4686/6000. The original recommendation was to consider SNIPS/DR and weight clipping when importance weights are uneven. Here SNIPS and DR intervals cover the target truth, while the IPS interval does not; naive observed CTR is lower by -0.1040. These finite-sample results do not prove universal unbiasedness or interval coverage.

The experiment estimates a new policy from simulated logs of an older policy. `itlr/eval/off_policy.py` is the historical implementation entry point. Applying it to real clicks requires appropriate logging propensities, support and reward assumptions to be checked for that dataset; this run does not establish them.
