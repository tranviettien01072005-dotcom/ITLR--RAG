"""Regression tests Batch B — audit lifecycle/API/crawler (2026-10-30).

Các hợp đồng được khóa:
1. Admin token non-ASCII phải 403 (không 500 TypeError từ compare_digest).
2. /admin/reload bị rate-limit; lần auth hụt được ghi log (không âm thầm).
3. Engine integrity hỏng (VersionError) → HTTP 503 theo hợp đồng tài liệu, giữ engine
   cũ đang phục vụ khi reload lỗi.
4. chunk_embeddings.pkl thiếu cặp chunk_meta.pkl → FileNotFoundError (bên 503 có
   sẵn), không KeyError 500.
5. GC giữ staging chưa publish; thiếu manifest không chứng minh build đã kết thúc.
6. build_cf từ chối ghi vào phiên bản active đã đóng băng integrity (không phá
   sha256 của bản đang chạy); phải qua staging mới của build_all_v2.
7. get_reranker khởi tạo CrossEncoder đúng một lần dưới luồng đồng thời.
8. CollectStore.upsert_doc trả "row_id" thống nhất cho event "new" như các event khác.
9. Test pickle-handle guard phải theo dõi cả pipeline V2 thật (build_embeddings_v2).
"""

import os
import sys
import threading
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from itlr import versioning
from itlr.engine import RecommenderEngine


@pytest.fixture()
def fake_client(monkeypatch):
    """Client FastAPI với engine giả — không cần artifacts (pattern test_admin_security_cf)."""
    from itlr.api import server as srv

    monkeypatch.setenv("USE_OLLAMA", "0")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ITLR_ADMIN_TOKEN", raising=False)
    from itlr.api import ratelimit
    ratelimit.reset()

    fake = RecommenderEngine(items=[], model=None, search_index={}, cf_model=None,
                             chatbot=None)

    def _load():
        return fake

    _load.cache_clear = lambda: None
    monkeypatch.setattr(srv, "load_engine", _load)
    with TestClient(srv.app) as c:
        yield c, monkeypatch
    ratelimit.reset()


