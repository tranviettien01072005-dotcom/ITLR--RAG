"""Integration-lite cho CollectRunner: fetcher stub trong bộ nhớ — KHÔNG mạng thật.

Kiểm tra luồng end-to-end của 1 lượt thu thập: robots→fetch→extract→quality→store,
chống trùng, cập nhật thay đổi, snippet-only cho nguồn không cho phép full-text.
"""

import pytest

from itlr.collect.http import HttpError
from itlr.collect.runner import CollectRunner
from itlr.collect.store import CollectStore
from itlr.collect.sources import Source, SourceSet

PAGE_TPL = ("<html><head><title>W</title></head><body><article>"
            "<h1>{title}</h1><p>" + ("nội dung học lập trình thật. " * 25) + "</p></article>"
            "</body></html>")


class StubFetcher:
    """Thay HttpFetcher: returns (status, bytes) theo map. Thiếu URL → HttpError."""

    def __init__(self, responses: dict):
        self.responses = responses  # url → (status, bytes)
        self.calls: list[str] = []

    def fetch(self, url, *, respect_robots=True):
        self.calls.append(url)
        item = self.responses.get(url)
        if item is None:
            raise HttpError(f"không cấu hình mock cho {url}")
        return item


def _sourceset(tmp_path, **overrides):
    rss = Source(source_id="rss1", kind="rss", name="R", platform="P", homepage="h",
                 full_text_allowed=True, license="L", feed_url="https://r/rss",
                 lang="vi", max_items_per_run=10)
    web = Source(source_id="web1", kind="web", name="W", platform="P", homepage="h",
                 full_text_allowed=False, license="none",
                 list_urls=("https://w/news",), lang="vi")
    return SourceSet(defaults={"recheck_after_hours": 24, "min_text_chars": 80,
                               "min_title_chars": 8, "max_text_chars": 3000},
                     sources=(rss, web))


def _rss_xml(items):
    entries = "".join(
        f"<item><title>{t}</title><link>{u}</link><description>{d}</description></item>"
        for t, u, d in items)
    return f"<rss version='2.0'><channel><title>r</title>{entries}</channel></rss>".encode()


