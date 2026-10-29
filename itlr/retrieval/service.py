"""Shared chunk retrieval contract for search, chat and relevance gating."""
from itlr.core.embeddings import encode_query


class RetrievalService:
    def __init__(self, index, items, encoder, query_prefix='', reranker=None):
        self.index = index
        self.encoder = encoder
        self.query_prefix = query_prefix
        self.reranker = reranker
        self.items = {int(r['item_id']): r for r in items.to_dict('records')}

    def vector(self, query):
        return encode_query(self.encoder, query, {'query_prefix':self.query_prefix})

    def relevance(self, query):
        if not query.strip():
            return 0.
        hits = self.index.search('', self.vector(query), top_k=1, candidate_k=1)
        return hits[0]['dense_score'] if hits else 0.

    def search(self, query, *, top_k=8, item_type=None, min_relevance=0., use_reranker=True):
        if not query.strip():
            return []
        allowed = {iid for iid,r in self.items.items() if not item_type or r['type']==item_type}
        hits = self.index.search(query,self.vector(query),top_k=top_k,
                                 allowed_item_ids=allowed,min_relevance=min_relevance,
                                 reranker=self.reranker if use_reranker else None)
        return [{**h,'item':self.items[int(h['item_id'])]} for h in hits]
