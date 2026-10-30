"""Ranking and beyond-accuracy metrics are report inputs; pin their math."""

import numpy as np
import pytest

from itlr.eval import diversity, metrics


def test_precision_recall_hit_and_reciprocal_rank():
    assert metrics.precision_at_k([1, 0, 1], 2) == 0.5
    assert metrics.precision_at_k([1, 0, 1], 0) == 0.0
    assert metrics.recall_at_k([1, 0, 1], 2, 2) == 0.5
    assert metrics.recall_at_k([1], 5, 0) == 0.0
    assert metrics.hit_rate_at_k([0, 0, 1], 2) == 0.0
    assert metrics.hit_rate_at_k([0, 0, 1], 3) == 1.0
    assert metrics.reciprocal_rank([0, 1, 0]) == 0.5
    assert metrics.reciprocal_rank([0, 0]) == 0.0


def test_dcg_and_ndcg_use_ideal_ranking():
    assert metrics.dcg_at_k([1], 5) == pytest.approx(1.0)
    assert metrics.ndcg_at_k([1], 5) == pytest.approx(1.0)
    assert metrics.ndcg_at_k([0, 1], 2, ideal_rels=[1]) == pytest.approx(1 / np.log2(3))
    assert metrics.ndcg_at_k([0, 0], 2) == 0.0


def test_average_precision_and_per_query_bundle():
    assert metrics.average_precision([1, 0, 1], 2) == pytest.approx((1 + 2 / 3) / 2)
    assert metrics.average_precision([0, 0], 1) == 0.0
    row = metrics.per_query_metrics([1, 0], 2, ks=(1, 2), ideal_rels=[1, 0])
    assert row["P@1"] == 1.0
    assert row["R@2"] == 0.5
    assert row["MRR"] == 1.0
    assert row["MAP"] == pytest.approx(0.5)


def test_evaluate_run_and_rankings():
    assert metrics.evaluate_run([]) == {}
    averaged = metrics.evaluate_run([{"A": 1.0, "B": 0.0}, {"A": 0.0, "B": 1.0}])
    assert averaged == {"A": 0.5, "B": 0.5}
    result = metrics.evaluate_rankings([[1, 0], [0, 1]], [1, 1], ks=(1,))
    assert result["R@1"] == 0.5
    assert result["MRR"] == pytest.approx(0.75)


def test_diversity_metrics():
    lists = [[0, 1], [1, 2]]
    assert diversity.catalog_coverage(lists, 4) == 0.75
    assert diversity.catalog_coverage(lists, 0) == 0.0

    orthogonal = np.eye(3)
    assert diversity.intra_list_diversity([0, 1], orthogonal) == pytest.approx(1.0)
    assert diversity.intra_list_diversity([0, 0], orthogonal) == pytest.approx(0.0)
    assert diversity.intra_list_diversity([0], orthogonal) == 0.0
    assert diversity.mean_intra_list_diversity([[0, 1], [2]], orthogonal) == pytest.approx(1.0)

    assert diversity.novelty([], np.ones(3)) == 0.0
    assert diversity.novelty([[0]], np.ones(3)) > 0.0
    assert diversity.serendipity([], [], []) == 0.0
    assert diversity.serendipity([[0, 1]], [{0, 1}], [{1}]) == 0.5

    assert diversity.gini_index([], 3) == 0.0
    assert diversity.gini_index([[0, 1, 2]], 3) == pytest.approx(0.0)
    assert diversity.gini_index([[0, 0, 0]], 3) > 0.0
    assert "Coverage" in diversity.beyond_accuracy_report(lists, 4)
