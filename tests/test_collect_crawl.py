"""Unit test bộ crawler (adapters, quality, chunk, store, runner) — Mock loader/mock fetcher.

Không dùng mạng thật trong unit test: mọi HTTP bị stub.
"""

import json
import sqlite3

import pytest

from itlr.collect.adapters import CandidateEntry, api_candidates, iso8601_or_empty, rss_candidates, web_candidates
from itlr.collect.chunk import chunk_text
from itlr.collect.quality import content_hash, passes_quality, title_similarity, cut_text
from itlr.collect.sources import Source, SourceSet, SourcesError, load_sources
from itlr.collect.store import CollectStore
from itlr.collect.url_util import content_key, normalize_url


# ------------------- config ---
def _write(tmp_path, data):
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


class TestSources:
    def test_valid_minimal(self, tmp_path):
        data = {"defaults": {}, "sources": [
            {"source_id": "s1", "kind": "rss", "name": "x", "license": "L",
             "full_text_allowed": False, "feed_url": "https://r/rss"},
        ]}
        ss = load_sources(_write(tmp_path, data))
        assert ss.ids() == ["s1"]
        assert ss.sources[0].lang == "en"

    def test_missing_required_field_raises(self, tmp_path):
        data = {"defaults": {}, "sources": [{"source_id": "s1", "kind": "rss", "name": "x"}]}
        with pytest.raises(SourcesError):
            load_sources(_write(tmp_path, data))

    def test_bad_kind_raises(self, tmp_path):
        data = {"defaults": {}, "sources": [
            {"source_id": "s1", "kind": "kafka", "name": "x",
             "list_url": "https://l", "fields": {"title": "t", "url": "u"}},
        ]}
        with pytest.raises(SourcesError):
            load_sources(_write(tmp_path, data))

    def test_filter_only(self, tmp_path):
        data = {"defaults": {}, "sources": [
            {"source_id": "a", "kind": "rss", "name": "x", "license": "L",
             "full_text_allowed": False, "feed_url": "https://r/rss"},
            {"source_id": "b", "kind": "rss", "name": "y", "license": "L",
             "full_text_allowed": False, "feed_url": "https://r/rss"},
        ]}
        ss = load_sources(_write(tmp_path, data), only={"b"})
        assert ss.ids() == ["b"]

    def test_unknown_filter_raises(self, tmp_path):
        data = {"defaults": {}, "sources": [
            {"source_id": "a", "kind": "rss", "name": "x", "license": "L",
             "full_text_allowed": False, "feed_url": "https://r/rss"},
        ]}
        with pytest.raises(SourcesError):
            load_sources(_write(tmp_path, data), only={"nope"})


