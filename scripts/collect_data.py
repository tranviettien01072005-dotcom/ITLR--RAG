"""Thu thập dữ liệu CNTT (crawl) — MỘT LỆNH, log rõ, tổng kết rc trung thực.

    python scripts/collect_data.py                # chạy toàn bộ nguồn trong config
    python scripts/collect_data.py --sources devto-python,freecodecamp-news
    python scripts/collect_data.py --sources help # liệt kê danh sách nguồn

Cấu hình nguồn: configs/collect.sources.json (appi/rss/web; license; full-text policy).
Chỉ crawl nguồn ĐƯỢC PHÉP: kiểm robots.txt trước khi fetch; Crawl-delay; retry/backoff.
SQLite: var/data/collect/crawl.db — chống trùng/ cập nhật thay đổi, provenance đầy đủ.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from itlr import config
from itlr.collect.http import HttpFetcher, RateLimiter, RobotsCtx
from itlr.collect.runner import CollectRunner
from itlr.collect.sources import load_sources
from itlr.collect.store import CollectStore

LOG = logging.getLogger("itlr.collect")


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    # httpx chắc chắn không spam INFO mỗi request
    logging.getLogger("httpx").setLevel(logging.WARNING)


def list_sources() -> int:
    ss = load_sources()
    print("Nguồn khả dụng (configs/collect.sources.json):")
    for s in ss.sources:
        txt_mode = "FULL-TEXT" if s.full_text_allowed else "snippet-only"
        print(f"  - {s.source_id:<22} {s.kind:<4} {txt_mode:<12} "
              f"license: {s.license[:40]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", default=None,
                    help="Chỉ chạy các source này (dấu phẩy); 'help' để liệt kê")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--stats-only", action="store_true",
                    help="Chỉ in tổng kết SQLite rồi thoát")
    args = ap.parse_args()

    setup_logging(args.verbose)

    if getattr(args, "sources", None) and "help" == args.sources.strip().lower():
        return list_sources()

    try:
        only = None if not args.sources else {s.strip() for s in args.sources.split(",")}
        ss = load_sources(only=only)
    except Exception as exc:  # noqa: BLE001
        LOG.error("Cấu hình nguồn lỗi: %s", exc)
        return 2

    LOG.info("[i] Cấu hình: %s | DB: %s", [s.source_id for s in ss.sources],
             config.COLLECT_DB)
    store = CollectStore(config.COLLECT_DB)

    if args.stats_only:
        print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
        store.close()
        return 0

    fetcher = HttpFetcher(
        timeout_connect=15.0, request_timeout=30.0, max_retries=3,
        rate_limiter=RateLimiter(min_interval=3.0, jitter=0.5),
        robots=RobotsCtx(timeout=10.0))
    try:
        runner = CollectRunner(ss, fetcher=fetcher, store=store)
        stats = runner.run()
    finally:
        fetcher.close() if hasattr(fetcher, "close") else None

    stats["store"] = store.stats()
    out_path = Path(config.COLLECT_DIR) / "last_run.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    store.close()

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    new_total = stats["totals"]["new"]
    err_total = sum(1 for s in stats["sources"].values() if "error" in s)
    if err_total == len(stats["sources"]):
        print("[!] TẤT CẢ nguồn lỗi — rc=1")
        return 1
    print(f"[OK] Lượt thu thập xong: {new_total} mới, rc=0 "
          f"(tổng kết: last_run.json, stats: {out_path})")
    return 0


if __name__ == "__main__":
    from itlr.locking import file_lock
    with file_lock(config.DATA_DIR / ".pipeline.lock"):
        sys.exit(main())
