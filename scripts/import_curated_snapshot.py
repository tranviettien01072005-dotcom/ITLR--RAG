"""Restore vetted real-source snapshot without network calls or modifying legacy CSV."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from itlr import config
from itlr.collect.store import CollectStore, utcnow
from itlr.collect.sources import Source
from itlr.collect.url_util import content_key, normalize_url
from scripts.collect_curated import selected_urls


def validate_row(row, allowed):
    url=normalize_url(row['link'])
    if url not in allowed or row['origin']!='crawl:'+allowed[url]['source_id']:
        raise ValueError('Snapshot source is outside curated allowlist')
    if hashlib.sha256(row['full_text'].encode()).hexdigest()!=row.get('snapshot_text_sha256',row['crawl_hash']):
        raise ValueError('Snapshot content hash mismatch')
    if row['crawl_license']!=allowed[url]['license']:
        raise ValueError('Snapshot license mismatch')
    return allowed[url]


def main():
    manifest=json.loads((ROOT/'configs/curated.resources.json').read_text())
    allowed={normalize_url(url):s for s,url in selected_urls(manifest)}
    rows=[json.loads(line) for line in (ROOT/'data/curated_resources.jsonl').read_text().splitlines()]
    for row in rows:validate_row(row,allowed)
    store=CollectStore(config.COLLECT_DB)
    try:
        for row in rows:
            s=validate_row(row,allowed);url=row['link'];key=content_key(url)
            store.upsert_source(Source(s['source_id'],'web',s['source_id'],s['author'],s['base_url'],True,s['license']).as_dict())
            store.upsert_doc(dict(content_key=key,source_id=s['source_id'],external_id=url,url=url,norm_url=url,
                title=row['title'],description=row['description'],text=row['full_text'],tags=row['topics'],author=row['instructor'],
                published_at=row['source_updated_at'],lang=row['crawl_lang'],license=row['crawl_license'],full_text_allowed=1,
                content_hash=row['crawl_hash'],n_chars=len(row['full_text']),quality_status='ok',status='active',fetched_at=row['source_fetched_at']))
            with sqlite3.connect(config.COLLECT_DB) as conn:
                old=conn.execute('SELECT item_id FROM item_map WHERE item_key=?',(key,)).fetchone()
                if old and old[0]!=int(row['item_id']):raise ValueError('Existing stable item ID conflicts with snapshot')
                conn.execute('INSERT INTO item_map(item_key,item_id,created_at) VALUES(?,?,?) ON CONFLICT(item_key) DO NOTHING',(key,int(row['item_id']),utcnow()))
    finally:store.close()
    print(f'Restored {len(rows)} real sources with stable IDs')

if __name__=='__main__':main()
