"""Regression: ANN phải theo CURRENT.json (active version), không đọc ARTIFACTS_DIR gốc.

Bug gốc: engine.load_engine() gọi load_ann() không tham số; _dir() mặc định
config.ARTIFACTS_DIR (gốc) trong khi mọi artifact khác đi qua config.artifact()
(đọc CURRENT.json). Hệ quả: hoặc fallback brute-force âm thầm, hoặc nạp ANN cũ và
trả kết quả sai do index lệch hàng.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

import itlr.config as config
import itlr.core.ann as ann
from itlr import versioning


class _FakeFaissIndex:
    def __init__(self, dim: int):
        self.dim = dim
        self.vecs: np.ndarray | None = None

    def add(self, vecs: np.ndarray) -> None:
        self.vecs = np.asarray(vecs, dtype=np.float32)

    def search(self, q: np.ndarray, k: int):
        sims = self.vecs @ q.reshape(-1).astype(np.float32)
        order = np.argsort(sims)[::-1][:k]
        return sims[order].reshape(1, -1), order.reshape(1, -1)


class _FakeFaissModule:
    IndexFlatIP = _FakeFaissIndex

    @staticmethod
    def write_index(index, path):
        with open(path, "wb") as f:
            np.save(f, index.vecs)

    @staticmethod
    def read_index(path):
        with open(path, "rb") as f:
            vecs = np.load(f)
        idx = _FakeFaissIndex(vecs.shape[1])
        idx.vecs = vecs
        return idx


@pytest.fixture()
def vroot(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setattr(config, "ARTIFACTS_DIR", root)
    monkeypatch.delenv("ITLR_ARTIFACTS_DIR", raising=False)
    monkeypatch.setattr(ann, "_try_import_faiss", lambda: _FakeFaissModule)
    monkeypatch.setattr(ann, "_try_import_hnswlib", lambda: None)
    return root


def _activate(root, name):
    d = versioning.create_version_dir(root, name)
    versioning.write_manifest(d, {"probe": "ok"})
    versioning.activate(root, name)
    return d


def test_build_and_load_follow_active_version(vroot):
    v1 = _activate(vroot, "v1")
    assert ann.build_ann(np.eye(4, 8, dtype=np.float32)) == "faiss"
    # Build phải ghi vào version đang active, không rải file ra gốc.
    assert (v1 / ann.ANN_META).is_file()
    assert not (vroot / ann.ANN_META).exists()

    loaded = ann.load_ann()
    assert loaded is not None and loaded["backend"] == "faiss"

    # Activate version mới chưa có ANN → tuyệt đối không được lấy ANN của v1.
    _activate(vroot, "v2")
    assert ann.load_ann() is None


def test_load_rejects_stale_index_shape(vroot):
    _activate(vroot, "v1")
    ann.build_ann(np.eye(4, 8, dtype=np.float32))

    assert ann.load_ann(expected_n=4, expected_dim=8) is not None
    assert ann.load_ann(expected_n=3, expected_dim=8) is None
    assert ann.load_ann(expected_n=4, expected_dim=16) is None


def test_pointer_payload_is_relative(vroot):
    _activate(vroot, "v1")
    meta = json.loads((vroot / "CURRENT.json").read_text(encoding="utf-8"))
    assert meta["dir"] == "versions/v1"
