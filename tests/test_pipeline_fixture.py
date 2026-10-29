"""Offline integration: fixture RSS -> SQLite -> catalog -> lexical hybrid retrieval.

No neural embeddings, live crawl or LLM is represented by this test.
"""
import pickle

from itlr import config
from itlr.collect.normalize import assemble_itlr_items
from itlr.collect.runner import CollectRunner
from itlr.collect.sources import Source, SourceSet
from itlr.collect.store import CollectStore
from itlr.collect.chunk import chunk_text
from itlr.core.bm25 import BM25Index
from itlr.core.recommender import (
    build_field_corpus, build_retrieval_model, create_vectorizer, search_by_query,
)


def test_fixture_crawl_catalog_index_reload_retrieval(tmp_path, monkeypatch):
    db = tmp_path / "crawl.db"
    monkeypatch.setattr(config, "COLLECT_DB", db)
    monkeypatch.setattr(config, "ITEMS_CSV", tmp_path / "absent.csv")
    titles = ["Docker containers deployment tutorial", "PostgreSQL indexes database tutorial",
              "Python generators programming tutorial"]
    pages = {}
    entries = []
    for i, title in enumerate(titles):
        url = f"https://fixture.example/articles/{i}"
        entries.append(f"<item><title>{title}</title><link>{url}</link></item>")
        pages[url] = (200, (f"<html><article><h1>{title}</h1><p>" +
                          (title + " practical examples for software engineers. ") * 20 +
                          "</p></article></html>").encode())
    feed = "https://fixture.example/feed"
    pages[feed] = (200, ("<rss version='2.0'><channel><title>Fixture</title>" +
                        "".join(entries) + "</channel></rss>").encode())

    class FixtureFetcher:
        def fetch(self, url, *, respect_robots=True):
            assert respect_robots
            return pages[url]

    src = Source("fixture", "rss", "Fixture", "Fixture", "https://fixture.example",
                 True, "test-fixture", feed_url=feed, max_items_per_run=3)
    store = CollectStore(db)
    try:
        stats = CollectRunner(SourceSet({"min_text_chars": 80}, (src,)),
                              fetcher=FixtureFetcher(), store=store).run()
        assert stats["totals"]["new"] == 3
    finally:
        store.close()
    items = assemble_itlr_items()
    assert len(items) == 3
    assert set(items.origin) == {"crawl:fixture"}
    assert set(items.crawl_license) == {"test-fixture"}
    assert all(chunk_text(text) for text in items.description)
    vectorizers, matrices = {}, {}
    for field in ("full", "title", "topics", "category"):
        corpus = build_field_corpus(items, field)
        # Empty source tags are valid; no topics vocabulary exists in this fixture.
        if field == "topics":
            continue
        vec = create_vectorizer()
        matrices[field] = vec.fit_transform(corpus)
        vectorizers[field] = vec
    model = build_retrieval_model(items, vectorizers, matrices,
                                  BM25Index().fit(build_field_corpus(items, "full")))
    artifact = tmp_path / "fixture-retrieval.pkl"
    with artifact.open("wb") as handle:
        pickle.dump(model, handle)
    with artifact.open("rb") as handle:
        restored = pickle.load(handle)
    results = search_by_query(items, restored, "docker containers deployment", use_mmr=False)
    assert results
    assert results[0]["title"] == titles[0]
    assert results[0]["item_id"] in items.item_id.tolist()
    assert results[0]["link"] == "https://fixture.example/articles/0"
