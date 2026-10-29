"""Reproducible lexical smoke benchmark; synthetic fixtures, NOT RAG quality evidence.

Run: .venv/bin/python eval/eval_fixture.py
No model downloads, network calls, or LLM calls. Hand-authored expected IDs.
"""
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from itlr.core.bm25 import BM25Index
from itlr.core.recommender import (
    build_field_corpus, build_retrieval_model, create_vectorizer, search_by_query,
)


def main():
    topics = ['docker containers deployment', 'postgresql indexes database', 'python generators programming']
    items = pd.DataFrame([
        dict(item_id=i + 1, title=topic, description=f'{topic} practical examples',
             topics=topic, category='Lập trình', type='Tài liệu', level='Trung cấp',
             instructor='Fixture', platform='Fixture', link=f'https://fixture.example/{i+1}')
        for i, topic in enumerate(topics)
    ])
    vectorizers, matrices = {}, {}
    for field in ['full', 'title', 'topics', 'category']:
        if field == 'category':  # constant category has no discriminating vocabulary
            continue
        vec = create_vectorizer()
        matrices[field] = vec.fit_transform(build_field_corpus(items, field))
        vectorizers[field] = vec
    model = build_retrieval_model(items, vectorizers, matrices,
                                  BM25Index().fit(build_field_corpus(items, 'full')))
    cases, timings = [], []
    for expected, query in enumerate(topics, 1):
        ranks = []
        for _ in range(20):
            start = time.perf_counter()
            results = search_by_query(items, model, query, top_n=3, use_mmr=False)
            timings.append((time.perf_counter() - start) * 1000)
            ids = [int(r['item_id']) for r in results]
            ranks.append(ids.index(expected) + 1 if expected in ids else None)
        rank = ranks[0]
        assert all(r == rank for r in ranks), 'Non-deterministic ranking'
        cases.append(dict(query=query, expected_id=expected, rank=rank))
    report = dict(
        scope='lexical TF-IDF + BM25 smoke only; no embeddings/reranker/LLM',
        provenance='synthetic 3-item fixture; expected IDs hand-authored; not human labels',
        queries=3, measured_requests=len(timings), repeats_per_query=20,
        recall_at_3=float(np.mean([c['rank'] is not None for c in cases])),
        mrr_at_3=float(np.mean([1/c['rank'] if c['rank'] else 0 for c in cases])),
        ndcg_at_3=float(np.mean([1/np.log2(c['rank']+1) if c['rank'] else 0 for c in cases])),
        latency_ms={f'p{p}':float(np.percentile(timings,p)) for p in [50,95,99]},
        groundedness=None, citation_accuracy=None, hallucination=None,
        llm_calls=0, llm_tokens=0, measured_api_cost_usd=0,
        limitations='No generation: null quality values are unmeasured, not zero error.',
        python=sys.version.split()[0], cases=cases)
    path = Path(__file__).resolve().parent.parent / 'reports' / 'fixture_eval.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
