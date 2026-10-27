"""Test cho itlr.core.ann — đường dẫn artifact TẬP TRUNG + không rò rỉ file handle.

Bugs bị hồi quy:
  1. build_ann()/load_ann() default 'artifacts' TƯƠNG ĐỐI (so với cwd) thay vì
     config.ARTIFACTS_DIR -> chữ ký "artifacts/" tự sinh tùy vị trí chạy.
     engine.load_engine() gọi load_ann() KHÔNG argument -> nạp dùng nhầm thư mục.
  2. pickle.load(open(...)) / pickle.dump(..., open(...)) KHÔNG đóng file handle.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

import itlr.config as config
import itlr.core.ann as ann


class _FakeFaissIndex:
    """Giả lập faiss.IndexFlatIP đủ dùng: add + searchIP + ghi/đọc qua pickle."""

    def __init__(self, dim: int):
        self.dim = dim
        self.vecs: np.ndarray | None = None

    def add(self, vecs: np.ndarray) -> None:
        self.vecs = np.asarray(vecs, dtype=np.float32)

    def search(self, q, k):
        """Trả (distances, labels) theo đúng API faiss: D, I = index.search(q, k)."""
        q = q.reshape(-1).astype(np.float32)
        scores_all = self.vecs @ q
        order = np.argsort(-scores_all)[:k].astype(np.int64)
        return scores_all[order][None, :].astype(np.float32), order[None, :]


def _fake_faiss_module():
    import pickle

    class _Mod:
        @staticmethod
        def IndexFlatIP(dim):
            return _FakeFaissIndex(dim)

        @staticmethod
        def write_index(index, path):
            with open(path, "wb") as f:
                pickle.dump({"dim": index.dim, "vecs": index.vecs}, f)

        @staticmethod
        def read_index(path):
            with open(path, "rb") as f:
                data = pickle.load(f)
            idx = _FakeFaissIndex(data["dim"])
            idx.vecs = data["vecs"]
            return idx

    return _Mod()


def _emb(n: int = 4, d: int = 8) -> np.ndarray:
    return np.eye(n, d, dtype=np.float32)


@pytest.fixture()
def artifacts_root(monkeypatch, tmp_path: Path) -> Path:
    """config.ARTIFACTS_DIR trỏ về tmp_path — đây là chuẩn mà mọi caller kỳ vọng."""
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    return tmp_path


def test_build_uses_config_artifacts_dir(artifacts_root, monkeypatch, tmp_path: Path):
    """build_ann không truyền dir: ghi vào config.ARTIFACTS_DIR, KHÔNG tạo cwd/artifacts."""
    monkeypatch.setattr(ann, "_try_import_faiss", lambda: _fake_faiss_module())
    monkeypatch.setattr(ann, "_try_import_hnswlib", lambda: None)

    cwd = tmp_path / "cwd_here"          # cwd != ARTIFACTS_DIR -> lộ mọi ghi tương đối
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    backend = ann.build_ann(_emb())
    assert backend == "faiss"
    assert (artifacts_root / "ann_meta.pkl").exists(), (
        "meta phải nằm tại config.ARTIFACTS_DIR"
    )
    assert (artifacts_root / "ann_index.faiss").exists()
    assert list(cwd.iterdir()) == [], f"build_ann ghi file relative: {list(cwd.iterdir())}"


def test_load_default_reads_config_artifacts_dir(artifacts_root, monkeypatch, tmp_path: Path):
    """load_ann() không argument phải đọc từ config.ARTIFACTS_DIR — engine gọi đúng cách này."""
    monkeypatch.setattr(ann, "_try_import_faiss", lambda: _fake_faiss_module())
    monkeypatch.setattr(ann, "_try_import_hnswlib", lambda: None)

    build_cwd = tmp_path / "build_cwd"
    build_cwd.mkdir()
    monkeypatch.chdir(build_cwd)
    assert ann.build_ann(_emb()) == "faiss"

    load_cwd = tmp_path / "load_cwd"     # cwd KHÁC lúc build -> tách bạch bug tương đối
    load_cwd.mkdir()
    monkeypatch.chdir(load_cwd)
    got = ann.load_ann()
    assert got is not None and got["backend"] == "faiss", (
        "load_ann() phải đọc từ config.ARTIFACTS_DIR thay vì 'artifacts' tương đối"
    )


def test_load_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    assert ann.load_ann() is None  # thiếu artifacts -> None (fail-safe), không crash


def test_no_unclosed_file_handle(artifacts_root, monkeypatch, tmp_path: Path):
    """pickle.load(open(...)) / pickle.dump(..., open(...)) gây ResourceWarning khi GC."""
    monkeypatch.setattr(ann, "_try_import_faiss", lambda: _fake_faiss_module())
    monkeypatch.setattr(ann, "_try_import_hnswlib", lambda: None)

    cwd = tmp_path / "handle_cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    # Build: phần dump cũng phải sạch (warning error ngay trong lệnh gọi).
    with warnings.catch_warnings():
        warnings.simplefilter("error", ResourceWarning)
        assert ann.build_ann(_emb()) == "faiss"

        load_cwd = tmp_path / "handle_load_cwd"
        load_cwd.mkdir()
        monkeypatch.chdir(load_cwd)
        got = ann.load_ann()
    assert got is not None and got["backend"] == "faiss"


def test_ann_search_roundtrip(artifacts_root, monkeypatch):
    monkeypatch.setattr(ann, "_try_import_faiss", lambda: _fake_faiss_module())
    monkeypatch.setattr(ann, "_try_import_hnswlib", lambda: None)
    ann.build_ann(_emb(4, 4))
    a = ann.load_ann()
    assert a is not None
    q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    idx, scores = ann.ann_search(a, q, top_n=2)
    assert idx is not None and len(idx) == 2 and idx[0] == 0
    assert scores is not None and scores[0] >= scores[1]


def test_ann_search_none_safe(recwarn):
    assert ann.ann_search(None, _emb()[0]) is None
