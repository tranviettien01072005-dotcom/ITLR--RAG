"""Frozen engineering judgments must retain provenance and a source-disjoint holdout."""
import json


def test_engineering_queries_have_evidence_and_no_source_leakage(repo_root):
    cases = [json.loads(line) for name in ('engineering_queries', 'engineering_confirmation_queries')
             for line in (repo_root / f'eval/{name}.jsonl').read_text().splitlines()]
    sources = {int(row['item_id']): row for row in map(json.loads,
               (repo_root / 'data/curated_resources.jsonl').read_text().splitlines())}
    assert len({case['id'] for case in cases}) == len(cases)
    groups = {}
    for split in ('dev', 'holdout', 'confirmation'):
        selected = [case for case in cases if case['split'] == split]
        assert any(case['judgments'] for case in selected)
        assert any(not case['judgments'] for case in selected)
        groups[split] = {j['item_id'] for case in selected for j in case['judgments']}
    assert groups['dev'].isdisjoint(groups['holdout'])
    assert groups['confirmation'].isdisjoint(groups['dev'] | groups['holdout'])
    for case in cases:
        for judgment in case['judgments']:
            source = sources[judgment['item_id']]
            assert judgment['quote'] in source['full_text']
            assert case['source'] == source['link']
