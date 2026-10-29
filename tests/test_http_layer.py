"""Test tầng HTTP thu thập: robots.txt an toàn, rate limit, retry/backoff.

Không gọi mạng thật trong unit test — mỗi phần nền tảng được inject hàm fetch/sleep.
"""

import urllib.robotparser

import pytest

from itlr.collect.http import HttpError, HttpFetcher, RateLimiter, RobotsCtx


class RobotsScripted:
    """RobotsCtx với fetcher giả: map URL → nội dung/exception."""

    def __init__(self, mapping=None, exc=None):
        self.mapping = mapping or {}
        self.exc = exc
        self.calls = []

    def _fetch(self, url, timeout):
        self.calls.append(url)
        if self.exc:
            raise self.exc
        return self.mapping.get(url, "")

    def make_ctx(self):
        return RobotsCtx(timeout=1.0, fetcher=self._fetch, ttl=3600.0)


class TestRobots:
    def test_empty_robots_allows_everything(self):
        s = RobotsScripted({})
        ctx = s.make_ctx()
        ok, delay = ctx.allowed("https://example.net/any-url")
        assert ok is True and delay == 0.0

    def test_disallow_blocks(self):
        s = RobotsScripted({"https://example.net/robots.txt":
                            "User-agent: *\nDisallow: /private/\n"})
        ctx = s.make_ctx()
        assert ctx.allowed("https://example.net/private/x")[0] is False
        assert ctx.allowed("https://example.net/public/y")[0] is True

    def test_crawl_delay_reported(self):
        s = RobotsScripted({"https://example.net/robots.txt":
                            "User-agent: *\nCrawl-delay: 7\nDisallow:\n"})
        ctx = s.make_ctx()
        ok, delay = ctx.allowed("https://example.net/public/y")
        assert ok is True and delay == 7.0

    def test_robots_404_allows(self):
        ctx = RobotsCtx(timeout=1.0, fetcher=_fetch404)
        assert ctx.allowed("https://example.net/x")[0] is True

    def test_robots_unreachable_blocks_deny_by_default(self):
        def fetch(url, timeout):
            raise ConnectionError("network down")
        ctx = RobotsCtx(timeout=1.0, fetcher=fetch)
        assert ctx.allowed("https://example.net/x")[0] is False

    def test_cache_reuses_robots(self):
        s = RobotsScripted({"https://example.net/robots.txt": "User-agent: *\nDisallow:\n"})
        ctx = s.make_ctx()
        ctx.allowed("https://example.net/a")
        ctx.allowed("https://example.net/b")
        assert s.calls.count("https://example.net/robots.txt") == 1


def _fetch404(url, timeout):
    import urllib.error

    raise urllib.error.HTTPError(url, 404, "not found", hdrs=None, fp=None)


class TestRateLimiter:
    def test_first_call_no_wait_second_respects_interval(self):
        sleeps = []
        rl = RateLimiter(min_interval=2.0, jitter=0.0, sleeper=sleeps.append)
        rl.wait("api.x.com")
        assert sleeps == []  # lượt đầu chờ 0
        rl.wait("api.x.com")
        assert sleeps and sleeps[0] == pytest.approx(2.0, abs=1e-3)  # độ chính xác clock
        # host khác không bị trừng phạt:
        sleeps.clear()
        rl.wait("other.com")
        assert sleeps == []

    def test_replace_by_larger_crawl_delay(self):
        sleeps = []
        rl = RateLimiter(min_interval=1.0, jitter=0.0, sleeper=sleeps.append)
        rl.wait("h", extra_delay=0)
        rl.wait("h", extra_delay=5.0)
        assert sleeps[0] == pytest.approx(5.0)


