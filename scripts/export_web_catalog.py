"""Export a real-only catalog with provenance for PostgreSQL COPY and reproducible snapshot.

`--refresh` merges the freshly built crawl catalog into an existing Web catalog:
- real rows from the build are added/updated,
- community rows appended by the Web app are preserved,
- stale crawl rows (no longer in the build) are dropped from the CSV; PostgreSQL sync
  never deletes rows, so user data/enrollments are untouched.

Default behaviour stays no-clobber to protect Web-appended community rows.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from itlr import config  # noqa: E402

COLS = ['item_id', 'title', 'type', 'level', 'description', 'category', 'topics', 'instructor',
        'platform', 'link', 'origin', 'crawl_license', 'crawl_lang', 'crawl_hash',
        'source_updated_at', 'source_fetched_at']

def _is_community(row: dict) -> bool:
    """Rows the Web app appended have no origin or a non-crawl origin."""
    return not (row.get('origin') or '').strip().startswith('crawl:')


def _read_rows(path: Path) -> list[dict]:
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def _write_atomic(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    try:
        with tmp.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=COLS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _merge(existing: list[dict], fresh: list[dict]) -> list[dict]:
    fresh_ids = {str(r['item_id']) for r in fresh}
    kept = [r for r in existing
            if _is_community(r) and str(r.get('item_id')) not in fresh_ids]
    merged = fresh + kept
    merged.sort(key=lambda r: int(r['item_id']))
    return merged


def export(source=None, dest=None, snapshot=None, refresh=False):
    """Write the Web catalog. Returns the number of real (crawl) rows exported."""
    source = Path(source or config.DATA_DIR / 'itlr_v2_items.csv')
    dest = Path(dest or config.DATA_DIR / 'web_items.csv')
    snapshot = Path(snapshot or ROOT / 'data/curated_resources.jsonl')
    with source.open(newline='') as handle:
        real_rows = [r for r in csv.DictReader(handle) if r.get('origin', '').startswith('crawl:')]
    if not real_rows:
        raise ValueError('No real collected resources; refusing synthetic product export')

    rows = real_rows
    if dest.exists():
        # Web appends community resources to this file; never truncate them.
        if not refresh:
            raise FileExistsError(
                f'{dest} already exists; pass refresh=True/--refresh to merge real rows '
                'while preserving community rows')
        rows = _merge(_read_rows(dest), real_rows)

    _write_atomic(dest, rows)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot_rows = [{**r, 'snapshot_text_sha256': hashlib.sha256(r['full_text'].encode()).hexdigest()}
                     for r in real_rows if r.get('full_text')]
    if snapshot_rows:
        snapshot.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n'
                                    for r in snapshot_rows))
    print(f'Exported {len(real_rows)} real resources to {dest} ({len(rows)} rows total)')
    return len(real_rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', type=Path, default=None)
    ap.add_argument('--dest', type=Path, default=None)
    ap.add_argument('--snapshot', type=Path, default=None)
    ap.add_argument('--refresh', action='store_true',
                    help='merge into an existing catalog, preserving community rows')
    args = ap.parse_args(argv)
    try:
        export(source=args.source, dest=args.dest, snapshot=args.snapshot, refresh=args.refresh)
    except (FileExistsError, ValueError) as exc:
        print(f'[LỖI] {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
