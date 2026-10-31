"""Controlled frozen A/B: evidence excerpt char budget None vs 800, same 20 cases.

Arm is pinned in-process (None arm monkeypatches _evidence_char_budget; 800 arm
uses the documented env override), so the arm cannot be silently wrong.
Each arm gets one untimed warmup. Human score fields stay null.
"""
import asyncio
import hashlib
import json
import os
import sys
import time
from contextlib import aclosing
from pathlib import Path

ROOT = Path('/home/o/ITLR--RAG')
sys.path.insert(0, str(ROOT))
OUT = Path('/tmp/opencode/itlr-e2e')
ARM = sys.argv[1]
assert ARM in ('none', '800'), ARM
for key in ('DEEPSEEK_API_KEY', 'OPENAI_API_KEY'):
    os.environ.pop(key, None)
os.environ.update(
    ITLR_ARTIFACTS_DIR='/tmp/opencode/itlr-e2e/artifacts',
    HF_HOME=str(ROOT / 'var/hf'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
    USE_OLLAMA='1', OLLAMA_MODEL='qwen2.5:3b',
    OLLAMA_BASE_URL='http://127.0.0.1:11434', OLLAMA_TIMEOUT='45',
    DISABLE_RERANKER='1', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
    OPENBLAS_NUM_THREADS='1')
os.environ.pop('ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET', None)
if ARM == '800':
    os.environ['ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET'] = '800'

from itlr.engine import load_engine
import itlr.chatbot.chatbot as cbm
import itlr.chatbot.citations as cit

if ARM == 'none':
    cbm._evidence_char_budget = lambda: None

prompt_chars = []
_orig = cit.evidence_selection_prompt
def _wrapped(sources, char_budget_per_chunk=None):
    text = _orig(sources, char_budget_per_chunk=char_budget_per_chunk)
    prompt_chars.append([len(text), char_budget_per_chunk])
    return text
cit.evidence_selection_prompt = _wrapped

p = ROOT / 'reports/release-readiness-evidence/blind_cases.jsonl'
sha = hashlib.sha256(p.read_bytes()).hexdigest()
assert sha == '2a3a98e2d207b7c4932ced6ec87b3d7db9668c8b543730545e9a76d10abe6dd1', sha
cases = [json.loads(x) for x in p.read_text().splitlines()]
engine = load_engine()
rows = []

async def run_case(case):
    started = time.perf_counter()
    events, first = [], None
    prompt_chars.clear()
    try:
        async with aclosing(engine.achat_stream(case['query'])) as response:
            async for kind, data in response:
                if kind == 'text' and first is None:
                    first = time.perf_counter() - started
                events.append({'type': kind, 'data': data})
    except Exception as exc:
        events.append({'type': 'error', 'data': repr(exc)})
    final = next((e['data'] for e in events if e['type'] == 'final'), None)
    row = {
        'id': case['id'], 'kind': case['kind'], 'query': case['query'],
        'seconds': round(time.perf_counter() - started, 3), 'ttft_s': first,
        'events': events, 'final': final,
        'prompt_chars': sum(x[0] for x in prompt_chars),
        'budget_seen': sorted({str(x[1]) for x in prompt_chars}),
        'human_groundedness': None, 'human_hallucination': None,
        'human_answer_relevance': None,
    }
    f = final or {}
    print(ARM, case['id'], row['seconds'], row['prompt_chars'], row['budget_seen'],
          f.get('generation_mode'), (f.get('citation_validation') or {}).get('status'),
          f.get('generation_error'), flush=True)
    return row

async def main():
    await run_case({'id': 'warmup', 'kind': 'positive', 'query': 'Docker là gì?'})
    for case in cases:
        rows.append(await run_case(case))
        doc = {
            'arm': ARM, 'dataset_sha256': sha,
            'dataset_author': 'frozen AI author, not human labels',
            'model': 'qwen2.5:3b', 'budget_s': 45, 'cases': rows,
            'code_sha256': hashlib.sha256((ROOT / 'itlr/chatbot/chatbot.py').read_bytes()).hexdigest(),
            'scope': 'controlled A/B, sequential shared-daemon; no policy tuning; warmup excluded',
        }
        (OUT / f'generation-eval-ab-{ARM}.json').write_text(
            json.dumps(doc, ensure_ascii=False, indent=2))

asyncio.run(main())
print('ARM DONE', ARM, flush=True)
