"""Statistical claims in eval reports must have covered primitives."""

import pytest

from itlr.eval.significance import cohen_kappa, compare, paired_bootstrap


def test_paired_bootstrap_is_reproducible_and_ordered():
    a, b = [1, 0, 1, 1], [0, 0, 1, 0]
    result = paired_bootstrap(a, b, n_boot=200, seed=7)
    assert result["mean_diff"] == pytest.approx(0.5)
    assert result["ci_low"] <= result["mean_diff"] <= result["ci_high"]
    assert result == paired_bootstrap(a, b, n_boot=200, seed=7)


def test_paired_bootstrap_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        paired_bootstrap([1, 0], [1])


def test_compare_detects_consistent_gain():
    result = compare([1] * 20, [0] * 20, n_boot=200)
    assert result["mean_diff"] == pytest.approx(1.0)
    assert result["significant"] is True


def test_cohen_kappa_perfect_agreement_and_invalid_input():
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        cohen_kappa([], [])
