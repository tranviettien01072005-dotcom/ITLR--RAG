"""Test probe/validate index V2 — dùng artifacts MINI tự dựng (numpy + sklearn), không torch."""

import pickle

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from itlr.indexv2 import probe, self_retrieval_sanity, validate_artifacts


def _mini_artifacts(tmp_path, *, n=30, dim=8, corrupt=None):
    rng = np.random.RandomState(20240623)
    titles = [f"Hướng dẫn lập trình web docker kubernetes bài {idx}"
              if idx % 2 == 0 else f"Tài liệu machine learning học máy part {idx}"
              for idx in range(n)]
    items = pd.DataFrame({
        "item_id": np.arange(1, n + 1),
        "title": titles,
        "type": ["Tài liệu"] * n,
        "level": ["Trung cấp"] * n,
        "description": titles,
        "category": ["Docker & Web"] * n,
        "topics": ["docker, kubernetes"] * n,
        "instructor": ["A"] * n,
        "platform": ["P"] * n,
        "link": [f"https://x/{idx}" for idx in range(n)],
    })
    vec = TfidfVectorizer(min_df=1).fit(titles)
    matrix = vec.transform(titles)
    emb = rng.randn(n, dim).astype(np.float32)
    emb = normalize(emb)
    for name in ("item_list.pkl",):
        with open(tmp_path / name, "wb") as f:
            pickle.dump(items, f)
    for name in ("embeddings.pkl",):
        with open(tmp_path / name, "wb") as f:
            pickle.dump(emb, f)
    for name in ("search_meta.pkl",):
        with open(tmp_path / name, "wb") as f:
            pickle.dump({"model_name": "test", "query_prefix": "",
                         "passage_prefix": "", "dim": dim}, f)
    for name in ("tfidf_vectorizer.pkl", "char_vectorizer.pkl"):
        with open(tmp_path / name, "wb") as f:
            pickle.dump(vec, f)
    for name in ("tfidf_matrix.pkl", "char_matrix.pkl"):
        with open(tmp_path / name, "wb") as f:
            pickle.dump(matrix, f)
    retrieval_model = {
        "vectorizers": {"full": vec},
        "matrices": {"full": matrix},
        "bm25": None,   # probe chỉ cần vectorizers/matrices/bm25/categories tồn tại
        "categories": ["Docker & Web"],
    }
    with open(tmp_path / "retrieval_model.pkl", "wb") as f:
        pickle.dump(retrieval_model, f)
    if corrupt:
        corrupt(tmp_path)
    return tmp_path


class TestValidation:
    def test_valid_artifacts_pass(self, tmp_path):
        d = _mini_artifacts(tmp_path)
        ok, report = validate_artifacts(d)
        assert ok is True, report

    def test_missing_file_fails(self, tmp_path):
        d = _mini_artifacts(tmp_path)
        (d / "embeddings.pkl").unlink()
        ok, report = validate_artifacts(d)
        assert ok is False
        assert any("required_files" == c["check"] for c in report["checks"])

    def test_nan_embeddings_fails(self, tmp_path):
        def corrupt(p):
            with open(p / "embeddings.pkl", "rb") as f:
                emb = pickle.load(f)
            emb[0] = np.nan
            with open(p / "embeddings.pkl", "wb") as f:
                pickle.dump(emb, f)
        d = _mini_artifacts(tmp_path, corrupt=corrupt)
        ok, report = validate_artifacts(d)
        assert ok is False
        assert any(c["check"] == "no_nan" and not c["ok"] for c in report["checks"])

    def test_row_mismatch_fails(self, tmp_path):
        def corrupt(p):
            with open(p / "embeddings.pkl", "rb") as f:
                emb = pickle.load(f)
            with open(p / "embeddings.pkl", "wb") as f:
                pickle.dump(emb[:-1], f)
        d = _mini_artifacts(tmp_path, corrupt=corrupt)
        ok, _ = validate_artifacts(d)
        assert ok is False

    def test_duplicate_item_ids_fail(self, tmp_path):
        def corrupt(p):
            with open(p / "item_list.pkl", "rb") as f:
                items = pickle.load(f)
            items.loc[1, "item_id"] = items.loc[0, "item_id"]
            with open(p / "item_list.pkl", "wb") as f:
                pickle.dump(items, f)
        d = _mini_artifacts(tmp_path, corrupt=corrupt)
        ok, report = validate_artifacts(d)
        assert ok is False


class TestSelfRetrieval:
    def test_tfidf_self_retrieval_high(self, tmp_path):
        d = _mini_artifacts(tmp_path)
        ratio, _ = self_retrieval_sanity(d, n_samples=10, top_k=5)
        assert ratio >= 0.8

    def test_probe_writes_manifest(self, tmp_path):
        d = _mini_artifacts(tmp_path)
        ok, report = probe(d, with_engine=False, min_self_recall=0.8)
        assert ok is True
        import json

        with open(d / "MANIFEST.json") as f:
            m = json.load(f)
        assert m["probe"] == "ok"


def test_self_retrieval_handles_catalog_smaller_than_top_k(tmp_path):
    d = _mini_artifacts(tmp_path, n=2)
    ratio, report = self_retrieval_sanity(d, top_k=5)
    assert ratio == 1.0
    assert report['n_samples'] == 2


def test_self_retrieval_rejects_zero_top_k(tmp_path):
    import pytest
    d = _mini_artifacts(tmp_path, n=2)
    with pytest.raises(ValueError, match='positive'):
        self_retrieval_sanity(d, top_k=0)
