"""Audit regressions: data policy, RSS timestamps and standard evaluation."""
import json
import math

import pytest

from itlr.collect.adapters import rss_candidates
from itlr.collect.sources import Source, SourcesError, load_sources
from eval.eval_v2_real import _ndcg_at_k


def test_rss_publication_timestamp_has_no_weekday_microseconds():
    src = Source('s', 'rss', 'S', 'P', 'https://r', True, 'L')
    xml = b'<rss version="2.0"><channel><title>R</title><item><title>Docker</title><link>https://r/a</link><pubDate>Wed, 28 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>'
    assert rss_candidates(src, xml)[0].published_at == '2026-10-28T10:00:00Z'


@pytest.mark.parametrize('field', ['full_text_allowed', 'listing_is_complete'])
@pytest.mark.parametrize('value', ['false', 1, None])
def test_policy_flags_require_json_booleans(tmp_path, field, value):
    src = dict(source_id='s', kind='rss', name='S', feed_url='https://r/rss')
    src[field] = value
    path = tmp_path / 'sources.json'
    path.write_text(json.dumps({'sources': [src]}))
    with pytest.raises(SourcesError):
        load_sources(path)


def test_ndcg_uses_logarithmic_rank_discount():
    assert _ndcg_at_k([2, 1], {1: 3, 2: 1}, 2) == pytest.approx(
        (1 + 7 / math.log2(3)) / (7 + 1 / math.log2(3)))


def test_rrf_repeated_document_in_one_ranking_does_not_inflate_weight():
    from itlr.core.recommender import reciprocal_rank_fusion
    assert reciprocal_rank_fusion([[1, 1, 2], [2, 1]]) == reciprocal_rank_fusion([[1, 2], [2, 1]])


def test_pipeline_encodes_query_once_per_rank(monkeypatch):
    from itlr.core import pipeline
    from types import SimpleNamespace
    import numpy as np
    calls = []
    def scores(*args):
        calls.append(True)
        return np.array([.9, .2])
    monkeypatch.setattr(pipeline, '_base_scores', scores)
    assert pipeline.rank(SimpleNamespace(), 'docker', pipeline.StageConfig()) == [0, 1]
    assert len(calls) == 1
