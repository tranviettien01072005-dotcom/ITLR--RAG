from eval.eval_release_retrieval import metrics, peak_process_rss_mib


def test_multi_item_metrics_and_unanswerable_are_separate():
    result = metrics([1, 9, 2], {1, 2}, 5)
    assert result['recall'] == 1
    assert result['precision_judged'] == .4
    assert result['mrr'] == 1
    assert 0 < result['ndcg'] < 1
    assert metrics([], set(), 5)['recall'] is None
    assert metrics([], set(), 5)['empty_result'] is True
    assert metrics([9], set(), 5)['empty_result'] is False


def test_process_memory_metric_is_positive():
    assert peak_process_rss_mib() > 0
