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
