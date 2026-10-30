"""Kiểm tra integration API FastAPI (chỉ chạy khi artifacts ĐÃ build).

Chạy sau `python scripts/build_all.py`. Không cần LLM: đặt USE_OLLAMA=0 + xóa key
để ép nhánh template — toàn bộ endpoint phải hoạt động deterministically.
"""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import pickle
    import numpy as np
    import sentence_transformers
    from test_index_probe import _mini_artifacts
    from itlr import config, versioning
    from itlr.retrieval.bm25 import BM25Index
    from itlr.core.recommender import build_field_corpus, build_retrieval_model, create_vectorizer
    from fastapi.testclient import TestClient
    from itlr.api import server as srv

    monkeypatch.setenv("USE_OLLAMA", "0")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    root = tmp_path / 'artifacts'
    d = versioning.create_version_dir(root, 'fixture')
    _mini_artifacts(d)
    with (d / 'item_list.pkl').open('rb') as f:
        items = pickle.load(f)
    vecs, matrices = {}, {}
    for field in ['title', 'description', 'topics', 'full']:
        vecs[field] = create_vectorizer().set_params(max_df=1.0)
        matrices[field] = vecs[field].fit_transform(build_field_corpus(items, field))
    model = build_retrieval_model(items, vecs, matrices,
                                 BM25Index().fit(build_field_corpus(items, 'full')))
    cf = dict(labels={1:'Synthetic fixture'}, histories={1:[0]},
              id_to_pos={int(i):p for p,i in enumerate(items.item_id)},
              item_sim=np.ones((len(items),len(items))), popularity=np.ones(len(items)))
    for name,value in [('retrieval_model.pkl',model), ('cf_model.pkl',cf)]:
        with (d/name).open('wb') as f:
            pickle.dump(value,f)
    with (d / 'embeddings.pkl').open('rb') as f:
        chunk_vectors = pickle.load(f)
    for name,value in [('chunk_embeddings.pkl',chunk_vectors),
                       ('chunk_meta.pkl',{'rows':[dict(item_id=int(r.item_id),chunk_idx=0,
                          chunk_text=r.description) for r in items.itertuples()]})]:
        with (d/name).open('wb') as f:
            pickle.dump(value,f)
    class FixtureEncoder:
        def __init__(self,*args,**kwargs): pass
        def encode(self,texts,**kwargs):
            v = np.ones((len(texts),8), dtype='float32')
            return v / np.linalg.norm(v,axis=1,keepdims=True)
    monkeypatch.setattr(sentence_transformers,'SentenceTransformer',FixtureEncoder)
    monkeypatch.setattr('itlr.core.rerank.get_reranker',lambda:None)
    monkeypatch.setattr(config,'ARTIFACTS_DIR',root)
    monkeypatch.delenv('ITLR_ARTIFACTS_DIR',raising=False)
    versioning.write_manifest(d, {'probe':'ok'})
    versioning.activate(root,'fixture')
    srv.load_engine.cache_clear()
    try:
        with TestClient(srv.app) as c:
            yield c
    finally:
        srv.load_engine.cache_clear()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_search_endpoint(client):
    r = client.post("/api/search", json={"query": "học docker kubernetes cơ bản",
                                         "min_pct": 70})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["results"], list)
    if data["results"]:
        top = data["results"][0]
        assert "item_id" in top and "title" in top


def test_chat_template_mode_works(client):
    r = client.post("/api/chat", json={"message": "Docker là gì và dùng để làm gì?",
                                       "history": []})
    assert r.status_code == 200
    data = r.json()
    assert data["response"], "template mode phải trả câu trả lời không trống"
    assert "intent" in data


def test_chat_stream_sse_frames(client):
    with client.stream("POST", "/api/chat/stream",
                       json={"message": "Git khác SVN thế nào?", "history": []}) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        frames = []
        for line in r.iter_lines():
            if line.startswith("data: "):
                frames.append(line)
        assert frames and any('"type": "done"' in f for f in frames)