class TestFetcher:
    def _fetcher(self, rate=False, robots=None, max_retries=2, backoff_base=0.0):
        rl = RateLimiter(min_interval=0, jitter=0,
                         sleeper=lambda s: None) if rate else None
        return HttpFetcher(max_retries=max_retries, backoff_base=backoff_base,
                           rate_limiter=rl, robots=robots)

    def _mock_client_factory(self, responses):
        """Trả về class thay thế httpx.Client: get() tuần tự pop từ responses.

        responses: list of (status, content) hoặc Exception.
        """
        calls = {"n": 0, "urls": []}

        class FakeResp:
            def __init__(self, status, content):
                self.status_code = status
                self.content = content
                self.text = content.decode()

        class FakeClient:
            def __init__(self, *a, **k):
                self.hooks = k.get("event_hooks", {}).get("request", [])

            def get(self, url):
                for hook in self.hooks:
                    hook(type("Request", (), {"url": url})())
                calls["urls"].append(url)
                item = responses[min(calls["n"], len(responses) - 1)]
                calls["n"] += 1
                if isinstance(item, Exception):
                    raise item
                return FakeResp(*item)

            def close(self):
                pass

        return FakeClient, calls

    def test_success(self):
        f = self._fetcher()
        FakeClient, calls = self._mock_client_factory([(200, b"hello")])
        f._httpx = type("H", (), {"Client": FakeClient,
                                  "Timeout": staticmethod(lambda t, connect: t),
                                  "TimeoutException": type("TE", (Exception,), {}),
                                  "TransportError": type("TR", (Exception,), {})})
        status, body = f.fetch("https://example.net/page")
        assert status == 200 and body == b"hello"

    def test_retry_then_success(self):
        f = self._fetcher(max_retries=2, backoff_base=0.0)
        FakeClient, calls = self._mock_client_factory(
            [(503, b"busy"), (503, b"busy"), (200, b"good")])
        f._httpx = type("H", (), {"Client": FakeClient,
                                  "Timeout": staticmethod(lambda t, connect: t),
                                  "TimeoutException": type("TE", (Exception,), {}),
                                  "TransportError": type("TR", (Exception,), {})})
        status, body = f.fetch("https://example.net/page")
        assert status == 200 and body == b"good"
        assert calls["n"] == 3  # 2 lỗi + 1 thành công

    def test_exhaust_retries_raises(self, caplog):
        f = self._fetcher(max_retries=1, backoff_base=0.0)
        FakeClient, calls = self._mock_client_factory([(500, b"x")])
        f._httpx = type("H", (), {"Client": FakeClient,
                                  "Timeout": staticmethod(lambda t, connect: t),
                                  "TimeoutException": type("TE", (Exception,), {}),
                                  "TransportError": type("TR", (Exception,), {})})
        with caplog.at_level("ERROR", logger="itlr.collect"):
            with pytest.raises(HttpError):
                f.fetch("https://example.net/page")
        assert calls["n"] == 2
        assert any("HẾT SỐ lần thử" in r.message for r in caplog.records)

    def test_404_no_retry(self):
        f = self._fetcher(max_retries=3)
        FakeClient, calls = self._mock_client_factory([(404, b"not found")])
        f._httpx = type("H", (), {"Client": FakeClient,
                                  "Timeout": staticmethod(lambda t, connect: t),
                                  "TimeoutException": type("TE", (Exception,), {}),
                                  "TransportError": type("TR", (Exception,), {})})
        status, _ = f.fetch("https://example.net/missing")
        assert status == 404
        assert calls["n"] == 1  # không giật máy chủ

    def test_robots_denied_raises_before_http(self):
        ctx = RobotsCtx(fetcher=lambda u, t: "", ttl=3600.0)
        class Deny:
            @staticmethod
            def allowed(url):
                return False, 0.0
        f = self._fetcher(robots=Deny())
        with pytest.raises(HttpError):
            f.fetch("https://example.net/anything")


def test_redirect_target_is_checked_before_fetching_and_each_hop_is_throttled(monkeypatch):
    import httpx

    visited = []
    throttled = []
    checked = []

    def respond(request):
        visited.append(str(request.url))
        return httpx.Response(302, headers={"Location": "https://blocked.test/private"})

    class Robots:
        def allowed(self, url):
            checked.append(url)
            return ("blocked.test" not in url), 4.0

    class Rate:
        def wait(self, host, extra_delay=0):
            throttled.append((host, extra_delay))

    original_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    fetcher = HttpFetcher(robots=Robots(), rate_limiter=Rate(), max_retries=0)
    with pytest.raises(HttpError):
        fetcher.fetch("https://allowed.test/start")
    assert visited == ["https://allowed.test/start"]
    assert "https://blocked.test/private" in checked
    assert throttled == [("allowed.test", 4.0)]


def test_each_retry_and_allowed_redirect_obeys_rate_limit(monkeypatch):
    import httpx

    visited = []
    throttled = []

    def respond(request):
        url = str(request.url)
        visited.append(url)
        if url.endswith("/start"):
            return httpx.Response(302, headers={"Location": "https://other.test/end"})
        return httpx.Response(503 if len(visited) == 2 else 200, content=b"ok")

    class Rate:
        def wait(self, host, extra_delay=0):
            throttled.append(host)

    original_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    monkeypatch.setattr("itlr.collect.http.time.sleep", lambda _: None)
    fetcher = HttpFetcher(rate_limiter=Rate(), max_retries=1, backoff_base=0)
    assert fetcher.fetch("https://allowed.test/start") == (200, b"ok")
    assert throttled == ["allowed.test", "other.test", "allowed.test", "other.test"]
