"""Verify the Web catalog covers the freshly built RAG catalog.

Catches the 'click a course -> 404' class of bug: the RAG index contains an item that
the Web PostgreSQL catalog was never refreshed with. Also reports duplicate ids, stale
crawl rows and non-HTTP links. Community rows (no crawl origin) are ignored.

    python scripts/verify_web_catalog.py --source var/data/itlr_v2_items.csv \
        --web var/data/web_items.csv
Exit code 0 only when there are no missing ids, duplicates or invalid links.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from itlr import config  # noqa: E402


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def _id(row: dict) -> str:
    raw = str(row.get('item_id') or '').strip()
    return raw


def _is_crawl(row: dict) -> bool:
    return str(row.get('origin') or '').strip().startswith('crawl:')


def _valid_link(row: dict) -> bool:
    link = str(row.get('link') or '').strip().lower()
    return link.startswith(('http://', 'https://'))


def compare(source_rows: list[dict], web_rows: list[dict]) -> dict:
    source_ids = {_id(r) for r in source_rows if _id(r)}
    web_ids = [_id(r) for r in web_rows if _id(r)]
    web_set = set(web_ids)
    seen, duplicates = set(), []
    for item_id in web_ids:
        if item_id in seen:
            duplicates.append(item_id)
        seen.add(item_id)
    missing = sorted(source_ids - web_set, key=int)
    stale = sorted({_id(r) for r in web_rows
                    if _is_crawl(r) and _id(r) and _id(r) not in source_ids}, key=int)
    invalid = sorted({_id(r) for r in web_rows if _is_crawl(r) and not _valid_link(r)},
                     key=lambda v: int(v) if v.isdigit() else 0)
    report = {
        'source_count': len(source_ids),
        'web_count': len(web_ids),
        'missing': missing,
        'duplicate_ids': sorted(set(duplicates), key=int),
        'stale_crawl': stale,
        'invalid_links': invalid,
    }
    report['ok'] = not (report['missing'] or report['duplicate_ids'] or report['invalid_links'])
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', type=Path, default=config.DATA_DIR / 'itlr_v2_items.csv')
    ap.add_argument('--web', type=Path, default=config.DATA_DIR / 'web_items.csv')
    ap.add_argument('--json', type=Path, default=None)
    args = ap.parse_args(argv)

    if not Path(args.source).exists():
        print(f'[LỖI] Chưa có catalog nguồn: {args.source}', file=sys.stderr)
        return 2
    report = compare(_rows(args.source), _rows(args.web))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json:
        Path(args.json).write_text(text + '\n', encoding='utf-8')
    if not report['ok']:
        print(f"[LỖI] Web catalog thiếu {len(report['missing'])} item / "
              f"{len(report['duplicate_ids'])} id trùng / "
              f"{len(report['invalid_links'])} link sai. Chạy export --refresh rồi sync PostgreSQL.",
              file=sys.stderr)
        return 1
    if report['stale_crawl']:
        print(f"[i] {len(report['stale_crawl'])} item crawl cũ không còn trong build "
              "(không xóa khỏi PostgreSQL; chỉ báo cáo).")
    print('[OK] Web catalog phủ đủ item của RAG index.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
