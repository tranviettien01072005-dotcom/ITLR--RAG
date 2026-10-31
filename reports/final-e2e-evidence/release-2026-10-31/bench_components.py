"""Component-level RAG benchmark: retrieval, prompt build, warm streaming, memory."""
import asyncio
import json
import os
import statistics
import sys
import time
from contextlib import aclosing
from pathlib import Path

ROOT = Path('/home/o/ITLR--RAG')
sys.path.insert(0, str(ROOT))
QUERIES = [
    'I need a Python UUID but want to avoid embedding my computer’s network address. How do uuid1() and uuid4() differ here?',
    'What does HTTP 404 mean?',
    'Tôi giữ một min-heap kích thước cố định. Nếu không muốn giá trị trả về lớn hơn phần tử mới đưa vào, vì sao nên cân nhắc heappushpop() thay cho heapreplace()?',
]
OUT = Path('/tmp/opencode/itlr-bench')
OUT.mkdir(exist_ok=True)
for key in ('DEEPSEEK_API_KEY', 'OPENAI_API_KEY'):
    os.environ.pop(key, None)
os.environ.update(
    ITLR_ARTIFACTS_DIR='/tmp/opencode/itlr-e2e/artifacts', HF_HOME=str(ROOT / 'var/hf'),
    HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', USE_OLLAMA='1', OLLAMA_MODEL='qwen2.5:3b',
    OLLAMA_BASE_URL='http://127.0.0.1:11434', OLLAMA_TIMEOUT='45', DISABLE_RERANKER='1',
    OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1')

from itlr.engine import load_engine  # noqa: E402
import itlr.chatbot.citations as cit  # noqa: E402

prompt_chars = []
_orig = cit.evidence_selection_prompt
def _wrap(sources, char_budget_per_chunk=None):
    text = _orig(sources, char_budget_per_chunk=char_budget_per_chunk)
    prompt_chars.append(len(text))
    return text
cit.evidence_selection_prompt = _wrap


def rss_mib(pid):
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'):
                return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        return None
    return None


eng = load_engine()
rows = []


def search_latency(query):
    start = time.perf_counter()
    res = eng.search(query, min_pct=84)
    return {'ms': round((time.perf_counter() - start) * 1000, 2), 'hits': len(res.get('results', []))}


async def stream(query):
    started = time.perf_counter()
    first_event = None
    final = None
    event_types = []
    prompt_chars.clear()
    async with aclosing(eng.achat_stream(query)) as response:
        async for kind, data in response:
            if first_event is None:
                first_event = time.perf_counter() - started
            event_types.append(kind)
            if kind == 'final':
                final = data
    return {
        'first_event_ms': round((first_event or 0) * 1000, 1),
        'total_ms': round((time.perf_counter() - started) * 1000, 1),
        'prompt_chars': max(prompt_chars) if prompt_chars else 0,
        'mode': (final or {}).get('generation_mode'),
        'citation': ((final or {}).get('citation_validation') or {}).get('status'),
        'events': event_types,
    }


async def main():
    for query in QUERIES:
        s = search_latency(query)
        t = await stream(query)  # first query is warm-up for the daemon/prefix cache
        rows.append({'query': query[:60], 'search': s, **t, 'warm': True})
    s_lat = [r['search']['ms'] for r in rows]
    t_tot = [r['total_ms'] for r in rows if r['warm']]
    llama = [p.name for p in Path('/proc').iterdir() if p.name.isdigit()
             and 'llama-server' in (Path(p) / 'cmdline').read_text(errors='ignore')]
    doc = {
        'host': 'i7-8650U 4C/8T CPU-only; Ollama 0.40.13 qwen2.5:3b; reranker disabled',
        'mode': 'warm (daemon and prompt-prefix cache warm); cold covered by isolated-container run',
        'queries': rows,
        'search_ms': {'p50': round(statistics.median(s_lat), 2), 'max': round(max(s_lat), 2)},
        'stream_total_ms': {'p50': round(statistics.median(t_tot), 1), 'max': round(max(t_tot), 1)},
        'python_peak_rss_mib': round(int([l for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('VmHWM:')][0].split()[1]) / 1024, 1),
        'ollama_runner_rss_mib': max((rss_mib(int(p)) or 0) for p in llama) if llama else None,
        'note': 'first_event is the sources event; in llm_extractive no provisional tokens are emitted before final',
    }
    (OUT / 'components-warm.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    print(json.dumps(doc, ensure_ascii=False, indent=2))

asyncio.run(main())
