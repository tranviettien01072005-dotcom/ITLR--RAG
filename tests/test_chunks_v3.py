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


def test_chunk_top_k_larger_than_default_candidate_pool():
    from itlr.core.chunks import ChunkIndex
    rows = [dict(item_id=i, chunk_idx=0, chunk_text='docker') for i in range(40)]
    index = ChunkIndex(rows, np.tile([1., 0.], (40, 1)))
    assert len(index.search('docker', [1., 0.], top_k=40)) == 40


def test_item_search_diversifies_before_candidate_truncation():
    from itlr.core.chunks import ChunkIndex
    rows = [dict(item_id=1, chunk_idx=i, chunk_text='docker') for i in range(40)]
    rows.append(dict(item_id=2, chunk_idx=0, chunk_text='docker volumes'))
    index = ChunkIndex(rows, np.array([[1., 0.]] * 40 + [[.8, .6]]))
    hits = index.search('docker', [1., 0.], top_k=2, unique_items=True)
    assert [h['item_id'] for h in hits] == [1, 2]
    assert len(index.search('docker', [1., 0.], top_k=2)) == 2


def test_cosine_threshold_is_inclusive_at_one_after_normalization():
    from itlr.core.chunks import ChunkIndex
    rows = [dict(item_id=1, chunk_idx=0, chunk_text='docker')]
    index = ChunkIndex(rows, [[1., 2., 3.]])
    hits = index.search('docker', [1., 2., 3.], min_relevance=1.)
    assert len(hits) == 1
    assert hits[0]['dense_score'] <= 1.


def test_min_relevance_gates_sparse_candidates_before_fusion():
    """Hợp đồng hiện hành: ngưỡng dense (min_relevance) áp cho CẢ candidate BM25 TRƯỚC
    fusion ⇒ mọi kết quả trả về đều có dense_score >= min_relevance. Chunk khớp BM25
    tốt nhưng dense dưới ngưỡng KHÔNG được trả về.

    Đây là lựa chọn design có chủ đích (ngưỡng floor chặt trên kết quả cuối), không phải
    bug. Muốn tách candidate generation dense/sparse độc lập (thêm ứng viên lexical
    xuyên ngưỡng) phải: thay đổi test này một cách có chủ ý, chạy lại eval Recall@5
    trên frozen benchmark, và ghi ADR."""
    from itlr.core.chunks import ChunkIndex
    rows = [dict(item_id=1, chunk_idx=0, chunk_text='terraform state locking guide'),
            dict(item_id=2, chunk_idx=0, chunk_text='container orchestration overview')]
    index = ChunkIndex(rows, np.array([[0., 1.], [1., 0.]], dtype='float32'))
    query_vec = np.array([1., 0.], dtype='float32')
    # BM25 khớp item 1 (3 token), dense item 1 = 0.0 dưới ngưỡng 0.5 → bị loại.
    hits = index.search('terraform state locking', query_vec, top_k=2, min_relevance=0.5)
    assert [h['item_id'] for h in hits] == [2]
    assert all(h['dense_score'] >= 0.5 for h in hits)
    # Không ngưỡng: RRF trả cả hai, item 1 đứng đầu nhờ sparse top-1.
    hits = index.search('terraform state locking', query_vec, top_k=2)
    assert {h['item_id'] for h in hits} == {1, 2}
