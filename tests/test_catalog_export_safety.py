"""Export must not truncate a catalog receiving community uploads."""
import csv

import pytest

from scripts import export_web_catalog as exporter


def test_export_refuses_existing_destination_without_modifying_it(tmp_path, monkeypatch):
    monkeypatch.setattr(exporter, 'ROOT', tmp_path)
    source = tmp_path / 'source.csv'
    with source.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['item_id', 'origin', 'full_text'])
        writer.writeheader()
        writer.writerow({'item_id': 1, 'origin': 'crawl:docs', 'full_text': 'source'})
    dest = tmp_path / 'web_items.csv'
    original = b'item_id,title\n9001,Community upload\n'
    dest.write_bytes(original)
    with pytest.raises(FileExistsError):
        exporter.export(source, dest)
    assert dest.read_bytes() == original
    assert not (tmp_path / 'data' / 'curated_resources.jsonl').exists()


def test_export_to_new_destination_keeps_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(exporter, 'ROOT', tmp_path)
    source = tmp_path / 'source.csv'
    with source.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['item_id', 'origin', 'full_text'])
        writer.writeheader()
        writer.writerow({'item_id': 1, 'origin': 'crawl:docs', 'full_text': 'source'})
    dest = tmp_path / 'new.csv'
    assert exporter.export(source, dest) == 1
    with dest.open() as handle:
        assert list(csv.DictReader(handle))[0]['origin'] == 'crawl:docs'
