"""Audit external source links: HTTP status, redirect target, robots policy, duplicates.

Uses the same public-URL validation and robots/rate-limit policy as the crawler, but keeps
its own HTTP client so redirect chains are observable (the ingestion fetcher only returns
a body). Never invents URLs; the input is the catalog's `link` column.

    python scripts/audit_source_links.py --csv var/data/web_items.csv --limit 50 \
        --json /tmp/link-audit.json

Exit 1 when any link is 404 or the audit hit transport errors; 0 when all reachable.
The full run is network-bound: it waits between requests to the same host.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from itlr.collect.http import RateLimiter, RobotsCtx, _validate_public_url  # noqa: E402
from itlr.collect.url_util import normalize_url  # noqa: E402
from itlr import config  # noqa: E402


@dataclass
class LinkResult:
    url: str
    status: int | None = None
    final_url: str | None = None
    redirected_to: str | None = None
    missing: bool = False
    robots_allowed: bool = True
    error: str | None = None


def _default_fetch(url: str, timeout: float) -> tuple[int, str]:
    import httpx

    _validate_public_url(url)
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        response = client.get(url)
        final = str(response.url)
        _validate_public_url(final)
        return response.status_code, final


def audit_links(urls, *, fetch=None, robots=None, throttle=None, timeout=20.0) -> list[dict]:
    """Audit unique URLs (normalized) and return plain dicts ready for JSON output."""
    fetch = fetch or (lambda url: _default_fetch(url, timeout))
    robots = robots or RobotsCtx()
    throttle = throttle or RateLimiter(min_interval=3.0, jitter=0.5)
    seen, results = set(), []
    for raw in urls:
        url = str(raw or '').strip()
        if not url:
            continue
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        allowed, delay = robots.allowed(url)
        result = LinkResult(url=url, robots_allowed=allowed)
        if not allowed:
            results.append(asdict(result))
            continue
        try:
            throttle.wait(urlsplit(url).netloc, extra_delay=delay)
            status, final_url = fetch(url)
            result.status = int(status) if status is not None else None
            result.final_url = final_url
            if normalize_url(final_url or '') != normalize_url(url):
                result.redirected_to = final_url
            result.missing = result.status == 404
        except Exception as exc:  # noqa: BLE001 — one bad link must not stop the audit
            result.error = f'{type(exc).__name__}: {exc}'
        results.append(asdict(result))
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--csv', type=Path, default=config.DATA_DIR / 'web_items.csv')
    ap.add_argument('--limit', type=int, default=0, help='0 = audit every link')
    ap.add_argument('--timeout', type=float, default=20.0)
    ap.add_argument('--json', type=Path, default=None)
    args = ap.parse_args(argv)

    if not args.csv.exists():
        print(f'[LỖI] Không thấy catalog: {args.csv}', file=sys.stderr)
        return 2
    with args.csv.open(newline='') as handle:
        links = [r.get('link', '') for r in csv.DictReader(handle)
                 if str(r.get('link') or '').lower().startswith(('http://', 'https://'))]
    if args.limit > 0:
        links = links[:args.limit]
    results = audit_links(links, timeout=args.timeout)
    missing = [r for r in results if r['missing']]
    errors = [r for r in results if r['error']]
    summary = {'checked': len(results), 'missing_404': len(missing),
               'transport_errors': len(errors),
               'redirected': sum(1 for r in results if r['redirected_to']),
               'robots_denied': sum(1 for r in results if not r['robots_allowed'])}
    payload = {'summary': summary, 'results': results}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + '\n', encoding='utf-8')
    return 1 if (missing or errors) else 0


if __name__ == '__main__':
    raise SystemExit(main())
