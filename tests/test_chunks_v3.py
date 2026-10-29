import numpy as np
import pytest


def test_chunk_dense_retrieves_tail_without_item_mean():
    from itlr.core.chunks import ChunkIndex
    rows = [dict(item_id=1, chunk_idx=0, chunk_text='unrelated intro'),
            dict(item_id=1, chunk_idx=1, chunk_text='database transaction rollback'),
            dict(item_id=2, chunk_idx=0, chunk_text='database overview')]
    index = ChunkIndex(rows, np.array([[1, 0], [0, 1], [.8, .6]], dtype='float32'))
    hits = index.search('transaction rollback', np.array([0, 1], dtype='float32'), top_k=2)
    assert hits[0]['chunk_id'] == '1:1'
    assert hits[0]['excerpt'] == rows[1]['chunk_text']
    assert index.ann.ntotal == 3


def test_chunk_cross_encoder_receives_passages_and_reorders():
    from itlr.core.chunks import ChunkIndex
    class Cross:
        def predict(self, pairs, **kwargs):
            assert all(len(p) == 2 for p in pairs)
            return np.array([0., 10.])
    rows = [dict(item_id=i, chunk_idx=0, chunk_text=t) for i,t in
            [(1,'docker networking'), (2,'docker volumes')]]
    index = ChunkIndex(rows, np.eye(2, dtype='float32'))
    hits = index.search('docker networking', np.array([1., 0.], dtype='float32'), reranker=Cross())
    assert hits[0]['item_id'] == 2


def test_chunk_invalid_vectors_fail_closed():
    from itlr.core.chunks import ChunkIndex
    with pytest.raises(ValueError):
        ChunkIndex([dict(item_id=1, chunk_idx=0, chunk_text='x')], np.zeros((2, 2)))


def test_citation_rejects_chunk_not_in_selected_evidence():
    from itlr.chatbot.citations import validate_citations
    sources = [dict(item_id=1, chunk_id='1:2', evidence_kind='source_text')]
    assert validate_citations('[item_id:1] [chunk_id:1:99]', sources)['status'] == 'invalid'
    assert validate_citations('[item_id:1] [chunk_id:1:2]', sources)['status'] == 'valid'
