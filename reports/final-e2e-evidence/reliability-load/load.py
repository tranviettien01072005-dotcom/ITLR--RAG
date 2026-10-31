"""Reliability/capacity probe for the isolated ITLR Docker staging stack.

Talks only to 127.0.0.1:19081 (API). No production touch, no artifact activation.
Modes: health, conc, soak, cancel, timeout, rss.
"""
import argparse
import json
import statistics
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'http://127.0.0.1:19081'
OUT = Path('/tmp/opencode/itlr-reliability')
OUT.mkdir(exist_ok=True)
QUERY = 'What does HTTP 404 mean?'
SQL_QUERY = 'docker compose --project-name itlr-resume-1031c --file /tmp/opencode/itlr-docker-fresh/compose.yml'


def post(path, payload, timeout=180):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
        return {'ok': True, 'status': 200, 'wall': round(time.monotonic() - started, 3), 'body': body.decode('utf-8', 'replace')[:2000]}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'status': e.code, 'wall': round(time.monotonic() - started, 3), 'body': e.read().decode('utf-8','replace')[:2000]}
    except Exception as e:
        return {'ok': False, 'status': None, 'wall': round(time.monotonic() - started, 3), 'error': repr(e)}


def health():
    started = time.monotonic()
    with urllib.request.urlopen(BASE + '/health', timeout=30) as r:
        body = json.loads(r.read())
    return round(time.monotonic() - started, 3), body


def stream_chat(query, timeout=180, cancel_after=None):
    """SSE chat; returns first-event latency, total, event types."""
    payload = json.dumps({'message': query}).encode()
    req = urllib.request.Request(BASE + '/api/chat/stream', data=payload,
                                 headers={'Content-Type': 'application/json', 'Accept': 'text/event-stream'})
    started = time.monotonic()
    types, ttft, closed = [], None, False
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if cancel_after is not None:
                def watchdog():
                    time.sleep(cancel_after)
                    try:
                        r.close()
                    except Exception:
                        pass
                threading.Thread(target=watchdog, daemon=True).start()
            while True:
                try:
                    line = r.readline()
                except Exception:
                    closed = True
                    break
                if not line:
                    break
                if line.startswith(b'data:'):
                    try:
                        ev = json.loads(line[5:])
                    except ValueError:
                        continue
                    types.append(ev.get('type'))
                    if ttft is None:
                        ttft = round(time.monotonic() - started, 3)
    except Exception as e:
        return {'ok': False, 'error': repr(e), 'types': types, 'wall': round(time.monotonic() - started, 3)}
    return {'ok': True, 'ttft': ttft, 'wall': round(time.monotonic() - started, 3),
            'types': types, 'terminal': types[-1] if types else None, 'cancelled_early': closed}


def run_parallel(fn, n):
    results = [None] * n
    def wrap(i):
        results[i] = fn()
    threads = [threading.Thread(target=wrap, args=(i,)) for i in range(n)]
    started = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return {'wall': round(time.monotonic() - started, 3), 'results': results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['health', 'conc', 'soak', 'cancel', 'rss', 'timeout'])
    ap.add_argument('--n', type=int, default=1)
    ap.add_argument('--seconds', type=int, default=180)
    args = ap.parse_args()
    report = {'mode': args.mode, 'started': time.strftime('%Y-%m-%dT%H:%M:%S'), 'n': args.n}

    if args.mode == 'health':
        report['health'] = health()

    elif args.mode == 'conc':
        chat = run_parallel(lambda: stream_chat(QUERY), args.n)
        search = run_parallel(lambda: post('/api/search', {'query': 'docker volumes', 'min_pct': 84}), args.n)
        report['chat'] = chat
        report['search'] = search
        ok = [r for r in chat['results'] if r and r.get('ok')]
        report['chat_summary'] = {
            'completed': len(ok),
            'p50_wall': round(statistics.median([r['wall'] for r in ok]), 2) if ok else None,
            'max_wall': max((r['wall'] for r in ok), default=None),
            'timeouts': sum(1 for r in chat['results'] if r and not r.get('ok')),
            'terminal_types': [r.get('terminal') for r in chat['results'] if r],
        }

    elif args.mode == 'soak':
        end = time.monotonic() + args.seconds
        seq = 0
        rows = []
        while time.monotonic() < end:
            row = {'seq': seq, 'search': post('/api/search', {'query': 'python context manager', 'min_pct': 84})['wall']}
            if seq % 2 == 0:
                row['chat'] = stream_chat('What does HTTP 404 mean?')
            rows.append(row)
            seq += 1
        report['requests'] = rows
        chats = [r['chat'] for r in rows if r.get('chat')]
        report['summary'] = {
            'iterations': len(rows),
            'chats': len(chats),
            'chat_ok': sum(1 for c in chats if c.get('ok')),
            'chat_p50': round(statistics.median([c['wall'] for c in chats if c.get('ok')]), 2) if chats else None,
            'chat_max': max((c['wall'] for c in chats if c.get('ok')), default=None),
            'terminal_types': [c.get('terminal') for c in chats],
        }

    elif args.mode == 'cancel':
        report['chat'] = stream_chat('Why must Dockerfile parser directives appear before comments? cancelled probe', cancel_after=3)
        time.sleep(1)
        report['health_after'] = health()

    elif args.mode == 'timeout':
        started = time.monotonic()
        r = stream_chat('I need a Python UUID but want to avoid embedding my computer’s network address. How do uuid1() and uuid4() differ here?', timeout=120)
        r['observed_max'] = round(time.monotonic() - started, 3)
        report['chat'] = r

    elif args.mode == 'rss':
        import subprocess
        p = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'],
                           capture_output=True, text=True)
        report['stats'] = [line for line in p.stdout.splitlines() if 'itlr-resume-1031c' in line]

    report['finished'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    path = OUT / f'{args.mode}-n{args.n}.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False)[:2000])
    print('saved', path)


if __name__ == '__main__':
    main()
