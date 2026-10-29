"""Bounded official-resource collection. No recursive links or synthetic content."""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys
from urllib.parse import urljoin, urlsplit
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from itlr import config
from itlr.collect.extract import extract_meta, extract_page_text
from itlr.collect.http import HttpFetcher, RateLimiter, RobotsCtx
from itlr.collect.sources import Source
from itlr.collect.store import CollectStore, utcnow
from itlr.collect.url_util import content_key, normalize_url


def selected_urls(manifest):
    out = []
    for source in manifest['sources']:
        base = source['base_url']
        if urlsplit(base).scheme != 'https' or urlsplit(base).hostname not in {'docs.python.org','developer.mozilla.org','docs.docker.com'}:
            raise ValueError('Only configured official HTTPS hosts are allowed')
        for path in source['paths']:
            url = urljoin(base, path)
            if not url.startswith(base) or urlsplit(url).fragment:
                raise ValueError('Resource path escaped source')
            out.append((source, url))
    if len(out) > min(300, manifest['max_pages']) or len({url for _,url in out}) != len(out):
        raise ValueError('Duplicate URLs or collection budget exceeded')
    return out


def parse_page(html, limit):
    meta = extract_meta(html)
    title = (meta.get("meta_title") or meta.get("title_html") or "").strip()
    return title, extract_page_text(html).strip()[:limit]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'configs/curated.resources.json')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    manifest = json.loads(args.config.read_text())
    pages = selected_urls(manifest)
    store = CollectStore(config.COLLECT_DB)
    fetcher = HttpFetcher(request_timeout=30, max_retries=1, rate_limiter=RateLimiter(min_interval=1,jitter=.2), robots=RobotsCtx())
    result = {'selection':manifest['selection'], 'attempted':len(pages), 'ok':[], 'failed':[], 'retrieved_at':utcnow()}
    try:
        for s in manifest['sources']:
            store.upsert_source(Source(s['source_id'],'web',s['source_id'],s['author'],s['base_url'],True,s['license']).as_dict())
        for s,url in pages:
            key = content_key(url)
            old = store.get_doc_by_key(key)
            if old and not args.refresh:
                result['ok'].append({'url':url,'hash':old['content_hash'],'cached':True})
                continue
            try:
                status,body = fetcher.fetch(url)
                if status != 200:
                    raise ValueError(f'HTTP {status}')
                html = body.decode('utf-8',errors='replace')
                meta = extract_meta(html)
                title,text = parse_page(html,manifest['max_text_chars'])
                if len(title)<4 or len(text)<200:
                    raise ValueError('Missing title/source text')
                digest = hashlib.sha256(text.encode()).hexdigest()
                store.upsert_doc(dict(content_key=key,source_id=s['source_id'],external_id=url,url=url,norm_url=normalize_url(url),title=title,
                    description=text[:600],text=text,tags=s['tags'],author=s['author'],published_at=meta.get('published_at',''),
                    lang='en',license=s['license'],full_text_allowed=1,content_hash=digest,n_chars=len(text),quality_status='ok',status='active',fetched_at=utcnow()))
                result['ok'].append({'url':url,'title':title,'hash':digest,'chars':len(text),'license':s['license']})
                print(f"[{len(result['ok'])}/{len(pages)}] {url}",flush=True)
            except Exception as exc:
                result['failed'].append({'url':url,'reason':str(exc)})
                logging.warning('Resource failed: %s (%s)',url,exc)
    finally:
        store.close()
    report = ROOT/'reports/curated_collection.json'
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(f"Collected {len(result['ok'])}; failed {len(result['failed'])}")
    return 0 if len(result['ok'])>=100 else 1

if __name__ == '__main__':
    raise SystemExit(main())