class TestRunner:
    def test_full_flow_rss_new_then_recheck_skip(self, tmp_path):
        ss = _sourceset(tmp_path)
        store = CollectStore(tmp_path / "c.db")
        page = PAGE_TPL.format(title="Hướng dẫn Docker cơ bản cho người mới bắt đầu")
        fetcher = StubFetcher({
            "https://r/rss": (200, _rss_xml([("Hướng dẫn Docker cơ bản cho lập trình viên",
                                              "https://blog.dev/docker-co-ban", "giới thiệu")])),
            "https://blog.dev/docker-co-ban": (200, page.encode("utf-8")),
        })
        stats = CollectRunner(ss, fetcher=fetcher, store=store).run()
        assert stats["sources"]["rss1"]["new"] == 1

        # Lượt 2 NGAY SAU: trong cửa sổ recheck_after_hours → skip (không tái fetch)
        stats2 = CollectRunner(ss, fetcher=fetcher, store=store).run(sources=(ss.sources[0],))
        assert stats2["sources"]["rss1"]["skipped"] == 1
        assert stats2["sources"]["rss1"]["unchanged"] == 0
        assert fetcher.calls.count("https://blog.dev/docker-co-ban") == 1  # chỉ fetch 1 lần

    def test_changed_content_detected_on_refetch(self, tmp_path):
        ss = _sourceset(tmp_path)
        store = CollectStore(tmp_path / "c.db")
        url = "https://blog.dev/k8s"
        f1 = StubFetcher({
            "https://r/rss": (200, _rss_xml([("Kubernetes cho người mới", url, "d")])),
            url: (200, PAGE_TPL.format(title="Kubernetes cho người mới").encode("utf-8")),
        })
        stats1 = CollectRunner(ss, fetcher=f1, store=store).run(sources=(ss.sources[0],))
        assert stats1["sources"]["rss1"]["new"] == 1

        page2 = ("<html><head><title>W2</title></head><body><article>"
                 "<h1>Kubernetes cho người mới</h1><p>"
                 + ("nội dung cập nhật k8s version 1.30. " * 20) +
                 "</p></article></body></html>")
        f2 = StubFetcher({
            "https://r/rss": (200, _rss_xml([("Kubernetes cho người mới", url, "d")])),
            url: (200, page2.encode("utf-8")),
        })
        # ép recheck=0 giờ để lượt 2 fetch lại thật
        ss2 = SourceSet(defaults={**ss.defaults, "recheck_after_hours": 0}, sources=ss.sources)
        stats2 = CollectRunner(ss2, fetcher=f2, store=store).run(sources=(ss.sources[0],))
        assert stats2["sources"]["rss1"]["updated"] == 1
        row = dict(store._conn.execute("SELECT * FROM docs WHERE source_id='rss1'").fetchone())
        assert row["revision"] == 2

    def test_web_snippet_only(self, tmp_path):
        ss = _sourceset(tmp_path)
        store = CollectStore(tmp_path / "c.db")
        listing = "<html><body><a href='/thu-thuat/bai-viet.html'>t</a></body></html>"
        checkpage = ("<html><head><title>x</title>"
                     "<meta name='description' content='Công nghệ 24h: cập nhật tin tức khoa "
                     "học công nghệ hàng ngày, tổng hợp dữ liệu thị trường và phân tích xu "
                     "hướng sản phẩm mới nhất cho bạn đọc chuyên ngành.'/></head>"
                     "<body><article><h1>Kinh nghiệm học lập trình web frontend từ con số 0"
                     "</h1></article></body></html>")
        fetcher = StubFetcher({
            "https://w/news": (200, listing.encode()),
            "https://w/thu-thuat/bai-viet.html": (200, checkpage.encode("utf-8")),
        })
        stats = CollectRunner(ss, fetcher=fetcher, store=store).run(sources=(ss.sources[1],))
        assert stats["sources"]["web1"]["new"] == 1
        # nguồn không cho phép full-text → KHÔNG vào index (docs_for_index full_text=1)
        assert store.docs_for_index() == []
        row = dict(store._conn.execute("SELECT * FROM docs").fetchone())
        assert row["text"] == ""
        assert "lập trình web frontend" in row["title"].lower()
        assert len(row["description"]) > 40  # snippet có nội dung

    def test_down_source_does_not_kill_run(self, tmp_path):
        ss = _sourceset(tmp_path)
        store = CollectStore(tmp_path / "c.db")
        fetcher = StubFetcher({"https://r/rss": (503, b"busy")})
        stats = CollectRunner(ss, fetcher=fetcher, store=store).run()
        assert "error" in stats["sources"]["rss1"]

    def test_404_article_rejected(self, tmp_path):
        ss = _sourceset(tmp_path)
        store = CollectStore(tmp_path / "c.db")
        fetcher = StubFetcher({
            "https://r/rss": (200, _rss_xml([("Bài lập trình Python cho người mới",
                                              "https://r/gone", "d")])),
            "https://r/gone": (404, b"not found"),
        })
        stats = CollectRunner(ss, fetcher=fetcher, store=store).run()
        assert stats["sources"]["rss1"]["quality_rejected"] == 1
        assert store.stats()["docs_total"] == 0

    def test_budget_caps_fetches(self, tmp_path):
        """budget max_items_per_run=2 → tối đa 2 bài fetch, phần còn bỏ qua."""
        rss = Source(source_id="rss1", kind="rss", name="R", platform="P", homepage="h",
                     full_text_allowed=True, license="L", feed_url="https://r/rss",
                     lang="vi", max_items_per_run=2)
        ss = SourceSet(defaults={"min_text_chars": 80, "min_title_chars": 8},
                       sources=(rss,))
        items = [(f"Bài học lập trình số {i} về Docker và CI/CD pipeline",
                  f"https://r/a-{i}", "d") for i in range(8)]
        fetcher = StubFetcher({
            "https://r/rss": (200, _rss_xml(items)),
            **{f"https://r/a-{i}": (200, PAGE_TPL.format(
                title=f"Bài học lập trình số {i}").encode()) for i in range(8)}
        })
        store = CollectStore(tmp_path / "budget.db")
        stats = CollectRunner(ss, fetcher=fetcher, store=store).run()
        assert stats["sources"]["rss1"]["new"] == 2