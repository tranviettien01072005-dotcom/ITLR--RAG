"""Khối kiểm tra robots.txt + rate limiting + HTTP client có retry/backoff/timeout.

Đảm bảo "chỉ thu thập nguồn ĐƯỢC PHÉP":
- robots: robotparser của urllib, cache theo host; khi KHÔNG tải được robots.txt
  (lỗi mạng/5xx) thì coi như KHÔNG ĐƯỢC phép (cẩn trọng theo chuẩn RFC 9309);
  404/403/410 hoặc robots trống nghĩa là mọi URL được phép.
- rate: thời gian tối thiểu giữa 2 lần gọi đến CÙNG host + jitter, chống spam máy chủ;
  tôn trọng Crawl-delay trong robots.txt.
- client: fetch() trả (status, body_bytes); retry exponential backoff + jitter cho
  429/5xx/timeout; mọi lỗi đều được LOG — không nuốt âm thầm (sàn CONSTRAINTS §2).
"""

from __future__ import annotations

import logging
import random
import time
import urllib.request
import urllib.robotparser
import urllib.parse

LOG = logging.getLogger("itlr.collect")

USER_AGENT = ("Mozilla/5.0 (compatible; ITLR-RAG/2.0; academic-research-crawler)")


class RobotsCtx:
    """Kiểm tra robots.txt theo host, cache TTL (mặc định 1h/host)."""

    def __init__(self, timeout=10.0, user_agent=USER_AGENT, fetcher=None, ttl=3600.0):
        self.timeout = float(timeout)
        self.user_agent = user_agent
        self._fetcher = fetcher or self._default_fetch
        self._ttl = float(ttl)
        self._cache: dict[str, tuple[dict, float]] = {}  # host → ({"kind": parsed|empty|unknown}, ts)

    @staticmethod
    def _default_fetch(url, timeout):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _robots_for(self, scheme_netloc: str):
        """Trả về ("rp", RobotFileParser) | ("empty", None) | ("unknown", None)."""
        now = time.time()
        hit = self._cache.get(scheme_netloc)
        if hit and now - hit[1] < self._ttl:
            return hit[0]

        kind, parser = "unknown", None
        try:
            text = self._fetcher(f"https://{scheme_netloc}/robots.txt", self.timeout)
            parser = urllib.robotparser.RobotFileParser()
            if text.strip():
                parser.parse(text.splitlines())
                kind = "rp"
            else:
                kind = "empty"
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None)
            if code in (403, 404, 410):
                LOG.info("robots.txt %s → HTTP %s (không tồn tại/khóa → cho phép crawl)",
                         scheme_netloc, code)
                kind = "empty"
            else:
                LOG.warning("robots.txt %s KHÔNG truy cập được (%s) → TỪ CHỐI crawl "
                            "theo mặc định an toàn đến khi kiểm tra được (RFC 9309).",
                            scheme_netloc, exc)
                kind = "unknown"

        self._cache[scheme_netloc] = ((kind, parser), now)
        return (kind, parser)

    def allowed(self, url) -> tuple[bool, float]:
        """Trả về (cho_phép, crawl_delay_s). Delay = Crawl-delay nếu robotparser khai báo."""
        p = urllib.parse.urlsplit(url)
        kind, parser = self._robots_for(p.netloc)
        if kind == "unknown" or (kind == "rp" and parser is None):
            return False, 0.0
        if kind == "empty":
            return True, 0.0
        ok = parser.can_fetch(self.user_agent, url)
        if not ok:
            LOG.info("robots.txt từ chối: %s", url)
            return False, 0.0
        delay = 0.0
        try:
            d = parser.crawl_delay(self.user_agent)
            delay = float(d) if d else 0.0
        except Exception:  # noqa: BLE001
            delay = 0.0
        return True, delay


