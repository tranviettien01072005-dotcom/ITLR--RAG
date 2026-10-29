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
