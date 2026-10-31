"""Per-case analysis of the frozen A/B (arm none vs 800). Read-only."""
import json
import math
import statistics
from pathlib import Path

D = Path('/tmp/opencode/itlr-e2e')


def accepted(row):
    f = row.get('final') or {}
    c = f.get('citation_validation') or {}
    return (f.get('generation_mode') == 'llm_extractive' and c.get('status') == 'valid'
            and c.get('evidence_binding') == 'verbatim' and not f.get('generation_error'))


def nonclaim(row):
    f = row.get('final') or {}
    mode = f.get('generation_mode')
    return mode in ('insufficient_evidence', 'error') or (mode == 'template' and f.get('intent') == 'off_topic')


def summary(path):
    doc = json.loads(Path(path).read_text())
    rows = doc['cases']
    pos = [r for r in rows if r['kind'] == 'positive']
    neg = [r for r in rows if r['kind'] == 'negative']
    acc = [r for r in pos if accepted(r)]
    durations = [r['seconds'] for r in acc]
    prompts = [r['prompt_chars'] for r in rows if r['prompt_chars']]
    return {
        'arm': doc['arm'], 'cases': len(rows),
        'positive_accepted': len(acc), 'positive_total': len(pos),
        'negative_nonclaim': sum(nonclaim(r) for r in neg), 'negative_total': len(neg),
        'prompt_chars_median': statistics.median(prompts) if prompts else None,
        'prompt_chars_max': max(prompts) if prompts else None,
        'accepted_p50_s': round(statistics.median(durations), 3) if durations else None,
        'accepted_p95_s': (round(sorted(durations)[int(math.ceil(0.95*len(durations)))-1], 3) if durations else None),
        'accepted_max_s': max(durations) if durations else None,
        'cache_hits_under5s': sum(1 for d in durations if d < 5),
        'generation_errors': [{'id': r['id'], 'error': (r.get('final') or {}).get('generation_error')} for r in rows if (r.get('final') or {}).get('generation_error')],
        'elapsed_ge_44s': [r['id'] for r in rows if r['seconds'] >= 44],
    }


A = summary(D / 'generation-eval-ab-none.json')
B = summary(D / 'generation-eval-ab-800.json')
rows_a = {r['id']: r for r in json.loads((D / 'generation-eval-ab-none.json').read_text())['cases']}
rows_b = {r['id']: r for r in json.loads((D / 'generation-eval-ab-800.json').read_text())['cases']}
per_case = []
for cid, ra in rows_a.items():
    rb = rows_b.get(cid)
    if rb is None:
        per_case.append({'id': cid, 'missing': True})
        continue
    per_case.append({
        'id': cid, 'kind': ra['kind'],
        'mode_none': (ra['final'] or {}).get('generation_mode'),
        'mode_800': (rb['final'] or {}).get('generation_mode'),
        'accepted_none': accepted(ra) if ra['kind'] == 'positive' else None,
        'accepted_800': accepted(rb) if rb['kind'] == 'positive' else None,
        'nonclaim_none': nonclaim(ra) if ra['kind'] == 'negative' else None,
        'nonclaim_800': nonclaim(rb) if rb['kind'] == 'negative' else None,
        'seconds_none': ra['seconds'], 'seconds_800': rb['seconds'],
        'prompt_chars_none': ra['prompt_chars'], 'prompt_chars_800': rb['prompt_chars'],
        'error_none': (ra['final'] or {}).get('generation_error'),
        'error_800': (rb['final'] or {}).get('generation_error'),
        'citation_none': (ra['final'] or {}).get('citation_validation', {}).get('evidence_binding'),
        'citation_800': (rb['final'] or {}).get('citation_validation', {}).get('evidence_binding'),
        'response_same': (ra['final'] or {}).get('response') == (rb['final'] or {}).get('response'),
    })
out = {'none': A, 'arm800': B, 'per_case': per_case,
       'note': 'Latency confounded by shared Ollama prompt-prefix cache; quality/acceptance and prompt size are the decision inputs.'}
(D / 'ab-analysis.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(json.dumps({'none': A, 'arm800': B}, indent=2))
for r in per_case:
    print(r)
