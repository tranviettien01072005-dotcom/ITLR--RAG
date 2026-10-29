"""Export a real-only catalog with provenance for PostgreSQL COPY and reproducible snapshot."""
import csv
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from itlr import config

COLS=['item_id','title','type','level','description','category','topics','instructor','platform','link',
      'origin','crawl_license','crawl_lang','crawl_hash','source_updated_at','source_fetched_at']

def export(source=None, dest=None):
    source=Path(source or config.DATA_DIR/'itlr_v2_items.csv')
    dest=Path(dest or config.DATA_DIR/'web_items.csv')
    with source.open(newline='') as handle:
        rows=[r for r in csv.DictReader(handle) if r.get('origin','').startswith('crawl:')]
    if not rows:
        raise ValueError('No real collected resources; refusing synthetic product export')
    with dest.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=COLS,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    snapshot=ROOT/'data/curated_resources.jsonl';snapshot.parent.mkdir(exist_ok=True)
    snapshot_rows = [{**r, 'snapshot_text_sha256': hashlib.sha256(r['full_text'].encode()).hexdigest()} for r in rows]
    snapshot.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in snapshot_rows))
    print(f'Exported {len(rows)} real resources to {dest}')
    return len(rows)

if __name__=='__main__':export()
