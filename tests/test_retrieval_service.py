import numpy as np
import pandas as pd
import pytest


def fixture_service():
    from itlr.retrieval.service import RetrievalService
    from itlr.core.chunks import ChunkIndex
    rows=[dict(item_id=1,chunk_idx=0,chunk_text='docker networks'),
          dict(item_id=2,chunk_idx=0,chunk_text='python lists')]
    items=pd.DataFrame([dict(item_id=1,type='article'),dict(item_id=2,type='video')])
    class Encoder:
        def encode(self,texts,**kwargs): return np.array([[1.,0.] for _ in texts],dtype='float32')
    return RetrievalService(ChunkIndex(rows,np.eye(2,dtype='float32')),items,Encoder(),'query: ')


def test_shared_service_filters_before_candidate_selection():
    service=fixture_service()
    hits=service.search('python',item_type='video',min_relevance=0,top_k=1)
    assert hits[0]['item_id']==2


def test_gate_uses_chunk_cosine_not_rrf_score():
    service=fixture_service()
    assert service.relevance('docker') == 1.
    assert service.search('docker',min_relevance=.9)[0]['chunk_id']=='1:0'


def test_empty_and_zero_query_have_no_results():
    assert fixture_service().search('   ')==[]


def test_search_default_uses_calibrated_floor_and_keeps_explicit_override(monkeypatch):
    from itlr.api.server import SearchReq
    from itlr.engine import RecommenderEngine
    from itlr.chatbot import query_understanding, knowledge_base
    from itlr.core.chunks import ChunkIndex

    service = fixture_service()
    service.index = ChunkIndex([dict(item_id=1, chunk_idx=0, chunk_text='docker')],
                               [[.86, (1 - .86**2)**.5]])
    service.items[1].update(title='Docker', category='DevOps', topics='docker',
                            description='Docker', instructor='', platform='Docs',
                            link='https://example.org')
    monkeypatch.setattr(query_understanding, 'understand_query', lambda *a: dict(
        corrected='docker', expansions=[], display='docker', corrections=[]))
    monkeypatch.setattr(knowledge_base, 'safe_concept_match', lambda *a: None)
    engine = RecommenderEngine(None, None, {'retrieval': service}, None, None)
    assert SearchReq(query='docker').min_pct == 84
    assert engine.search('docker')['results']
    assert engine.search('docker', min_pct=90)['results'] == []


def test_glossary_expansion_preserves_specific_question_intent(monkeypatch):
    from types import SimpleNamespace
    from itlr.engine import RecommenderEngine
    from itlr.chatbot import query_understanding, knowledge_base

    seen = []

    def search(query, **kwargs):
        seen.append(query)
        return []

    monkeypatch.setattr(query_understanding, 'understand_query', lambda q, *a: dict(
        corrected=q, expansions=[], display=q, corrections=[]))
    monkeypatch.setattr(knowledge_base, 'safe_concept_match', lambda *a: 'token')
    monkeypatch.setitem(knowledge_base.CONCEPTS, 'token', dict(
        name='Token', aliases=['token'], topics=['authentication', 'security']))
    engine = RecommenderEngine(None, None, {'retrieval': SimpleNamespace(search=search)}, None, None)
    question = 'What is the secret session token for my logged-in user?'
    engine.search(question)
    assert seen[-1] == question
    engine.search('TOKEN')
    assert 'authentication' in seen[-1]


@pytest.mark.parametrize('changed', [False, True])
def test_dense_search_keeps_raw_text_unless_a_correction_is_needed(monkeypatch, changed):
    from types import SimpleNamespace
    from itlr.engine import RecommenderEngine
    from itlr.chatbot import query_understanding, knowledge_base

    question = 'Which Python function handles this case?'
    normalized = 'which python function handles this case'
    seen = []
    monkeypatch.setattr(query_understanding, 'understand_query', lambda *a: dict(
        corrected=normalized, expansions=[], display=normalized,
        corrections=[('fixture', 'corrected')] if changed else []))
    monkeypatch.setattr(knowledge_base, 'safe_concept_match', lambda *a: None)

    def search(query, **kwargs):
        seen.append(query)
        return []

    engine = RecommenderEngine(None, None, {'retrieval': SimpleNamespace(search=search)}, None, None)
    engine.search(question)
    assert seen == [normalized if changed else question]


def test_legacy_bm25_pickle_global_still_resolves():
    import pickle
    from itlr.retrieval.bm25 import BM25Index
    assert pickle.loads(b'citlr.core.bm25\nBM25Index\n.') is BM25Index


def test_engine_search_returns_distinct_items_when_one_has_many_chunks(monkeypatch):
    from itlr.core.chunks import ChunkIndex
    from itlr.retrieval.service import RetrievalService
    from itlr.engine import RecommenderEngine
    from itlr.chatbot import query_understanding, knowledge_base
    from types import SimpleNamespace

    service = fixture_service()
    rows = [dict(item_id=1, chunk_idx=i, chunk_text='docker') for i in range(40)]
    rows.append(dict(item_id=2, chunk_idx=0, chunk_text='docker volumes'))
    items = pd.DataFrame([
        dict(item_id=i, title='Docker', type='article', category='DevOps',
             description='Docker documentation', topics='docker', instructor='',
             platform='Docs', link='https://example.org') for i in (1, 2)])
    service = RetrievalService(ChunkIndex(rows, [[1., 0.]] * 40 + [[.8, .6]]),
                               items, service.encoder)
    monkeypatch.setattr(query_understanding, 'understand_query', lambda *a: dict(
        corrected='docker', expansions=[], display='docker', corrections=[]))
    monkeypatch.setattr(knowledge_base, 'safe_concept_match', lambda *a: None)
    engine = RecommenderEngine(items, None, {'retrieval': service}, None, None)
    assert {r['item_id'] for r in engine.search('docker', min_pct=0)['results']} == {1, 2}
    from itlr.chatbot.chatbot import EducationalChatbot
    bot = SimpleNamespace(search_index={'retrieval': service})
    assert {r['item_id'] for r in EducationalChatbot._quick_resources(bot, 'docker', k=2)} == {1, 2}