@pytest.fixture()
def vroot(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setattr(versioning.config, "ARTIFACTS_DIR", root)
    return root


def _new_ok_version(vroot, name):
    d = versioning.create_version_dir(vroot, name)
    (d / f"{name}.txt").write_text("x")
    versioning.write_manifest(d, {"probe": "ok"})
    return d


def _new_failed_version(vroot, name, manifest=None):
    d = versioning.create_version_dir(vroot, name)
    (d / f"{name}.txt").write_text("x")
    versioning.write_manifest(d, manifest or {"probe": "fail"})
    return d


def _admin_request_with_token(token_bytes: bytes):
    return {"type": "http", "method": "POST", "path": "/admin/reload",
              "headers": [(b"x-admin-token", token_bytes)],
              "client": ("203.0.113.9", 1234), "query_string": b""}


def test_admin_authorized_utf8_token_bytes_returns_403_not_500(monkeypatch):
    """Header non-ASCII (proxy thường decode latin-1) phải 403 — không TypeError 500."""
    from fastapi import Request
    from itlr.api import server as srv

    monkeypatch.setenv("ITLR_ADMIN_TOKEN", "secret-token")
    scope = {"type": "http", "method": "POST", "path": "/admin/reload",
             "headers": [(b"x-admin-token", b"t\xc3\xb6k\xc3\xa9n")],
             "client": ("203.0.113.9", 1234), "query_string": b""}
    request = Request(scope)

    assert srv._admin_authorized(request) is False
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        srv.admin_reload(request)
    assert exc.value.status_code == 403

    request_bad = Request(_admin_request_with_token(b"wrong-token"))
    assert srv._admin_authorized(request_bad) is False

    request_ok = Request(_admin_request_with_token(b"secret-token"))
    assert srv._admin_authorized(request_ok) is True


def test_admin_reload_rate_limited(fake_client):
    client, monkeypatch = fake_client
    monkeypatch.setenv("ITLR_RATE_ADMIN_PER_MIN", "3")
    monkeypatch.setenv("ITLR_ADMIN_TOKEN", "secret-token")
    statuses = [
        client.post("/admin/reload",
                    headers={"X-Admin-Token": "wrong"}).status_code
        for _ in range(4)
    ]
    assert statuses[:3] == [403, 403, 403]
    assert statuses[3] == 429, statuses


def test_admin_reload_failed_attempt_is_logged(fake_client, capsys):
    client, monkeypatch = fake_client
    monkeypatch.setenv("ITLR_ADMIN_TOKEN", "secret-token")
    client.post("/admin/reload", headers={"X-Admin-Token": "wrong"})
    assert "/admin/reload auth fail" in capsys.readouterr().out


def test_health_and_search_return_503_on_version_error(fake_client):
    """Integrity hỏng (VersionError) theo hợp đồng phải ra 503 — không 500, không âm thầm."""
    client, monkeypatch = fake_client
    from itlr.versioning import VersionError
    from itlr.api import server as srv

    def broken():
        raise VersionError("Artifact integrity mismatch")

    broken.cache_clear = lambda: None
    monkeypatch.setattr(srv, "load_engine", broken)
    assert client.get("/health").status_code == 503
    assert client.post("/api/search", json={"query": "docker"}).status_code == 503


def test_engine_reload_version_error_keeps_previous_serving(tmp_path, monkeypatch):
    from itlr import engine
    from itlr.versioning import VersionError

    monkeypatch.setattr(engine.config, 'ARTIFACTS_DIR', tmp_path)
    previous = object()
    monkeypatch.setattr(engine, '_load_engine', lambda: previous)
    engine.load_engine.cache_clear()
    try:
        assert engine.load_engine() is previous

        def raise_integrity():
            raise VersionError("Artifact integrity mismatch")

        monkeypatch.setattr(engine, '_load_engine', raise_integrity)
        with pytest.raises(VersionError):
            engine.load_engine.reload()
        assert engine.load_engine() is previous
    finally:
        engine.load_engine.cache_clear()


def test_chunk_embeddings_without_chunk_meta_fail_closed(tmp_path, monkeypatch):
    """Nửa bộ artifacts (ebdings có, meta mất) → FileNotFoundError (bên 503), không KeyError."""
    import pickle
    import numpy as np
    from test_index_probe import _mini_artifacts
    from itlr.retrieval.bm25 import BM25Index
    from itlr.core.recommender import (build_field_corpus, build_retrieval_model,
                                       create_vectorizer)
    from itlr import config, engine

    # The fixture encoder is a stub; importing the real package would pull torch.
    sentence_transformers = ModuleType("sentence_transformers")
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)

    monkeypatch.setenv("USE_OLLAMA", "0")
    monkeypatch.delenv("ITLR_ARTIFACTS_DIR", raising=False)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
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
    with (d / 'retrieval_model.pkl').open('wb') as f:
        pickle.dump(model, f)
    with (d / 'embeddings.pkl').open('rb') as f:
        chunk_vectors = pickle.load(f)
    with (d / 'chunk_embeddings.pkl').open('wb') as f:
        pickle.dump(chunk_vectors, f)
    # LỐI ĐI CỐ TÌNH: vì lý do nào đó chunk_meta.pkl KHÔNG có mặt (bản chép nửa vời).

    class FixtureEncoder:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, texts, **kwargs):
            v = np.ones((len(texts), 8), dtype='float32')
            return v / np.linalg.norm(v, axis=1, keepdims=True)

    sentence_transformers.SentenceTransformer = FixtureEncoder
    monkeypatch.setattr('itlr.core.rerank.get_reranker', lambda: None)
    monkeypatch.setattr(config, 'ARTIFACTS_DIR', root)
    versioning.write_manifest(d, {'probe': 'ok'})
    versioning.activate(root, 'fixture')
    engine.load_engine.cache_clear()
    try:
        with pytest.raises(FileNotFoundError) as exc:
            engine._load_engine()
        assert 'chunk_meta' in str(exc.value)
    finally:
        engine.load_engine.cache_clear()


