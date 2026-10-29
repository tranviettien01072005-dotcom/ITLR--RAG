"""Unit test cho các tiện ích của tầng thu thập dữ liệu: URL chuẩn hóa & ID ổn định.

Mỗi test tái hiện đây là hợp đồng sẽ được dùng từ crawler → index: URL trục trặc
(tracking, http/https, trailing slash...) phải quy về MỘT khóa bền vững.
"""

import pytest

from itlr.collect import url_util


class TestNormalizeUrl:
    def test_keeps_plain_url(self):
        u = "https://dev.to/user/some-post-abc"
        assert url_util.normalize_url(u) == u

    def test_strips_utm_and_click_tracking(self):
        u = "https://site.com/p.html?utm_source=feed&utm_medium=rss&gclid=abc&keep=1"
        out = url_util.normalize_url(u)
        assert out.startswith("https://site.com/p.html")
        assert "gclid" not in out and "utm_" not in out
        assert out.endswith("keep=1")

    def test_strips_fragment(self):
        u = "https://site.com/p.html#section-2"
        assert url_util.normalize_url(u) == "https://site.com/p.html"

    def test_lowercases_host_keeps_path_case(self):
        out = url_util.normalize_url("https://DEV.to/Post-SomeThing/Path")
        assert out == "https://dev.to/Post-SomeThing/Path"

    def test_http_to_https_same_host(self):
        u = "http://dev.to/post"
        assert url_util.normalize_url(u) == "https://dev.to/post"

    def test_removes_empty_query_and_trailing_slash(self):
        assert url_util.normalize_url("https://dev.to/post?") == "https://dev.to/post"
        assert url_util.normalize_url("https://dev.to/post/") == "https://dev.to/post"

    def test_decodes_percent_encoding_consistent(self):
        # "%41" == "A" → hai cách viết phải quy về MỘT URL đại diện
        assert url_util.normalize_url("https://dev.to/p%41th") == "https://dev.to/pAth"
        assert url_util.content_key("https://dev.to/p%41th") == \
            url_util.content_key("https://dev.to/pAth")

    def test_invalid_returns_none(self):
        assert url_util.normalize_url("") is None
        assert url_util.normalize_url("not a url") is None
        assert url_util.normalize_url(None) is None

    def test_query_key_order_irrelevant(self):
        a = url_util.normalize_url("https://x.dev/p?a=1&b=2")
        b = url_util.normalize_url("https://x.dev/p?b=2&a=1")
        assert a == b


class TestContentKey:
    def test_stable_across_insignificant_changes(self):
        a = url_util.content_key("https://Dev.to/post/?utm=1#top")
        b = url_util.content_key("https://dev.to/post/")
        assert a == b

    def test_differs_for_different_pages(self):
        assert url_util.content_key("https://dev.to/a") != url_util.content_key("https://dev.to/b")

    def test_hash_shape(self):
        k = url_util.content_key("https://dev.to/a")
        assert isinstance(k, str) and len(k) == 42 and k.startswith("u:")  # "u:" + sha1 hex 40


def test_content_key_sha1_is_explicitly_nonsecurity(monkeypatch):
    """URL IDs stay stable while declaring the digest is not an integrity primitive."""
    import hashlib
    from itlr.collect import url_util

    original = hashlib.sha1
    calls = []

    def checked_sha1(data, **kwargs):
        calls.append(kwargs)
        return original(data, **kwargs)

    expected = 'u:' + original(b'https://example.com/article', usedforsecurity=False).hexdigest()
    monkeypatch.setattr(url_util.hashlib, 'sha1', checked_sha1)
    assert url_util.content_key('https://example.com/article?utm_source=test') == expected
    assert calls == [{'usedforsecurity': False}]
