"""Hồi quy bug V2: build_model từng nổ cả hàng có ô rỗng âm thầm (35/5060 items).

Sàn "no silent fallback": ô rỗng TÙY CHỌN (topics/…) không được giết cả item;
chỉ item thiếu dữ liệu CỐT LÕI mới bị loại, và phải log đếm.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

pd = pytest.importorskip("pandas")

from itlr.pipelines.build_model import load_catalog_items  # noqa: E402


def _write_catalog(tmp_path: Path) -> Path:
    p = tmp_path / "catalog.csv"
    pd.DataFrame([
        # row đầy đủ (legacy-style)
        {"item_id": 1, "title": "Học SSH", "type": "Tài liệu", "level": "Cơ bản",
         "description": "SSH cơ bản", "category": "Quản trị hệ thống & Linux",
         "topics": "ssh,linux", "instructor": "AI", "platform": "In-house",
         "link": "https://x/1"},
        # row crawl-style: topics/instructor RỖNG — phải SỐNG SÓT (bug cũ nổ cả hàng)
        {"item_id": 5001, "title": "MDN Blog Post", "type": "Tài liệu", "level": "Trung cấp",
         "description": "Post nội dung thật", "category": "Lập trình Web",
         "topics": "", "instructor": "", "platform": "MDN", "link": "https://a/b"},
        # row thiếu MÔ TẢ — cốt lõi → bị loại (dự kiến, có log)
        {"item_id": 5002, "title": "No description", "type": "Tài liệu", "level": "",
         "description": "", "category": "Lập trình", "topics": "x",
         "instructor": "y", "platform": "z", "link": "https://a/c"},
    ]).to_csv(p, index=False)
    return p


def test_empty_optional_cells_survive(tmp_path):
    df = load_catalog_items(_write_catalog(tmp_path))
    # 2 of 3: ô tùy chọn rỗng giữ hàng; item thiếu description (cốt lõi) bị loại
    assert len(df) == 2
    mdn = df[df["item_id"] == 5001]
    assert len(mdn) == 1
    row = mdn.iloc[0]
    assert row["topics"] == ""
    assert row["instructor"] == ""


def test_missing_core_cell_dropped(tmp_path):
    df = load_catalog_items(_write_catalog(tmp_path))
    assert 5002 not in df["item_id"].tolist()


def test_no_nan_values_after_load(tmp_path):
    df = load_catalog_items(_write_catalog(tmp_path))
    fillable = ["topics", "instructor", "platform", "link", "level", "type"]
    cols = [c for c in fillable if c in df.columns]
    assert not df[cols].isna().any().any(), "cột tùy chọn không được để NaN sau load"
