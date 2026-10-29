"""Regression: chống trùng gần đúng + đồng bộ active/missing của crawler.

Lỗi gốc:
  - `title_similarity` dùng overlap coefficient (giao/min) nhưng docstring nói Jaccard;
    tiêu đề ngắn chung vài token phổ biến bị chặn nhầm.
  - Runner chỉ so title CHÍNH XÁC nên near-dup giữa nguồn không bao giờ bị bắt.
  - `mark_missing`/`link_seen` không được gọi -> bài đã bị nguồn xóa vẫn active mãi.
  - Nếu đồng bộ missing mà không loại trừ listing lỗi/budget, sẽ đánh missing hàng loạt sai.
"""

from __future__ import annotations

import pytest

from itlr.collect.http import HttpError
from itlr.collect.quality import content_hash, normalize_title, title_similarity
from itlr.collect.runner import CollectRunner
from itlr.collect.sources import Source, SourceSet
from itlr.collect.store import CollectStore
from itlr.collect.url_util import content_key

PAGE_TPL = ("<html><head><title>W</title></head><body><article>"
            "<h1>{title}</h1><p>" + ("nội dung học lập trình thật. " * 25) + "</p></article>"
            "</body></html>")


class StubFetcher:
    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[str] = []

    def fetch(self, url, *, respect_robots=True):
        self.calls.append(url)
        item = self.responses.get(url)
        if item is None:
            raise HttpError(f"không cấu hình mock cho {url}")
        return item


def _rss_xml(items):
    entries = "".join(
        f"<item><title>{t}</title><link>{u}</link><description>{d}</description></item>"
        for t, u, d in items)
    return f"<rss version='2.0'><channel><title>r</title>{entries}</channel></rss>".encode()


def _doc(key: str, *, title: str, source_id: str = "rss1") -> dict:
    text = "nội dung học lập trình thật. " * 25
    return {
        "content_key": key, "source_id": source_id, "external_id": "",
        "url": f"https://r/{key}", "norm_url": f"https://r/{key}",
        "title": title, "description": "d", "text": text, "tags": "",
        "author": "A", "published_at": "2026-10-28", "lang": "vi",
        "license": "L", "full_text_allowed": 1,
        "content_hash": content_hash(text + title + "d"),
        "n_chars": len(text), "quality_status": "ok", "status": "active",
        "fetched_at": "2026-10-28T00:00:00Z",
    }


def _rss_source(max_items=10) -> Source:
    return Source(source_id="rss1", kind="rss", name="R", platform="P", homepage="h",
                  full_text_allowed=True, license="L", feed_url="https://r/rss",
                  lang="vi", max_items_per_run=max_items)


def _sset(src: Source) -> SourceSet:
    return SourceSet(defaults={"recheck_after_hours": 0, "min_text_chars": 80,
                               "min_title_chars": 8, "max_text_chars": 3000},
                     sources=(src,))


def test_title_similarity_is_jaccard_not_overlap():
    # 2 token chung / 4 token hợp = 0.5; overlap coefficient cũ sẽ cho 1.0.
    assert title_similarity("Hướng dẫn Docker", "Hướng dẫn Kubernetes") == pytest.approx(0.5)
    assert title_similarity("Hướng dẫn Docker", "hướng dẫn docker") == 1.0
    assert normalize_title("  Hướng   Dẫn Docker ") == "hướng dẫn docker"


def test_near_dup_lookup_catches_title_variant(tmp_path):
    st = CollectStore(tmp_path / "c.db")
    st.upsert_doc(_doc("u:1", title="Hướng dẫn Docker cơ bản cho người mới"))
    assert st.find_near_dup_title("Hướng dẫn Docker cơ bản cho người mới nhất") is not None
    assert st.find_near_dup_title("Kubernetes nâng cao cho DevOps") is None
    st.close()


def test_reconcile_marks_missing_and_restores(tmp_path):
    st = CollectStore(tmp_path / "c.db")
    ka, kb = content_key("https://r/a"), content_key("https://r/b")
    st.upsert_doc(_doc(ka, title="Học Docker từ cơ bản đến nâng cao"))
    st.upsert_doc(_doc(kb, title="Kubernetes cho lập trình viên backend"))
    st.upsert_doc(_doc("u:other", title="Bài của nguồn khác", source_id="other"))

    r = st.reconcile_source("rss1", {ka})
    assert r == {"marked_missing": 1, "restored": 0}
    assert st.get_doc_by_key(kb)["status"] == "missing"
    assert st.get_doc_by_key(ka)["status"] == "active"
    assert st.get_doc_by_key("u:other")["status"] == "active"

    # Không thay đổi gì -> không báo missing/restored sai.
    assert st.reconcile_source("rss1", {ka}) == {"marked_missing": 0, "restored": 0}

    # Xuất hiện lại -> restored.
    assert st.reconcile_source("rss1", {ka, kb}) == {"marked_missing": 0, "restored": 1}
    assert st.get_doc_by_key(kb)["status"] == "active"
    st.close()


