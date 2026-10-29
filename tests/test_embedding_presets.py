from itlr.core.embeddings import resolve_preset

def test_full_e5_model_id_preserves_required_prefixes():
    preset = resolve_preset('intfloat/multilingual-e5-base')
    assert preset['query_prefix'] == 'query: '
    assert preset['passage_prefix'] == 'passage: '
    assert preset['dim'] == 768