def test_garbage_collect_preserves_unpublished_staging_versions(vroot):
    for v in ("v1", "v2", "v3", "v4", "v5"):
        _new_ok_version(vroot, v)
        versioning.activate(vroot, v)
    for v in ("f1", "f2", "f3", "f4"):
        _new_failed_version(vroot, v)
    _new_failed_version(vroot, "n_missing_probe", manifest={"integrity_schema": 1})
    d_nom = versioning.create_version_dir(vroot, "n1")
    (d_nom / "garbage.txt").write_text("x")

    def failed_now():
        return [v for v in versioning.list_versions(vroot)
                if not versioning.probe_ok(versioning._dir(vroot, v))]

    def ok_now():
        return [v for v in versioning.list_versions(vroot)
                if versioning.probe_ok(versioning._dir(vroot, v))]

    failed_before, ok_before = failed_now(), ok_now()
    versioning.garbage_collect(vroot, keep=2)

    after = set(versioning.list_versions(vroot))
    assert after == set(ok_before[:2]) | set(failed_before)
    assert d_nom.is_dir(), "staging không có manifest có thể vẫn đang build"


def test_build_cf_refuses_to_write_frozen_active_dir(tmp_path, monkeypatch):
    """Ghi cf_model.pkl vào bản active đã stamp manifest sẽ phá integrity — phải chặn."""
    active = tmp_path / "active"
    active.mkdir()
    (active / "MANIFEST.json").write_text('{"probe": "ok"}')
    monkeypatch.setenv("ITLR_ARTIFACTS_DIR", str(active))

    from itlr.pipelines import build_cf

    with pytest.raises(RuntimeError, match="MANIFEST"):
        build_cf.main()
    assert not (active / "cf_model.pkl").exists(), "không được ghi phá cung phách integrity"


def test_cf_builder_pins_directory_when_pointer_changes(tmp_path, monkeypatch):
    import pandas as pd
    from itlr.pipelines import build_cf

    staging, frozen = tmp_path / 'staging', tmp_path / 'frozen'
    staging.mkdir()
    frozen.mkdir()
    items = pd.DataFrame({'item_id': range(1, 7), 'category': ['IT'] * 6})
    for directory in (staging, frozen):
        items.to_pickle(directory / 'item_list.pkl')
    (frozen / 'MANIFEST.json').write_text('{}')
    interactions = tmp_path / 'interactions.csv'
    pd.DataFrame({'user_id': [1] * 6, 'item_id': range(1, 7)}).to_csv(
        interactions, index=False)
    calls = []

    def moving_pointer(name):
        directory = staging if not calls else frozen
        calls.append(name)
        return str(directory / name)

    monkeypatch.setattr(build_cf.config, 'artifact', moving_pointer)
    monkeypatch.setattr(build_cf.config, 'INTERACTIONS_CSV', interactions)
    build_cf.main()
    assert (staging / 'cf_model.pkl').is_file()
    assert not (frozen / 'cf_model.pkl').exists()


def test_reranker_loads_once_under_concurrent_first_queries(monkeypatch):
    from itlr.core import rerank

    monkeypatch.setattr(rerank, "_RERANKER", None)
    monkeypatch.delenv("DISABLE_RERANKER", raising=False)

    count = {"n": 0}

    class SlowCE:
        def __init__(self, *a, **k):
            count["n"] += 1
            threading.Event().wait(0.25)  # cửa sổ race

    fake = ModuleType("sentence_transformers")
    fake.CrossEncoder = SlowCE
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)

    start = threading.Barrier(2, timeout=5)
    results = []

    def worker():
        start.wait()
        results.append(rerank.get_reranker())

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert count["n"] == 1, f"CrossEncoder khởi tạo {count['n']} lần"
    assert results[0] is results[1]


def test_upsert_doc_returns_row_id_for_new_event(tmp_path):
    from itlr.collect.store import CollectStore

    store = CollectStore(tmp_path / "crawl.db")
    try:
        doc = dict(
            content_key="k1", source_id="s1", external_id="e1",
            url="https://example.org/a", norm_url="https://example.org/a",
            title="A", description="d", text="t", tags="", author="",
            published_at="", lang="vi", license="cc0",
            full_text_allowed=True, content_hash="h1", n_chars=1,
            quality_status="ok", status="active",
            fetched_at="2026-10-30T00:00:00Z",
        )
        res = store.upsert_doc(doc)
        row = store.get_doc_by_key("k1")
        assert res["event"] == "new"
        assert res["row_id"] == row["doc_id"], res
        assert res["revision"] == 1
    finally:
        store.close()


def test_pickle_handle_guard_tracks_v2_builder():
    from tests.test_pickle_handles import TRACKED

    assert "itlr/pipelines/build_embeddings_v2.py" in TRACKED, TRACKED