class RateLimiter:
    """Giới hạn tần suất: >= min_interval giây giữa 2 lần gọi cùng host (+ jitter).

    Tuần tự, không thread pool — đơn giản, dễ đoán, tiết kiệm tài nguyên.
    """

    def __init__(self, min_interval=3.0, jitter=0.5, sleeper=time.sleep):
        self.min_interval = float(min_interval)
        self.jitter = float(jitter)
        self._sleeper = sleeper
        self._last: dict[str, float] = {}

    def wait(self, host: str, extra_delay: float = 0.0) -> float:
        """Chờ đến lượt của `host`; trả về số giây đã chờ."""
        now = time.monotonic()
        last = self._last.get(host, 0.0)
        base = max(self.min_interval, float(extra_delay))
        wait_s = (last + base) - now
        if self.jitter and wait_s > 0:
            wait_s += random.uniform(0, self.jitter)
        sleep_s = max(0.0, wait_s)
        if sleep_s > 0:
            self._sleeper(sleep_s)
        self._last[host] = time.monotonic()
        return sleep_s


class HttpError(Exception):
    """Fetch thất bại sau hết số lần thử (hoặc bị robots từ chối)."""


class HttpFetcher:
    """HTTP fetch (httpx, tạo client mới cho từng lần gọi — không dùng chung),

    retry exponential backoff cho 429/5xx/timeout, tôn trọng robots + rate limit.
    Trả (status, body_bytes). 4xx khác không retry — caller tự quyết định.
    """

    def __init__(self, timeout_connect=15.0, request_timeout=30.0,
                 max_retries=3, backoff_base=1.6, backoff_cap=30.0,
                 user_agent=USER_AGENT, rate_limiter=None, robots=None):
        import httpx  # import cục bộ để unit test không cần httpx nếu không fetch

        self._httpx = httpx
        self.timeout_connect = float(timeout_connect)
        self.request_timeout = float(request_timeout)
        self.max_retries = int(max_retries)
        self.backoff_base = float(backoff_base)
        self.backoff_cap = float(backoff_cap)
        self.user_agent = user_agent
        self.rate: RateLimiter | None = rate_limiter
        self.robots: RobotsCtx | None = robots

    def _new_client(self):
        timeout = self._httpx.Timeout(self.request_timeout, connect=self.timeout_connect)
        return self._httpx.Client(
            timeout=timeout, follow_redirects=True,
            headers={"User-Agent": self.user_agent},
        )

    def _throttle(self, url: str, crawl_delay: float = 0.0):
        if self.rate is not None:
            self.rate.wait(urllib.parse.urlsplit(url).netloc, extra_delay=crawl_delay)

    def fetch(self, url: str, *, respect_robots=True) -> tuple[int, bytes]:
        """Fetch URL → (status, body_bytes); raise HttpError nếu robots chặn hoặc hết retry."""
        if self.robots is not None and respect_robots:
            ok, crawl_delay = self.robots.allowed(url)
            if not ok:
                raise HttpError(f"robots.txt từ chối: {url}")
            self._throttle(url, crawl_delay)
        else:
            self._throttle(url)

        cap = max(0, self.max_retries)
        last_err = None
        for attempt in range(cap + 1):
            client = None
            try:
                client = self._new_client()
                resp = client.get(url)
                code = resp.status_code
                if 200 <= code < 300:
                    return code, resp.content
                if code == 429 or 500 <= code < 600:
                    last_err = f"HTTP {code} retryable"
                    raise HttpError(last_err)
                # 4xx khác (404/401/...) — không retry
                LOG.info("fetch %s → HTTP %s (không retry)", url, code)
                return code, resp.content
            except self._httpx.TimeoutException as exc:
                last_err = f"timeout: {exc}"
            except self._httpx.TransportError as exc:
                last_err = f"lỗi mạng: {exc}"
            except HttpError as exc:
                last_err = str(exc)
            except Exception as exc:  # noqa: BLE001
                LOG.warning("fetch ngoài dự kiến %s: %s", url, exc)
                last_err = f"ngoài dự kiến: {exc}"
            finally:
                if client is not None:
                    client.close()

            if attempt < cap:
                delay = min(self.backoff_cap, self.backoff_base ** attempt)
                delay *= random.uniform(0.6, 1.4)
                LOG.warning("fetch %s thử %d/%d lỗi (%s) — chờ %.1fs rồi thử lại",
                            url, attempt + 1, cap + 1, last_err, delay)
                time.sleep(delay)

        LOG.error("fetch HẾT SỐ lần thử (%d): %s — lỗi cuối: %s", cap + 1, url, last_err)
        raise HttpError(f"{last_err} sau {cap + 1} lần thử: {url}")
