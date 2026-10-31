"""Catalog export refresh/verify tests (synthetic fixtures only; no real crawl data)."""
import csv
import json
from pathlib import Path

import pytest

from scripts import export_web_catalog


HEADER = export_web_catalog.COLS


def _write(path: Path, rows: list[dict]) -> None:
    with path.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER + ['full_text'], extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def _row(item_id: int, title: str, origin: str = 'crawl:fixture') -> dict:
    return {'item_id': item_id, 'title': title, 'type': 'Tài liệu', 'level': 'Cơ bản',
            'description': f'{title} description', 'category': 'DevOps', 'topics': 'docker',
            'instructor': 'Fixture', 'platform': 'Fixture', 'link': f'https://example.test/{item_id}',
            'origin': origin, 'crawl_license': 'CC-BY-4.0', 'crawl_lang': 'en',
            'crawl_hash': 'a' * 64, 'source_updated_at': '', 'source_fetched_at': '',
            'full_text': f'{title} body'}


def test_export_refuses_to_overwrite_without_refresh(tmp_path):
    source, dest = tmp_path / 'source.csv', tmp_path / 'web.csv'
    _write(source, [_row(5001, 'Old')])
    _write(dest, [_row(5000, 'Existing')])
    with pytest.raises(FileExistsError):
        export_web_catalog.export(source=source, dest=dest, snapshot=tmp_path / 'snap.jsonl')


def test_refresh_updates_crawl_rows_adds_new_and_keeps_community_rows(tmp_path):
    source, dest = tmp_path / 'source.csv', tmp_path / 'web.csv'
    snapshot = tmp_path / 'snap.jsonl'
    _write(source, [_row(5001, 'Updated title'), _row(5002, 'New real item')])
    _write(dest, [_row(5001, 'Stale title'), _row(9000, 'Community upload', origin=''),
                  _row(9999, 'Other docs', origin='')])
    exported = export_web_catalog.export(source=source, dest=dest, snapshot=snapshot, refresh=True)
    rows = list(csv.DictReader(dest.open(newline='')))
    by_id = {int(r['item_id']): r for r in rows}
    assert exported == 2
    assert by_id[5001]['title'] == 'Updated title'      # refreshed, not duplicated
    assert by_id[5002]['title'] == 'New real item'      # new real row added
    assert by_id[9000]['title'] == 'Community upload'   # community row preserved
    assert by_id[9999]['title'] == 'Other docs'
    assert len(rows) == len(by_id)                       # no duplicate ids
    assert not list(tmp_path.glob('*.tmp'))
    assert len(snapshot.read_text().splitlines()) == 2
    snap = json.loads(snapshot.read_text().splitlines()[0])
    assert snap['snapshot_text_sha256']


def test_refresh_drops_stale_crawl_rows_but_never_community_rows(tmp_path):
    source, dest = tmp_path / 'source.csv', tmp_path / 'web.csv'
    _write(source, [_row(5002, 'Current')])
    _write(dest, [_row(5001, 'Removed from source'), _row(9000, 'Community', origin='')])
    export_web_catalog.export(source=source, dest=dest, snapshot=tmp_path / 's.jsonl', refresh=True)
    ids = {int(r['item_id']) for r in csv.DictReader(dest.open(newline=''))}
    assert ids == {5002, 9000}