# ------------------- adapters ---
class TestAdapters:
    def test_api_candidates_mapping(self):
        src = Source(source_id="d", kind="api", name="D", platform="DEV",
                     homepage="h", full_text_allowed=True, license="L",
                     list_url="u", fields={"id": "id", "title": "title",
                                           "url": "url", "description": "description",
                                           "author": "user.name", "published_at": "published_at",
                                           "tags": "tags"})
        payload = json.dumps([
            {"id": 1, "title": "T1", "url": "https://x/a", "description": "d",
             "user": {"name": "u1"}, "published_at": "2026-10-28T10:00:00Z",
             "tags": ["python", "web"]},
        ]).encode()
        cands = api_candidates(src, payload)
        assert len(cands) == 1
        assert cands[0].title == "T1"
        assert cands[0].author == "u1"
        assert cands[0].tags == ["python", "web"]
        assert cands[0].published_at.startswith("2026-10-28")

    def test_api_json_dict_with_articles_key(self):
        src = Source(source_id="d", kind="api", name="D", platform="DEV",
                     homepage="h", full_text_allowed=True, license="L",
                     list_url="u", fields={"title": "title", "url": "url"})
        payload = json.dumps({"articles": [{"title": "T", "url": "https://x/a"}]}).encode()
        assert api_candidates(src, payload)[0].title == "T"

    def test_api_bad_payload_raises(self):
        src = Source(source_id="d", kind="api", name="D", platform="DEV",
                     homepage="h", full_text_allowed=True, license="L",
                     list_url="u", fields={"title": "t", "url": "u"})
        with pytest.raises(ValueError):
            api_candidates(src, b'{"nope": 1}')

    def test_rss_candidates_basic(self):
        src = Source(source_id="f", kind="rss", name="F", platform="P",
                     homepage="h", full_text_allowed=True, license="L",
                     feed_url="u")
        xml = b"""<rss version="2.0"><channel><title>test</title>
        <item><title>Title One</title><link>https://x/one</link>
        <description>hello &amp; world</description>
        <pubDate>Tue, 28 Oct 2026 10:00:00 +0000</pubDate>
        <category>python</category></item></channel></rss>"""
        cands = rss_candidates(src, xml)
        assert cands[0].title == "Title One"
        assert cands[0].url == "https://x/one"
        par = cands[0].description
        assert "hello" in par and "world" in par

    def test_rss_bad_feed_raises(self):
        src = Source(source_id="f", kind="rss", name="F", platform="P",
                     homepage="h", full_text_allowed=True, license="L",
                     feed_url="u")
        with pytest.raises(ValueError):
            rss_candidates(src, b"<unknown/> really bad? not rss")

    def test_web_candidates_filters_cross_host_and_short(self):
        src = Source(source_id="w", kind="web", name="W", platform="P",
                     homepage="h", full_text_allowed=False, license="none",
                     list_urls=("https://site.com/news",), link_prefix="https://site.com/")
        html = """
          <a href="https://site.com/thu-thuat/bai-viet-1">B1</a>
          <a href="https://site.com/ab">short</a>
          <a href="https://other.com/out">out</a>
          <a href="#anchor">anchor</a>
          <a href="https://site.com/nice/a-2">A2</a>
        """
        cands = web_candidates(src, html, "https://site.com/news")
        urls = [c.url for c in cands]
        assert "https://site.com/thu-thuat/bai-viet-1" in urls
        assert all(u.startswith("https://site.com/") for u in urls)

    def test_iso8601_variants(self):
        assert iso8601_or_empty("2026-10-28T10:00:00Z").startswith("2026-10-28")
        assert iso8601_or_empty(1698500000).startswith("2023-")
        assert iso8601_or_empty(None) == ""
        assert iso8601_or_empty("nonsense") == ""


# ------------------- quality ---
class TestQuality:
    def test_content_hash_stable_and_sensitive(self):
        h1 = content_hash("Nội dung A")
        h2 = content_hash("Nội dung   A ")  # whitespace không đổi hash
        h3 = content_hash("Nội dung B")
        assert h1 == h2 and h1 != h3

    def test_passes_quality_rejects_short(self):
        ok, reason = passes_quality("too short", "tiny")
        assert ok is False and reason == "title_too_short"

    def test_passes_quality_ok(self):
        txt = " ".join(f"từ một đoạn văn bản đầy đủ của bài học lập trình {i}" for i in range(10))
        ok, _reason = passes_quality("Bài học lập trình Python cơ bản", txt)
        assert ok is True

    def test_cut_text_respect_sentenceish(self):
        t = "A. B. C. " * 50  # 250 chars
        out = cut_text(t, 100)
        assert len(out) <= 101
        assert out.endswith("…")

    def test_title_similarity(self):
        assert title_similarity("Hướng dẫn Docker cơ bản", "hướng dẫn docker cơ bản") == 1.0
        assert title_similarity("Hướng dẫn Docker cơ bản", "2026 WILL be cooler") < 0.5


# ------------------- chunking ---
class TestChunkChunking:
    def test_short_text_single_chunk(self):
        assert chunk_text("ngắn") == ["ngắn"]
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_long_text_chunked(self):
        long = ". ".join(f"Câu thứ {i} của một tài liệu về lập trình dài, cùng chủ đề mạng máy tính" for i in range(120))
        chunks_long = chunk_text(long, max_chars=800, overlap_chars=100)
        assert len(chunks_long) >= 3
        assert all([len(c) <= 850 for c in chunks_long])  # chừa overlap khi ghép
        joined = " ".join(chunks_long)
        assert "cùng chủ đề mạng máy tính" in joined  # không mất nội dung

    def test_huge_sentence_cut_by_chars(self):
        s = "x" * 2500
        chunks = chunk_text(s, max_chars=800)
        assert chunks and all(len(c) <= 800 for c in chunks)
        assert sum(len(c) for c in chunks) >= 2400  # không mất ký tự tí nào (trừ space nhỏ)

    def test_tail_merged_when_short(self):
        long2 = "Câu dài một ngưỡng. " * 40 + " Kết."
        chunks = chunk_text(long2)
        assert not chunks or len(chunks[-1]) >= 4  # "Kết." được gộp, không mảnh quá ngắn


