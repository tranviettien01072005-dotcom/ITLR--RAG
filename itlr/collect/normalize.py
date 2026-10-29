"""Chuẩn hóa dữ liệu thu thập (SQLite) → schema ITLR — KHÔNG bịa dữ liệu.

Nguyên tắc:
- item_id ỔN ĐỊNH: sinh từ item_map (khóa bền vững theo URL) — giữa các lần chạy,
  item không đổi ID (trích dẫn [item_id:...] không hỏng).
- Cột chỉ nhận từ dữ liệu THẬT của nguồn: title/description/text, author, platform,
  link (URL chuẩn hóa), tags→topics. Category PHÂN LOẠI theo từ khóa cấu hình sẵn
  (latin/vietsừ khóa); level/type lấy nhãn trung tính của cấu hình nguồn.
- Thêm cột provenance (origin/license/lang) để minh bạch nguồn gốc từng item.
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import pandas as pd

from itlr import config
from itlr.collect.chunk import chunk_text
from itlr.collect.quality import content_hash, title_similarity
from itlr.collect.store import CollectStore
from itlr.collect.url_util import content_key, normalize_url

LOG = logging.getLogger("itlr.collect")

# Ánh xạ từ khóa (viết thường) → category ITLR (CHỈ dùng category có thật trong
# catalog hiện có — không tự sáng tạo chủ đề). So khớp theo thứ tự, trúng đầu thì dừng.
CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
    (("docker", "kubernetes", "ci/cd", "ci cd", "devops", "jenkins", "terraform",
      "github actions"), "DevOps"),
    (("machine learning", "deep learning", "neural", "artificial intelligence", "ai",
     "trí tuệ nhân tạo", "llm", "transformer", "embedding", "gpt", "reinforcement"),
     "Trí tuệ nhân tạo"),
    (("python", "javascript", "typescript", "rust", "golang", "lập trình",
     "programming", "c++", "c#", "java", "go"), "Lập trình"),
    (("react", "angular", "vue", "frontend", "css", "html", "web", "next.js", "svelte",
     "tailwind"), "Lập trình Web"),
    (("sql", "postgres", "mysql", "mongodb", "redis", "database", "nosql",
     "cơ sở dữ liệu"), "Cơ sở dữ liệu"),
    (("security", "bảo mật", "an ninh mạng", "breach", "phishing", "penetration",
     "pentest", "auth0", "hashing", "malware"), "An ninh mạng"),
    (("aws", "azure", "gcp", "cloud", "điện toán đám mây", "serverless"),
     "Điện toán đám mây"),
    (("linux", "ubuntu", "shell", "bash", "zsh", "ssh", "sysadmin", "nginx"),
     "Quản trị hệ thống & Linux"),
    (("data science", "khoa học dữ liệu", "pandas", "statistics", "thống kê",
     "visualization", "dashboard"), "Khoa học dữ liệu"),
    (("android", "ios", "flutter", "mobile", "swift", "kotlin"), "Lập trình Mobile"),
    (("blockchain", "web3", "ethereum", "crypto", "smart contract", "solidity"),
     "Blockchain & Web3"),
    (("test", "kiểm thử", "unit test", "e2e", "pytest", "jest"), "Kiểm thử phần mềm"),
    (("mlops", "ai engineering", "airflow", "model", "kaggle"), "MLOps & AI Engineering"),
    (("kafka", "stream", "big data", "hadoop", "dữ liệu lớn", "spark", "etl"),
     "Dữ liệu lớn"),
    (("network", "mạng", "tcp", "dns", "routing", "vpn"), "Mạng máy tính"),
]


def _rule_regex(key: str):
    """Regex khớp WHOLE-WORD cho từng từ khóa (không trúng giữa từ: 'explain' ≠ 'ai')."""
    return re.compile(rf"(?<![a-z\d]){re.escape(key)}(?![a-z\d])", re.IGNORECASE)


def classify_category(text: str, extra_topics: str = "") -> str | None:
    """Dò từ khóa theo thứ tự RULES; trả None nếu không trúng (caller dùng nhãn mặc định)."""
    hay = f"{(extra_topics or '')} {text or ''}".lower()
    for keys, category in CATEGORY_RULES:
        for k in keys:
            if not k:
                continue
            if _rule_regex(k).search(hay):
                return category
    return None


def _chunk_stats(text: str) -> tuple[int, list[str]]:
    chunks = chunk_text(text or "", max_chars=900, overlap_chars=120)
    return len(chunks), chunks


def assemble_itlr_items(max_items=None, source_ids=None) -> pd.DataFrame:
    """docs (SQLite, full_text ok) → DataFrame schema ITLR + item_id ổn định."""
    store = CollectStore(config.COLLECT_DB)
    floor = _legacy_floor_id()
    if floor > 0:
        store.set_item_floor(floor)  # item_id crawl bắt đầu sau catalog legacy
    docs = store.docs_for_index(source_ids=source_ids)
    if max_items:
        docs = docs[: int(max_items)]
    rows = []
    for d in docs:
        item_key = d["content_key"] if d["content_key"] else content_key(d["url"])
        item_id, _new = store.assign_item_id(item_key)
        text_full = (d["text"] or "").strip()
        description = (d["description"] or "").strip()
        # nội dung mô tả: dùng đoạn đầu của văn bản thật (không bịa), cắt vừa đủ gọn
        if not description and text_full:
            description = text_full[:800]
        elif text_full and len(description) < 300:
            description = (description + " " + text_full[:600])[:1400]
        topics = (d.get("tags") or "").replace("\t", ", ").strip() \
            if d.get("tags") else ""
        category = classify_category(f"{d['title']} {description}", topics)
        rows.append({
            "item_id": item_id,
            "title": d["title"],
            "type": "Tài liệu",
            "level": "Trung cấp",
            "description": description,
            "category": category or "Khoa học máy tính",
            "topics": topics,
            "instructor": d["author"] or d["source_id"],
            "platform": _platform_name(store, d["source_id"]),
            "link": d["norm_url"],
            # — provenance (không thuộc schema gốc, giữ cho minh bạch) —
            "origin": f"crawl:{d['source_id']}",
            "crawl_license": d["license"],
            "crawl_lang": d["lang"],
            "crawl_hash": d["content_hash"][:16],
        })
    store.close()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # chống trùng nội bộ (title like) cho chắc chắn trước khi into index
    df["_title_norm"] = df["title"].str.strip().str.lower()
    keep_mask = ~df["_title_norm"].duplicated()
    df = df.loc[keep_mask].drop(columns="_title_norm").reset_index(drop=True)
    LOG.info("Assemble: %d items từ SQLite (%d docs hợp lệ)", len(df), len(docs))
    return df


def _legacy_floor_id() -> int:
    """item_id lớn nhất của catalog legacy (CSV) — ID mới bắt đầu sau số đó."""
    if not Path(config.ITEMS_CSV).is_file():
        return 0
    try:
        df = pd.read_csv(config.ITEMS_CSV, usecols=["item_id"])
        return int(df["item_id"].max() or 0)
    except Exception:  # noqa: BLE001
        return 0


PROVENANCE_COLS = ["origin", "crawl_license", "crawl_lang", "crawl_hash"]


def build_catalog_v2(out_path=None, max_items=None, source_ids=None) -> pd.DataFrame:
    """GHÉP catalog legacy (floor, nhãn synthetic) + crawl (real) → catalog V2 dùng build.

    Chống trùng với legacy: URL chuẩn hóa trùng hoặc tiêu đề quá khớp (≥0.8)
    → BỎ item crawl (floor legacy thì giữ nguyên — item_id ổn định).
    Xuất CSV đầy đủ schema ITLR (12 cột gốc + provenance).
    Nếu không có CSV legacy (máy mới): build từ crawl DUY NHẤT và ghi WARNING
    (không nuốt lỗi — floor = 0, item_id bắt đầu từ 1).
    """
    legacy_path = Path(config.ITEMS_CSV)
    if legacy_path.is_file():
        legacy = pd.read_csv(legacy_path)
    else:
        LOG.warning("Không tìm thấy catalog legacy %s — catalog V2 sẽ chỉ gồm dữ liệu crawl.",
                    legacy_path)
        legacy = pd.DataFrame(columns=["item_id", "title", "type", "level", "description",
                                       "category", "topics", "instructor", "platform", "link"])
    legacy["origin"] = "legacy:synthetic"   # nhãn trung thực: catalog legacy là synthetic
    legacy["crawl_license"] = ""
    legacy["crawl_lang"] = ""
    legacy["crawl_hash"] = ""

    crawl = assemble_itlr_items(max_items=max_items, source_ids=source_ids)
    if not crawl.empty:
        keep = []
        legacy_links = {normalize_url(str(l)) for l in legacy["link"].astype(str)}
        legacy_titles = list(legacy["title"].astype(str))
        for _, row in crawl.iterrows():
            if normalize_url(str(row["link"])) in legacy_links:
                LOG.info("Chống trùng URL với legacy: %s", row["title"][:60])
                continue
            if any(title_similarity(t, row["title"]) >= 0.80 for t in legacy_titles):
                LOG.info("Chống trùng tiêu đề với legacy: %s", row["title"][:60])
                continue
            keep.append(row)
        crawl = pd.DataFrame(keep) if keep else crawl.iloc[0:0]
        if not crawl.empty:
            crawl = crawl.copy()
            crawl["item_id"] = crawl["item_id"].astype("int64")

    cols = ["item_id", "title", "type", "level", "description", "category", "topics",
            "instructor", "platform", "link"] + PROVENANCE_COLS
    if crawl.empty:
        crawl = pd.DataFrame(columns=cols)
    combo = pd.concat([legacy[cols], crawl[cols]], ignore_index=True)
    combo["item_id"] = combo["item_id"].astype("int64")
    out = Path(out_path or (config.DATA_DIR / "itlr_v2_items.csv"))
    out.parent.mkdir(parents=True, exist_ok=True)
    combo.to_csv(out, index=False)
    LOG.info("Catalog V2: %d items (legacy %d + crawl %d) → %s",
             len(combo), len(legacy), len(crawl), out)
    return combo


def _platform_name(store: CollectStore, source_id: str) -> str:
    s = store.source_row(source_id) or {}
    return s.get("platform") or source_id


def main() -> int:
    """CLI: ghép docs → catalog CSV V2 (đã chọn nguồn nguồn tăng trưởng)."""
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=sys.stdout)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="CSV xuất ra (mặc định var/data/itlr_v2_items.csv)")
    ap.add_argument("--max-items", type=int, default=None)
    ap.add_argument("--source", action="append", default=None,
                    help="Chỉ ghép nguồn này (có thể lặp)")
    args = ap.parse_args()
    df = assemble_itlr_items(max_items=args.max_items, source_ids=args.source)
    out = Path(args.out or (config.DATA_DIR / "itlr_v2_items.csv"))
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"[OK] Đã ghi {len(df)} items → {out}")
    print(df["category"].value_counts().to_string() if not df.empty else "(trống)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
