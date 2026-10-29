import json
from pathlib import Path
import pytest
from scripts.collect_curated import selected_urls, parse_page

def test_curated_urls_are_bounded_official_allowlist():
    manifest=json.loads(Path('configs/curated.resources.json').read_text())
    assert 100<=len(selected_urls(manifest))<=300
    manifest['sources'][0]['paths']=['https://evil.example/']
    with pytest.raises(ValueError):selected_urls(manifest)

def test_source_parser_uses_real_extractor_metadata_keys():
    title,text=parse_page('<html><head><title>Python Lists</title></head><body><main><h1>Lists</h1><p>'+('Real source content. '*30)+'</p></main></body></html>',12000)
    assert 'Python Lists' in title
    assert 'Real source content.' in text

def test_snapshot_content_and_origin_are_verified():
    import hashlib
    from scripts.import_curated_snapshot import validate_row
    row=dict(link='https://docs.python.org/3/tutorial/introduction.html',origin='crawl:python-official',full_text='Source',crawl_license='PSF',crawl_hash=hashlib.sha256(b'Source').hexdigest())
    allowed={row['link']:dict(source_id='python-official',license='PSF')}
    assert validate_row(row,allowed)['source_id']=='python-official'
    row['full_text']='tampered'
    with pytest.raises(ValueError,match='hash'):validate_row(row,allowed)
