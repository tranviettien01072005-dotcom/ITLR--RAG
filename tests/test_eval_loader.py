"""Evaluation shares the loaded version and supports optional CF."""
from types import SimpleNamespace

import pandas as pd


def test_rank_context_without_cf_uses_loaded_engine_model(monkeypatch):
    from itlr import engine, config
    from itlr.eval.loader import build_rank_context
    model = {'version': 'loaded'}
    loaded = SimpleNamespace(
        items=pd.DataFrame([dict(category='DevOps', topics='docker')]),
        model=object(), cf_model=None,
        chatbot=SimpleNamespace(retrieval_model=model),
        search_index=dict(embeddings=None, char_vectorizer=None, char_matrix=None))
    monkeypatch.setattr(engine, 'load_engine', lambda: loaded)
    def unexpected_read(*a):
        raise AssertionError('must reuse the model from the loaded version')
    monkeypatch.setattr(config, 'artifact', unexpected_read)
    ctx = build_rank_context()
    assert ctx.retrieval_model is model
    assert ctx.cf_popularity is None
