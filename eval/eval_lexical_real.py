"""Real-snapshot lexical retrieval benchmark; hand-authored single-annotator qrels.

Scope: 118 checked-in curated resources, 8 queries, BM25/TF-IDF + MMR disabled.
No embeddings, reranker, or LLM. Labels are engineer-authored (one annotator), not a
human panel; results are smoke/regression evidence, not production RAG quality.

Run: python eval/eval_lexical_real.py [--out reports/lexical_real_eval.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from itlr.core.recommender import (  # noqa: E402
    build_field_corpus, build_retrieval_model, create_vectorizer, search_by_query,
)
from itlr.eval.metrics import ndcg_at_k, recall_at_k  # noqa: E402
from itlr.retrieval.bm25 import BM25Index  # noqa: E402

# Same eight hand-authored qrels as eval/bench_chunks_v3.py (single annotator).
CASES = [
    (5001, "How does Docker daemon access affect root privileges?"),
    (5003, "How do services networks and volumes work together in Compose?"),
    (5011, "How do I publish a container port to a host port?"),
    (5024, "How does a browser use a preflight request for cross origin HTTP?"),
    (5028, "How do I select the first DOM element matching a CSS selector?"),
    (5117, "How do I create and activate a Python virtual environment?"),
    (5121, "How do I handle exceptions with try and except in Python?"),
    (5126, "How do Python lists support indexing and slicing?"),
]
FIELDS = ("full", "title", "topics")
REPEATS = 20
TOP_K = 5


def load_items(path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    frame = pd.DataFrame(rows)
    frame["item_id"] = frame["item_id"].astype(int)
    return frame


def build_model(items: pd.DataFrame):
    vectorizers, matrices = {}, {}
    for field in FIELDS:
        vectorizers[field] = create_vectorizer()
        matrices[field] = vectorizers[field].fit_transform(build_field_corpus(items, field))
    return build_retrieval_model(
        items, vectorizers, matrices, BM25Index().fit(build_field_corpus(items, "full"))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="optional JSON output path")
    args = parser.parse_args()

    items = load_items(ROOT / "data" / "curated_resources.jsonl")
    model = build_model(items)
    known = set(items["item_id"])
    missing = [item_id for item_id, _ in CASES if item_id not in known]
    if missing:
        raise RuntimeError(f"qrels reference missing item_id: {missing}")

    cases, latencies = [], []
    for expected, query in CASES:
        ranks = []
        for _ in range(REPEATS):
            start = time.perf_counter()
            results = search_by_query(items, model, query, top_n=TOP_K, use_mmr=False)
            latencies.append((time.perf_counter() - start) * 1000)
            ids = [int(row["item_id"]) for row in results]
            ranks.append(ids.index(expected) + 1 if expected in ids else None)
        if len(set(ranks)) != 1:
            raise RuntimeError(f"non-deterministic ranking for {query!r}: {ranks}")
        rank = ranks[0]
        rels = [1 if rank == i else 0 for i in range(1, TOP_K + 1)]
        cases.append({
            "query": query,
            "expected_id": expected,
            "rank": rank,
            "recall_at_5": recall_at_k(rels, TOP_K, 1),
            "mrr_at_5": (1.0 / rank) if rank else 0.0,
            "ndcg_at_5": ndcg_at_k(rels, TOP_K, ideal_rels=[1]),
        })

    total_seconds = sum(latencies) / 1000
    report = {
        "scope": "lexical TF-IDF + BM25 over real curated snapshot; MMR off; no neural/reranker/LLM",
        "provenance": "118 checked-in items; 8 engineer-authored single-annotator qrels; not a human panel",
        "queries": len(CASES),
        "corpus_items": len(items),
        "measured_requests": len(latencies),
        "top_k": TOP_K,
        "recall_at_5": float(np.mean([c["recall_at_5"] for c in cases])),
        "mrr_at_5": float(np.mean([c["mrr_at_5"] for c in cases])),
        "ndcg_at_5": float(np.mean([c["ndcg_at_5"] for c in cases])),
        "latency_ms": {f"p{p}": float(np.percentile(latencies, p)) for p in (50, 95, 99)},
        "throughput_rps": float(len(latencies) / total_seconds) if total_seconds else None,
        "faithfulness": None,
        "answer_relevance": None,
        "hallucination": None,
        "llm_calls": 0,
        "measured_api_cost_usd": 0,
        "limitations": "Single-annotator qrels, 118 documents, lexical only; neural/generation unmeasured.",
        "python": sys.version.split()[0],
        "cases": cases,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