def test_runner_marks_doc_missing_when_removed_from_complete_inventory(tmp_path):
    store = CollectStore(tmp_path / "c.db")
    url_a, url_b = "https://r/a", "https://r/b"
    ka, kb = content_key(url_a), content_key(url_b)

    f1 = StubFetcher({
        "https://r/rss": (200, _rss_xml([("Học Docker từ cơ bản đến nâng cao", url_a, "d")])),
        url_a: (200, PAGE_TPL.format(title="Học Docker từ cơ bản").encode()),
    })
    src = _rss_source()
    src.listing_is_complete = True
    s1 = CollectRunner(_sset(src), fetcher=f1, store=store).run()
    assert s1["sources"]["rss1"]["new"] == 1

    f2 = StubFetcher({
        "https://r/rss": (200, _rss_xml([("Kubernetes cho lập trình viên backend", url_b, "d")])),
        url_b: (200, PAGE_TPL.format(title="Kubernetes cho backend").encode()),
    })
    s2 = CollectRunner(_sset(src), fetcher=f2, store=store).run()
    assert s2["sources"]["rss1"]["missing"] == 1
    assert store.get_doc_by_key(ka)["status"] == "missing"
    assert store.get_doc_by_key(kb)["status"] == "active"

    f3 = StubFetcher({
        "https://r/rss": (200, _rss_xml([("Học Docker từ cơ bản đến nâng cao", url_a, "d")])),
        url_a: (200, PAGE_TPL.format(title="Học Docker từ cơ bản").encode()),
    })
    s3 = CollectRunner(_sset(src), fetcher=f3, store=store).run()
    assert s3["sources"]["rss1"]["restored"] == 1
    assert store.get_doc_by_key(ka)["status"] == "active"
    store.close()


def test_budget_truncation_does_not_mark_unseen_as_missing(tmp_path):
    """5 bài trong feed, budget=1: 4 bài chưa fetch vẫn phải active (vẫn còn trong listing)."""
    store = CollectStore(tmp_path / "c.db")
    src = _rss_source(max_items=1)
    items = [(f"Bài học lập trình số {i} về Docker và CI/CD pipeline",
              f"https://r/a-{i}", "d") for i in range(5)]
    for title, url, _ in items:
        store.upsert_doc(_doc(content_key(url), title=title))

    fetcher = StubFetcher({
        "https://r/rss": (200, _rss_xml(items)),
        **{url: (200, PAGE_TPL.format(title=title).encode()) for title, url, _ in items},
    })
    stats = CollectRunner(_sset(src), fetcher=fetcher, store=store).run()
    assert stats["sources"]["rss1"]["missing"] == 0
    statuses = [dict(r)["status"] for r in store._conn.execute("SELECT status FROM docs")]
    assert statuses and all(s == "active" for s in statuses)
    store.close()


def test_failed_listing_never_marks_existing_docs_missing(tmp_path):
    store = CollectStore(tmp_path / "c.db")
    key = content_key("https://w/old")
    store.upsert_doc(_doc(key, title="Bài cũ vẫn còn trên site", source_id="web1"))

    web = Source(source_id="web1", kind="web", name="W", platform="P", homepage="h",
                 full_text_allowed=False, license="none",
                 list_urls=("https://w/news",), lang="vi")
    ss = SourceSet(defaults={"recheck_after_hours": 0, "min_text_chars": 80,
                             "min_title_chars": 8}, sources=(web,))
    # Chỉ có trang bài, KHÔNG có listing -> fetch listing ném HttpError.
    fetcher = StubFetcher({"https://w/old": (200, b"<html></html>")})
    stats = CollectRunner(ss, fetcher=fetcher, store=store).run()
    assert stats["sources"]["web1"]["missing"] == 0
    assert store.get_doc_by_key(key)["status"] == "active"
    store.close()


def test_rolling_feed_keeps_archived_articles_active(tmp_path):
    store = CollectStore(tmp_path / 'rolling.db')
    old_key = content_key('https://r/old')
    store.upsert_doc(_doc(old_key, title='Docker archive tutorial'))
    src = _rss_source()
    fetcher = StubFetcher({'https://r/rss': (200, _rss_xml([
        ('Kubernetes backend tutorial', 'https://r/new', 'd')])),
        'https://r/new': (200, PAGE_TPL.format(title='Kubernetes backend tutorial').encode())})
    stats = CollectRunner(_sset(src), fetcher=fetcher, store=store).run()
    assert stats['sources']['rss1']['missing'] == 0
    assert store.get_doc_by_key(old_key)['status'] == 'active'
    store.close()


def test_rolling_feed_restores_seen_document_beyond_fetch_budget(tmp_path):
    store = CollectStore(tmp_path / 'restore.db')
    key = content_key('https://r/old')
    store.upsert_doc(_doc(key, title='Docker archive tutorial'))
    store.mark_missing('rss1')
    src = _rss_source(max_items=1)
    fetcher = StubFetcher({'https://r/rss': (200, _rss_xml([
        ('New Kubernetes tutorial', 'https://r/new', 'd'),
        ('Docker archive tutorial', 'https://r/old', 'd')])),
        'https://r/new': (200, PAGE_TPL.format(title='New Kubernetes tutorial').encode())})
    stats = CollectRunner(_sset(src), fetcher=fetcher, store=store).run()
    assert stats['sources']['rss1']['restored'] == 1
    assert store.get_doc_by_key(key)['status'] == 'active'
    assert 'https://r/old' not in fetcher.calls
    store.close()
