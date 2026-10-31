"""Frozen blind-case evaluation over all 20 cases with the current tree.

Inherits: dataset SHA pinned, budget 45s, no tuning, human score fields stay null.
Output: /tmp/opencode/itlr-e2e/generation-eval.json + human-review-packet.jsonl
"""
import asyncio, hashlib, json, os, sys, time
from contextlib import aclosing
from pathlib import Path

ROOT = Path('/home/o/ITLR--RAG')
sys.path.insert(0, str(ROOT))
OUT = Path('/tmp/opencode/itlr-e2e')

for key in ('DEEPSEEK_API_KEY', 'OPENAI_API_KEY'):
    os.environ.pop(key, None)
os.environ.update(
    ITLR_ARTIFACTS_DIR='/tmp/opencode/itlr-e2e/artifacts',
    HF_HOME=str(ROOT / 'var/hf'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
    USE_OLLAMA='1', OLLAMA_MODEL='qwen2.5:3b',
    OLLAMA_BASE_URL='http://127.0.0.1:11434', OLLAMA_TIMEOUT='45',
    DISABLE_RERANKER='1', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
    OPENBLAS_NUM_THREADS='1')

from itlr.engine import load_engine

p = ROOT / 'reports/release-readiness-evidence/blind_cases.jsonl'
sha = hashlib.sha256(p.read_bytes()).hexdigest()
assert sha == '2a3a98e2d207b7c4932ced6ec87b3d7db9668c8b543730545e9a76d10abe6dd1', sha
cases = [json.loads(x) for x in p.read_text().splitlines()]
engine = load_engine()
rows = []

async def main():
    for idx, case in enumerate(cases):
        started = time.perf_counter()
        events = []
        first = None
        try:
            async with aclosing(engine.achat_stream(case['query'])) as response:
                async for kind, data in response:
                    if kind == 'text' and first is None:
                        first = time.perf_counter() - started
                    events.append({'type': kind, 'data': data})
        except Exception as exc:
            events.append({'type': 'error', 'data': repr(exc)})
        final = next((e['data'] for e in events if e['type'] == 'final'), None)
        rows.append({
            'id': case['id'], 'kind': case['kind'], 'query': case['query'],
            'seconds': round(time.perf_counter() - started, 3), 'ttft_s': first,
            'events': events, 'final': final,
            'human_groundedness': None, 'human_hallucination': None,
            'human_answer_relevance': None,
        })
        f = final or {}
        print(case['id'], rows[-1]['seconds'], f.get('generation_mode'),
              (f.get('citation_validation') or {}).get('status'),
              f.get('generation_error'), flush=True)
        doc = {'dataset_sha256': sha, 'dataset_author': 'frozen AI author, not human labels',
               'model': 'qwen2.5:3b', 'budget_s': 45, 'cases': rows,
               'scope': 'current engine async stream, sequential shared-daemon evaluation; no policy tuning'}
        (OUT / 'generation-eval.json').write_text(
            json.dumps(doc, ensure_ascii=False, indent=2))
        with (OUT / 'human-review-packet.jsonl').open('w') as fh:
            for row in rows:
                f2 = row['final'] or {}
                fh.write(json.dumps({
                    'id': row['id'], 'query': row['query'],
                    'response': f2.get('response'),
                    'provisional_model_text': ''.join(e['data'] for e in row['events'] if e['type'] == 'text'),
                    'generation_error': f2.get('generation_error'),
                    'sources': f2.get('sources', []),
                    'reviewer_id': None, 'claim_support': None,
                    'answer_relevance': None, 'refusal_appropriate': None, 'notes': None,
                    'generation_mode': f2.get('generation_mode'),
                }, ensure_ascii=False) + '\n')

asyncio.run(main())
print('ALL DONE', flush=True)
