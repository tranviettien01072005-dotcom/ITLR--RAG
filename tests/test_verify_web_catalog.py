"""Catalog-vs-artifact verification tests (synthetic fixtures)."""
from pathlib import Path

from scripts import verify_web_catalog


def _row(item_id, origin='crawl:fixture', link='https://example.test/x'):
    return {'item_id': str(item_id), 'title': f'item {item_id}', 'origin': origin, 'link': link}


def test_reports_missing_ids_and_broken_links(tmp_path):
    source = tmp_path / 'source.csv'
    web = tmp_path / 'web.csv'
    source.write_text('item_id\n5001\n5002\n')
    report = verify_web_catalog.compare([_row(5001), _row(5002)],
                                        [_row(5001, link='javascript:alert(1)')])
    assert report['missing'] == ['5002']
    assert report['invalid_links'] == ['5001']
    assert report['ok'] is False


def test_duplicate_ids_and_stale_crawl_rows(tmp_path):
    report = verify_web_catalog.compare(
        [_row(5001)],
        [_row(5001), _row(5001), _row(5000)],
    )
    assert report['duplicate_ids'] == ['5001']
    assert report['stale_crawl'] == ['5000']
    assert report['ok'] is False


def test_community_rows_are_not_treated_as_missing(tmp_path):
    report = verify_web_catalog.compare(
        [_row(5001)],
        [_row(5001), _row(9000, origin='', link='')],
    )
    assert report['missing'] == []
    assert report['invalid_links'] == []
    assert report['ok'] is True
