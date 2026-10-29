from itlr.retrieval.bm25 import BM25Index


def test_refit_clears_terms_from_previous_corpus():
    index=BM25Index().fit(['kubernetes networking','python lists'])
    old_terms=set(index.idf)
    index.fit(['docker containers'])
    assert old_terms.isdisjoint(index.idf)
    assert index.n_docs==1
    assert index.score_query('kubernetes')==[0.]


def test_new_and_legacy_pickle_state_score_identically():
    import pickle
    index=BM25Index().fit(['docker networking','python lists','docker volumes'])
    expected=index.score_query('docker')
    del index.postings
    restored=pickle.loads(pickle.dumps(index))
    assert restored.score_query('docker')==expected
    assert index.score_query('docker')[1]==0.


def test_concurrent_legacy_index_initialization_never_exposes_partial_postings():
    import threading
    index=BM25Index().fit(['python lists','docker volumes'])
    expected=index.score_query('docker')
    del index.postings
    entered,release=threading.Event(),threading.Event()
    class SlowList(list):
        def __iter__(self):
            for position,terms in enumerate(super().__iter__()):
                if position==1 and threading.current_thread().name=='builder':
                    entered.set()
                    release.wait(5)
                yield terms
    index.doc_freqs=SlowList(index.doc_freqs)
    thread=threading.Thread(target=lambda:index.score_query('docker'),name='builder')
    thread.start()
    try:
        assert entered.wait(5)
        assert index.score_query('docker')==expected
    finally:
        release.set()
        thread.join(5)
