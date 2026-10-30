"""Không được rò file handle qua mẫu `pickle.load(open(...))` / `pickle.dump(..., open(...))`
trong mã nguồn itlr/ — mỗi spot là điểm rò rỉ descriptor (app giữ file mở vô hạn khi nạp
nhiều lần, không đóng được bởi caller).

Chỉ quét các file cốt lõi nạp artifact; regex kiểm chứng NHANH (Ý ĐỊNH là hồi quy).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# File cốt lõi bắt buộc sạch. Mở rộng danh sách nếu thêm module nạp pickle.
TRACKED = ["itlr/engine.py", "itlr/core/ann.py",
           "itlr/pipelines/build_model.py",
           "itlr/pipelines/build_embeddings.py",
           "itlr/pipelines/build_embeddings_v2.py",
           "itlr/pipelines/build_cf.py"]

# Ghi chú: `import pickle; pickle.load(open(path, "rb"))` NHƯNG nếu file khớp
# `open(` dùng trực tiếp làm độc lập arg pickle -> bắt lỗi.
PATTERNS = [
    re.compile(r"pickle\.load\(\s*open\("),
    re.compile(r"pickle\.dump\([^,]+,\s*open\("),
]


@pytest.mark.parametrize("rel", TRACKED)
def test_tracked_files_do_not_leak_file_handles(rel: str):
    path = ROOT / rel
    assert path.exists(), f"thiếu {rel}"
    offenders = [
        pat.pattern for pat in PATTERNS if pat.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        f"{rel} dùng pickle.load/open trực tiếp (không đóng handle): {offenders} — "
        f"hãy dùng `with open(...) as f: pickle.xxx(f)`."
    )


def test_runtime_does_not_hide_estimator_version_mismatch():
    import importlib
    import warnings
    from sklearn.exceptions import InconsistentVersionWarning
    from itlr.utils import runtime_patches

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('default', InconsistentVersionWarning)
        importlib.reload(runtime_patches)
        warnings.warn(InconsistentVersionWarning(
            estimator_name='fixture', current_sklearn_version='1', original_sklearn_version='0'))
    assert any(isinstance(w.message, InconsistentVersionWarning) for w in caught)


def test_repickle_dump_failure_preserves_original(tmp_path, monkeypatch):
    import pickle
    from itlr.utils import repickle

    path = tmp_path / 'fixture.pkl'
    original = pickle.dumps({'trusted': 'original'})
    path.write_bytes(original)
    monkeypatch.setattr(repickle, 'TARGETS', ['fixture.pkl'])
    monkeypatch.setattr(repickle.config, 'artifact', lambda name: str(tmp_path / name))

    def fail_dump(obj, stream, **kwargs):
        stream.write(b'partial')
        raise OSError('fixture disk full')

    monkeypatch.setattr(repickle.pickle, 'dump', fail_dump)
    result = repickle.main()
    assert path.read_bytes() == original
    assert result == 1
    assert list(tmp_path.iterdir()) == [path]


def test_repickle_does_not_restamp_incompatible_sklearn_model(tmp_path, monkeypatch):
    import pickle
    import sklearn
    from sklearn.feature_extraction.text import TfidfVectorizer
    from itlr.utils import repickle

    path = tmp_path / 'fixture.pkl'
    original = pickle.dumps(TfidfVectorizer()).replace(sklearn.__version__.encode(), b'0.0.0')
    path.write_bytes(original)
    monkeypatch.setattr(repickle, 'TARGETS', ['fixture.pkl'])
    monkeypatch.setattr(repickle.config, 'artifact', lambda name: str(tmp_path / name))
    assert repickle.main() == 1
    assert path.read_bytes() == original


def test_repickle_success_is_atomic_and_keeps_permissions(tmp_path, monkeypatch):
    import os
    import pickle
    from itlr.utils import repickle

    path = tmp_path / 'fixture.pkl'
    path.write_bytes(pickle.dumps({'trusted': 'data'}))
    path.chmod(0o640)
    monkeypatch.setattr(repickle, 'TARGETS', ['fixture.pkl'])
    monkeypatch.setattr(repickle.config, 'artifact', lambda name: str(tmp_path / name))
    assert repickle.main() == 0
    with path.open('rb') as stream:
        assert pickle.load(stream) == {'trusted': 'data'}
    if os.name != 'nt':
        assert path.stat().st_mode & 0o777 == 0o640
    assert list(tmp_path.iterdir()) == [path]
