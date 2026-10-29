"""Chunk-level FAISS + BM25 retrieval with RRF and bounded cross-encoding."""
import numpy as np

from itlr.retrieval.bm25 import BM25Index


class ChunkIndex:
    def __init__(self, rows, vectors):
        import faiss
        self.rows = rows
        vectors = np.asarray(vectors, dtype='float32')
        if (vectors.ndim != 2 or len(rows) != len(vectors) or not rows
                or not np.isfinite(vectors).all()
                or np.any(np.linalg.norm(vectors, axis=1) == 0)):
            raise ValueError('Invalid chunk vectors or ownership')
        keys = [(int(r['item_id']), int(r['chunk_idx'])) for r in rows]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate chunk identifiers')
        vectors = vectors.copy()
        faiss.normalize_L2(vectors)
        self.ann = faiss.IndexFlatIP(vectors.shape[1])
        self.ann.add(vectors)
        self.bm25 = BM25Index().fit([r['chunk_text'] for r in rows])

    def search(self, query, vector, *, top_k=8, candidate_k=32, reranker=None,
               allowed_item_ids=None, min_relevance=-1., unique_items=False):
        import faiss
        if top_k < 1 or candidate_k < 1:
            raise ValueError('Positive retrieval limits required')
        candidate_k = max(candidate_k, top_k)
        vector = np.asarray(vector, dtype='float32').reshape(1, -1).copy()
        if (vector.shape[1] != self.ann.d or not np.isfinite(vector).all()
                or not np.linalg.norm(vector)):
            raise ValueError('Invalid query vector')
        faiss.normalize_L2(vector)
        scores, ids = self.ann.search(vector, len(self.rows))
        dense_scores = dict(zip(ids[0].tolist(), np.clip(scores[0], -1., 1.).tolist()))

        def select(ranking):
            selected, seen = [], set()
            for idx in ranking:
                item_id = int(self.rows[idx]['item_id'])
                if unique_items and item_id in seen:
                    continue
                seen.add(item_id)
                selected.append(idx)
                if len(selected) == candidate_k:
                    break
            return selected

        allowed = {i for i,r in enumerate(self.rows)
                   if (allowed_item_ids is None or int(r['item_id']) in allowed_item_ids)
                   and dense_scores[i] + 1e-6 >= min_relevance}
        dense = select(sorted(allowed, key=lambda i: (-dense_scores[i], i)))
        lexical = self.bm25.score_query(query)
        sparse = select(sorted((i for i,s in enumerate(lexical) if s > 0 and i in allowed),
                               key=lambda i: (-lexical[i], i)))
        fused = {}
        for ranking in (dense, sparse):
            for rank, idx in enumerate(ranking, 1):
                fused[idx] = fused.get(idx, 0.) + 1 / (60 + rank)
        ranked = select(sorted(fused, key=lambda i: (-fused[i], i)))
        if reranker is not None and ranked:
            scores = np.asarray(reranker.predict(
                [[query, self.rows[i]['chunk_text']] for i in ranked],
                convert_to_numpy=True, show_progress_bar=False)).reshape(-1)
            if len(scores) != len(ranked) or not np.isfinite(scores).all():
                raise ValueError('Invalid cross-encoder scores')
            ranked = [i for i,_ in sorted(zip(ranked, scores), key=lambda p: -float(p[1]))]
        return [{**self.rows[i], 'chunk_id': f"{self.rows[i]['item_id']}:{self.rows[i]['chunk_idx']}",
                 'excerpt': self.rows[i]['chunk_text'], 'score': fused[i],
                 'dense_score': dense_scores[i],
                 'evidence_kind': 'source_text'} for i in ranked[:top_k]]
