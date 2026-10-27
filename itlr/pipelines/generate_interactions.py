"""Sinh dữ liệu tương tác MÔ PHỎNG cho CF (cấu trúc latent-persona), deterministic theo seed.

Đặc tả:
  - n_users (mặc định 1.800), mỗi user có "persona" gồm 1-3 chuyên mục ưa thích (sampling
    theo phân phối tần suất chuyên mục của catalog — tái lập được khi cùng seed).
  - Số click/user theo phân phối gamma quanh avg_per_user (~25) — mô phỏng vài user
    hyper-active, đa số bình thường.
  - WITHIN_PERSONA_PROB (mặc định 0.8): click nằm TRONG chuyên mục persona; còn lại là
    khám phá (exploration, giới hạn EXPLORATION_CAP) — giúp CF học cả liên kết chéo.
  - Trong pool, chọn theo phổ-biến power-law (rich-get-richer) — giống hành vi học online
    nơi "khóa viral" được bấm nhiều hơn.

LƯU Ý QUAN TRỌNG về tính trung thực: đây là dữ liệu MÔ PHỎNG (synthetic), KHÔNG phải hành
vi người thật. Dùng để demo pipeline, chạy eval CF (off-policy với click là reward đã biết
trước) và so sánh hệ thống — KHÔNG được tuyên bố là dữ liệu thực tế của người dùng.

Cách chạy:
    python -m itlr.pipelines.generate_interactions              # 1800 users, seed 7
    python -m itlr.pipelines.generate_interactions --n-users 500 --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

from itlr import config

MIN_HISTORY = 5             # user có lịch sử ngắn hơn bị DỌN (build_cf yêu cầu >= 5)
WITHIN_PERSONA_PROB = 0.8   # tỷ lệ click TRONG chuyên mục persona
POWERLAW_ALPHA = 1.15       # độ "nghĩa" phổ-biến: P(rank) ~ rank^-alpha
EXPLORATION_CAP = 1         # tối đa số lượt khám phá NGOÀI persona (giữ tín hiệu tập trung)


def _personas(items: pd.DataFrame, n_users: int,
              rng: np.random.RandomState) -> list[set]:
    """Chọn 1-3 chuyên mục ưa thích mỗi user, phân phối theo tần suất chuyên mục."""
    cat_counts = items["category"].value_counts()
    cats = list(cat_counts.index)
    probs = (cat_counts / cat_counts.sum()).to_numpy()
    n_choices = rng.choice([1, 2, 3], size=n_users, p=[0.45, 0.40, 0.15])
    out = []
    for k in n_choices:
        picks = rng.choice(cats, size=k, replace=False, p=probs)
        out.append(set(str(c) for c in picks))
    return out


def generate_interactions(items: pd.DataFrame, n_users: int = 1800, seed: int = 7,
                          avg_per_user: float = 25.0) -> pd.DataFrame:
    """Sinh tương tác mô phỏng deterministically; schema (user_id, item_id)."""
    rng = np.random.RandomState(seed)

    items = items.reset_index(drop=True)
    isin = items["item_id"].astype(int).to_numpy()
    n_items = len(items)
    pos = np.arange(n_items)

    # Phổ-biến power-law:(rank) ~ rank^-alpha — items xếp sớm trong catalog phổ biến hơn.
    pop_raw = (pos / n_items + 0.02) ** (-POWERLAW_ALPHA)
    pop_all = pop_raw / pop_raw.sum()

    by_cat = {cat: group["item_id"].astype(int).to_numpy()
              for cat, group in items.groupby("category", sort=False)}
    mask_by_cat = {cat: np.isin(isin, ids) for cat, ids in by_cat.items()}

    personas = _personas(items, n_users, rng)

    rows: list[tuple[int, int]] = []
    for uid, picks in enumerate(personas, start=1):
        n_clicks = max(MIN_HISTORY + 1,
                       int(rng.gamma(shape=2.0, scale=avg_per_user / 2.0)))

        within_mask = np.zeros(n_items, dtype=bool)
        for c in picks:
            within_mask |= mask_by_cat.get(c, np.zeros(n_items, dtype=bool))
        within_items = isin[within_mask]
        within_weights = pop_all[within_mask]
        within_weights = within_weights / within_weights.sum()  # sẵn sàng khi pool rỗng
        within_items = within_items if within_items.size else isin
        if not within_items.size:
            within_items = isin
            within_weights = pop_all

        outside_mask = ~within_mask
        outside_items = isin[outside_mask]
        outside_weights = pop_all[outside_mask]
        outside_weights = outside_weights / outside_weights.sum()
        if not outside_items.size:
            outside_items = isin
            outside_weights = pop_all

        n_expl = int(min(EXPLORATION_CAP, max(0, int(rng.binomial(n_clicks,
                                                                  1.0 - WITHIN_PERSONA_PROB)))))
        n_within = n_clicks - n_expl

        chosen: set[int] = set()
        for pool, weights, quota in (
                (within_items, within_weights, n_within),
                (outside_items, outside_weights, n_expl)):
            for _ in range(quota):
                iid = None
                for _retry in range(6):
                    cand = int(rng.choice(pool, p=weights))
                    if cand not in chosen:
                        iid = cand
                        break
                if iid is not None:
                    chosen.add(iid)

        for iid in sorted(chosen):   # sorted -> ổn định thứ tự các lượt trong lịch sử user
            rows.append((uid, iid))

    df = pd.DataFrame(rows, columns=["user_id", "item_id"])
    df = df.sort_values(["user_id"], kind="stable").reset_index(drop=True)
    df.attrs["seed"] = seed
    df.attrs["n_users_target"] = n_users
    df.attrs["min_history"] = MIN_HISTORY
    return df


def user_meets_min_history(df: pd.DataFrame) -> pd.DataFrame:
    """Chỉ giữ user có đủ lịch sử — điều kiện CHÚT CHÚT của build_cf (>= MIN_HISTORY)."""
    counts = df.groupby("user_id").size()
    keep = counts[counts >= MIN_HISTORY].index
    return df[df["user_id"].isin(keep)].reset_index(drop=True)


def write_interactions(df: pd.DataFrame, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
    print(f"-> {path}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-users", type=int, default=1800,
                    help="Số user mô phỏng (mặc định 1800)")
    ap.add_argument("--seed", type=int, default=7, help="Seed tái lập (mặc định 7)")
    ap.add_argument("--avg-per-user", type=float, default=25.0,
                    help="Trung bình số item/user (gamma)")
    ap.add_argument("--out", default=None,
                    help="File CSV ghi tương tác (mặc định ITLR_INTERACTIONS_CSV)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Chỉ in thống kê, KHÔNG ghi file")
    args = ap.parse_args()

    items = pd.read_csv(config.ITEMS_CSV)
    df = generate_interactions(items, n_users=args.n_users, seed=args.seed,
                               avg_per_user=args.avg_per_user)
    df = user_meets_min_history(df)

    sizes = df.groupby("user_id").size()
    cats = df.merge(items[["item_id", "category"]], on="item_id").groupby("user_id")[
        "category"].nunique()
    n_u = df["user_id"].nunique()
    print(f"Tương tác MÔ PHỎNG: {len(df)} lượt click · {n_u} users (seed={args.seed}, "
          f"target={args.n_users})")
    print(f"  lịch sử/user: TB {sizes.mean():.1f} | P50 {sizes.median():.0f} | "
          f"P90 {sizes.quantile(0.9):.0f} | max {sizes.max()}")
    print(f"  chuyên mục/user: TB {cats.mean():.2f} (persona TẬP TRUNG)")
    if args.dry_run:
        print("[dry-run] KHÔNG ghi file thật.")
        return 0
    out = args.out or str(config.INTERACTIONS_CSV)
    write_interactions(df, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
