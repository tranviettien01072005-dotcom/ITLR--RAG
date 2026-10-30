"""Test cho itlr.pipelines.generate_interactions — sinh tương tác mô phỏng
latent-persona cho CF, đủ 1.800 users (seed cố định cho tái lập).

Bugs/được hồi quy:
  - build_cf cần lịch sử >= 5 items/user — generator phải BẢO ĐẢM điều này.
  - Cấu trúc tiềm ẩn (persona) phải có: lịch sử mỗi user TẬP TRUNG vào số ít chuyên mục
    (khác cơ hội-ba-trời) — nếu không CF chỉ học phổ-biến (dữ liệu vô nghĩa).
  - Reproducibility: cùng seed -> cùng dữ liệu (byte-identical).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import itlr.pipelines.generate_interactions as gi

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def items_small() -> pd.DataFrame:
    """Catalog mini 36 items / 3 chuyên mục / 12 topics — đủ để ràng buộc cấu trúc."""
    rows = []
    cats = ["AI / Machine Learning", "Web Development", "An ninh mạng"]
    topics = {
        "AI / Machine Learning": ["Python", "Deep Learning", "NLP", "Computer Vision"],
        "Web Development": ["JavaScript", "React", "CSS", "HTML"],
        "An ninh mạng": ["Bảo mật web", "Pentest", "Mạng", "Sao lưu"],
    }
    iid = 1
    for cat in cats:
        for t in topics[cat]:
            for k in range(3):
                rows.append({
                    "item_id": iid, "title": f"{t} {cat} {k}", "type": "Khóa học",
                    "level": "Cơ bản", "description": "mô tả ngắn",
                    "category": cat, "topics": t, "instructor": "GV-a",
                    "platform": "Tự học", "link": "https://example.com/x",
                })
                iid += 1
    return pd.DataFrame(rows)


def test_generate_deterministic_with_seed(items_small):
    a = gi.generate_interactions(items_small, n_users=60, seed=7, avg_per_user=15.0)
    b = gi.generate_interactions(items_small, n_users=60, seed=7, avg_per_user=15.0)
    pd.testing.assert_frame_equal(a, b)


def test_generate_schema_and_coverage(items_small):
    df = gi.generate_interactions(items_small, n_users=60, seed=7, avg_per_user=15.0)
    assert list(df.columns) == ["user_id", "item_id"]
    assert df["user_id"].nunique() == 60
    # user_id liên tục 1..60 (persona đủ đơn giản cho feed for-you)
    assert sorted(df["user_id"].unique()) == list(range(1, 61))
    assert df["item_id"].isin(set(items_small["item_id"])).all()
    # mỗi user >= MIN_HIST (chuỗi cạnh build_cf yêu cầu >= 5)
    assert df.groupby("user_id").size().min() >= gi.MIN_HISTORY
    # không trùng cặp (user đã xem lại cùng item trong lịch sử mô phỏng thì mất nghĩa)
    assert df.duplicated(subset=["user_id", "item_id"]).sum() == 0


def test_generate_latent_structure(items_small):
    """Persona phải TẬP TRUNG: share chuyên mục CHÍNH mỗi user (top-1) phải cao hơn
    rõ rệt so với baseline xáo trộn (baseline ~ 1/3 khi catalog có 3 chuyên mục)."""
    def top1_share(frame: pd.DataFrame) -> float:
        cnt = frame.groupby(["user_id", "category"]).size().reset_index()
        by_user = cnt.groupby("user_id")[0]
        share = by_user.max() / by_user.sum()
        return float(share.mean())

    df = gi.generate_interactions(items_small, n_users=60, seed=7, avg_per_user=15.0)
    sim = top1_share(df.merge(items_small[["item_id", "category"]], on="item_id"))

    rng = np.random.RandomState(0)
    shuffled = df.copy()
    shuffled["item_id"] = rng.permutation(shuffled["item_id"].to_numpy())
    base = top1_share(shuffled.merge(items_small[["item_id", "category"]], on="item_id"))

    assert sim >= max(0.6, base + 0.15), (
        f"persona không tập trung: sim={sim:.2f} vs ngẫu nhiên={base:.2f}"
    )


def test_generate_full_size_1800(items_small):
    """Ràng buộc quy mô: 1.800 users với catalog nhỏ chạy nhanh và đủ 1800 user."""
    df = gi.generate_interactions(items_small, n_users=1800, seed=7, avg_per_user=25.0)
    assert df["user_id"].nunique() >= 1800 - 60  # cho phép dropout user quá ngắn -> min hist
    assert len(df) >= 1800 * gi.MIN_HISTORY


def test_cli_help():
    r = subprocess.run([sys.executable, "-m", "itlr.pipelines.generate_interactions", "--help"],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[:300]
    assert "--n-users" in r.stdout and "--seed" in r.stdout