def test_for_you_with_persona(client):
    personas = client.get("/api/personas").json()
    assert isinstance(personas, list) and len(personas) > 0
    uid = personas[0]["uid"]
    r = client.post("/api/for-you", json={"persona": uid})
    assert r.status_code == 200
    recs = r.json().get("recs", [])
    assert isinstance(recs, list)


def test_versioned_chunk_index_loaded(client):
    from itlr.api.server import load_engine
    engine = load_engine()
    assert engine.search_index['chunks'].ann.ntotal == len(engine.items)
    sources = engine.chatbot._semantic_retrieve('docker', top_k=2)
    assert sources and all(s['chunk_id'].endswith(':0') for s in sources)


def test_api_search_and_chat_use_shared_retrieval(client, monkeypatch):
    from itlr.api.server import load_engine
    engine=load_engine()
    service=engine.search_index['retrieval']
    calls=[]
    original=service.search
    def traced(query,**kwargs):
        calls.append(query)
        return original(query,**kwargs)
    monkeypatch.setattr(service,'search',traced)
    assert client.post('/api/search',json={'query':'docker','min_pct':10}).status_code==200
    engine.chatbot._semantic_retrieve('docker')
    assert len(calls)==2
    monkeypatch.setattr(service,'relevance',lambda query:.1)
    assert engine.chatbot._is_off_topic('Docker') is True


def test_corrupt_version_reload_keeps_loaded_engine(client):
    import pytest
    from itlr.api.server import load_engine
    from itlr import config, versioning
    previous=load_engine()
    path=config.current_dir()/'chunk_embeddings.pkl'
    with path.open('ab') as handle:
        handle.write(b'corruption')
    with pytest.raises(versioning.VersionError):
        load_engine.reload()
    assert load_engine() is previous
    assert client.get('/health').status_code==200


def test_quick_resources_uses_chunk_service(client, monkeypatch):
    from itlr.api.server import load_engine
    from itlr.chatbot import chatbot
    def legacy(*a,**kw): raise AssertionError('V3 must use shared retrieval')
    monkeypatch.setattr(chatbot,'search_by_embedding',legacy)
    resources=load_engine().chatbot._quick_resources('docker',k=2)
    assert resources and all('chunk_id' in item for item in resources)


def test_isolated_probe_activate_reload_rollback_and_gc(client, monkeypatch):
    """Exercise real pointer/integrity/engine lifecycle on the fixture root only.

    Encoder is the client fixture double; this is not a neural model probe.
    """
    import shutil
    import pickle
    from itlr import config, versioning
    from itlr.indexv2 import probe
    from itlr.api import server

    root = config.ARTIFACTS_DIR
    original = versioning.current_dir(root)
    for name in ('release-two', 'unactivated'):
        target = versioning.create_version_dir(root, name)
        shutil.copytree(original, target, dirs_exist_ok=True)
        with (target / 'item_list.pkl').open('rb') as handle:
            items = pickle.load(handle)
        items['release_marker'] = name
        with (target / 'item_list.pkl').open('wb') as handle:
            pickle.dump(items, handle)
        ok, report = probe(target, with_engine=False)
        assert ok, report
    monkeypatch.setenv('ITLR_ADMIN_TOKEN', 'fixture-lifecycle-token')
    headers = {'X-Admin-Token': 'fixture-lifecycle-token'}
    versioning.activate(root, 'release-two')
    assert client.post('/admin/reload', headers=headers).status_code == 200
    second = server.load_engine()
    assert set(second.items.release_marker) == {'release-two'}
    assert client.post('/api/search', json={'query': 'docker', 'min_pct': 0}).status_code == 200
    assert versioning.rollback(root)
    assert client.post('/admin/reload', headers=headers).status_code == 200
    assert 'release_marker' not in server.load_engine().items.columns
    assert server.load_engine() is not second
    versioning.garbage_collect(root, keep=0)
    assert versioning.current_dir(root) == original
    assert original.is_dir()
    assert not (root / 'versions' / 'unactivated').exists()