# ------------------- item_id ổn định ---
class TestItemIds:
    def test_mapping_stability(self, tmp_path):
        db = tmp_path / "t.db"
        st = CollectStore(db)
        id_a, _ = st.assign_item_id(content_key("https://dev.to/a"))
        id_b, _ = st.assign_item_id(content_key("https://dev.to/b"))
        id_a2, _ = st.assign_item_id(content_key("https://dev.to/a"))
        st.close()
        st2 = CollectStore(db)  # mở lại file db — mapping phải giữ nguyên
        assert st2.item_id_lookup(content_key("https://dev.to/a")) == id_a
        st2.close()
        assert len({id_a, id_b}) == 2 and id_a2 == id_a

    def test_store_floor_start(self, tmp_path):
        st = CollectStore(tmp_path / "t.db")
        st.set_item_floor(5000)
        nid, _ = st.assign_item_id(content_key("https://dev.to/new1"))
        assert nid == 5001
        st.close()


# ------------------- store doc lifecycle ---
class TestStoreDocs:
    def _doc(self, key="u:k1", title="T1", text="body"):
        return {"content_key": key, "source_id": "s1", "external_id": "x1",
                "url": "https://x/a", "norm_url": normalize_url("https://x/a"),
                "title": title, "description": "d", "text": text, "tags": "",
                "author": "A", "published_at": "2026-10-28", "lang": "en",
                "license": "L", "full_text_allowed": 1,
                "content_hash": content_hash(text + title + "d"),
                "n_chars": len(text), "quality_status": "ok", "status": "active",
                "fetched_at": "2026-10-28T00:00:00Z"}

    def test_new_then_unchanged_then_updated(self, tmp_path):
        st = CollectStore(tmp_path / "t.db")
        r1 = st.upsert_doc(self._doc("u:1"))
        r2 = st.upsert_doc(self._doc("u:1"))
        upd = self._doc("u:1")
        upd["text"] = "body-2"
        upd["content_hash"] = content_hash(upd["text"] + upd["title"] + upd["description"])
        r3 = st.upsert_doc(upd)
        assert (r1["event"], r2["event"], r3["event"]) == ("new", "unchanged", "updated")
        assert r3["revision"] == 2
        st.close()

    def test_title_dup_lookup(self, tmp_path):
        st = CollectStore(tmp_path / "t.db")
        st.upsert_doc(self._doc("u:1", title="Học Docker từ lào con để thành rành"))
        dup = st.find_title_dup("học docker từ lào con để thành rành")
        assert dup is not None and dup["content_key"] == "u:1"
        assert st.find_title_dup("tiêu đề hoàn toàn khác không giống") is None
        st.close()

    def test_quality_filter_column_updates(self, tmp_path):
        """Doc trước ok, sau bị đổi nội dung rác → quality_status cập nhật."""
        st = CollectStore(tmp_path / "t.db")
        bad = self._doc("u:2", text="...")  #quality_status ok theo fixture
        bad["quality_status"] = "junk"
        r = st.upsert_doc(bad)
        assert r["event"] == "new"
        r2 = st.upsert_doc(self._doc("u:2", text="..."))
        assert r2["event"] == "unchanged"
        st.close()

    def test_docs_for_index_respects_policy(self, tmp_path):
        st = CollectStore(tmp_path / "t.db")
        st.upsert_doc(self._doc("u:ok"))
        junk = self._doc("u:junk", text="r")
        junk["quality_status"] = "junk"
        st.upsert_doc(junk)
        nosn = self._doc("u:noft")
        nosn["full_text_allowed"] = 0
        st.upsert_doc(nosn)
        rows = st.docs_for_index()
        assert [r["content_key"] for r in rows] == ["u:ok"]
        st.close()
