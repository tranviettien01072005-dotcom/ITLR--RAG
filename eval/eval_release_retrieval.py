"""Frozen real-snapshot lexical release diagnostics; no neural or generation claims."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from eval.eval_lexical_real import build_model, load_items
from itlr.core.recommender import search_by_query
from itlr.eval.metrics import ndcg_at_k


def peak_process_rss_mib():
    """Whole-process high-water RSS, including model build and both variants."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    'peak', 'working', 'peak_paged', 'paged', 'peak_nonpaged',
                    'nonpaged', 'pagefile', 'peak_pagefile')]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        get_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if not get_info(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise OSError('GetProcessMemoryInfo failed')
        return counters.peak / 1024**2
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2 if sys.platform == 'darwin' else 1024)


def metrics(ids, expected, k):
    if not expected:
        return {'recall': None, 'precision_judged': None, 'mrr': None, 'ndcg': None,
                'empty_result': not ids}
    rels = [int(i in expected) for i in ids[:k]]
    first = next((i for i, rel in enumerate(rels, 1) if rel), None)
    return {'recall': sum(rels) / len(expected), 'precision_judged': sum(rels) / k,
            'mrr': 1 / first if first else 0.,
            'ndcg': ndcg_at_k(rels, k, ideal_rels=[1] * len(expected)),
            'empty_result': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=ROOT / 'eval/release_queries.jsonl')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    corpus = ROOT / 'data/curated_resources.jsonl'
    items = load_items(corpus)
    sources = {int(row['item_id']): row['full_text'] for row in items.to_dict('records')}
    cases = [json.loads(line) for line in args.cases.read_text(encoding='utf-8').splitlines()]
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate evaluation query IDs')
    for case in cases:
        for judgment in case['judgments']:
            if judgment['quote'] not in sources[judgment['item_id']]:
                raise ValueError(f"Evidence mismatch for {case['id']}")
    model = build_model(items)
    outputs = {}
    # Alternate variant execution per query/repeat to reduce order drift.
    for name in ('lexical', 'lexical_mmr'):
        outputs[name] = {'latencies': [], 'cases': []}
    for case in cases:
        ranks = {name: [] for name in outputs}
        for repeat in range(args.repeats):
            order = list(outputs) if repeat % 2 == 0 else list(reversed(outputs))
            for name in order:
                start = time.perf_counter()
                results = search_by_query(items, model, case['query'], top_n=10,
                                          use_mmr=name == 'lexical_mmr')
                outputs[name]['latencies'].append((time.perf_counter() - start) * 1000)
                ranks[name].append([int(row['item_id']) for row in results])
        for name, repeated in ranks.items():
            if any(ids != repeated[0] for ids in repeated):
                raise RuntimeError('Non-deterministic rankings')
            expected = {j['item_id'] for j in case['judgments']}
            outputs[name]['cases'].append({'id': case['id'], 'kind': case['kind'],
                'query': case['query'], 'expected': sorted(expected), 'ranked': repeated[0],
                'metrics': {str(k): metrics(repeated[0], expected, k) for k in (1, 5, 10)}})
    for output in outputs.values():
        latencies = output.pop('latencies')
        output['latency_ms'] = {f'p{p}': float(np.percentile(latencies, p)) for p in (50, 95, 99)}
        output['serial_throughput_rps'] = len(latencies) / (sum(latencies) / 1000)
        output['aggregate'] = {}
        for k in (1, 5, 10):
            positive = [c['metrics'][str(k)] for c in output['cases'] if c['expected']]
            output['aggregate'][str(k)] = {key: float(np.mean([m[key] for m in positive]))
                for key in ('recall', 'precision_judged', 'mrr', 'ndcg')}
        negative = [c for c in output['cases'] if not c['expected']]
        output['no_answer_empty_rate'] = float(np.mean([not c['ranked'] for c in negative])) if negative else None
    report = {'scope': 'real corpus lexical diagnostics only; not neural V3 or production quality',
        'labels': 'engineer-authored, frozen before ranking; evidence quotes; incomplete judgments, no independent human panel',
        'precision_note': 'precision against judged items only; unjudged items may also be relevant',
        'negative_note': 'empty ranking is a retrieval diagnostic, not generation refusal accuracy',
        'corpus_items': len(items), 'query_count': len(cases), 'repeats': args.repeats,
        'corpus_sha256': hashlib.sha256(corpus.read_bytes()).hexdigest(),
        'queries_sha256': hashlib.sha256(args.cases.read_bytes()).hexdigest(),
        'peak_process_rss_mib': peak_process_rss_mib(),
        'memory_scope': 'whole process high-water; includes build and both variants, not per-variant',
        'neural_v3': None, 'cross_encoder': None, 'faithfulness': None,
        'citation_support': None, 'answer_relevancy': None, 'hallucination': None,
        'refusal_accuracy': None, 'llm_calls': 0, 'results': outputs}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
