"""Orchestrator một lượt thu thập: nguồn → kiểm robots/rate → fetch → trích → lọc chất lượng → SQLite.

Mỗi lượt:
1) úpsert metadata nguồn (provenance)
2) với từng nguồn: lấy danh sách ứng viên (api/rss/listing-web)
3) với từng ứng viên: chuẩn hóa URL; skip nếu đã rõ trong recheck cửa sổ;
   fetch trang (robots + rate + retry) → trích title/text/meta
4) lọc chất lượng → upsert SQLite (new / updated / unchanged)
5) tổng kết trả dict (dùng cho CLI + pipeline auto refresh)

Từ chối lọc chủ thể — KHÔNG sửa nội dung, KHÔNG bịa ngoài dữ liệu thực nhận.
"""

from __future__ import annotations

import logging
import time

from itlr.collect.adapters import api_candidates, rss_candidates, web_candidates
from itlr.collect.extract import extract_meta, extract_page_text, strip_boilerplate
from itlr.collect.http import HttpError, HttpFetcher, RateLimiter, RobotsCtx
from itlr.collect.quality import content_hash, cut_text, passes_quality, title_similarity
from itlr.collect.store import CollectStore
from itlr.collect.url_util import content_key, normalize_url
from itlr.collect.sources import Source, SourceSet

LOG = logging.getLogger("itlr.collect")

NEAR_DUP_TITLE_TH = 0.80


class CollectRunner:
    def __init__(self, source_set: SourceSet, *, fetcher=None, store=None,
                 recheck_after_hours=None):
        from itlr import config

        self.sset = source_set
        self.store = store or CollectStore(config.COLLECT_DB)
        self.recheck_h = float(
            recheck_after_hours if recheck_after_hours is not None
            else source_set.defaults.get("recheck_after_hours", 24))
        self.fetcher = fetcher or HttpFetcher(
            timeout_connect=15.0, request_timeout=30.0,
            max_retries=3, rate_limiter=RateLimiter(min_interval=3.0, jitter=0.5),
            robots=RobotsCtx(timeout=10.0))
        self._stats = self._fresh_stats()

    @staticmethod
    def _fresh_stats() -> dict:
        base = {"sources": {}, "robots_blocked": 0, "fetch_errors": 0,
                "quality_rejected": 0, "duplicates_skipped": 0, "skipped_recheck": 0}
        return base

    def run(self, sources: tuple[Source, ...] | None = None) -> dict:
        sources = tuple(sources or self.sset.sources)
        t0 = time.time()
        self._stats = self._fresh_stats()
        for src in sources:
            try:
                self._collect_source(src)
            except (HttpError, ValueError) as exc:
                LOG.error("Nguồn %s lỗi ở cấp nguồn (bỏ qua, tiếp nguồn khác): %s",
                          src.source_id, exc)
                self._stats["sources"][src.source_id] = {"error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                LOG.exception("Nguồn %s NGOÀI DỰ KIẾN lỗi: %s", src.source_id, exc)
                self._stats["sources"][src.source_id] = {"error": str(exc)}
        self._stats["seconds"] = round(time.time() - t0, 1)
        totals = self._stats["totals"] = {
            "new": 0, "updated": 0, "unchanged": 0, "quality_rejected": 0,
            "duplicates": 0, "skipped": 0}
        for s in self._stats["sources"].values():
            for k in totals:
                totals[k] += int(s.get(k, 0))
        return self._stats

    # ---------- per source ----------
    def _collect_source(self, src: Source) -> None:
        self.store.upsert_source(src.as_dict())
        entries = self._list_entries(src)
        seen_keys: set[str] = set()
        counts = {"new": 0, "updated": 0, "unchanged": 0, "quality_rejected": 0,
                  "duplicates": 0, "skipped": 0}
        budget = src.max_items_per_run or (self.sset.defaults.get("max_items_per_run")) or 25

        for entry in entries[:budget]:
            norm = normalize_url(entry.url)
            if not norm or not content_key(entry.url):
                counts["quality_rejected"] += 1  # URL chết → không dùng được
                continue
            ckey = content_key(entry.url)
            if ckey in seen_keys:
                counts["duplicates"] += 1
                self._stats["duplicates_skipped"] += 1
                continue
            seen_keys.add(ckey)

            doc0 = self.store.get_doc_by_key(ckey)
            if doc0 and _fetched_recently(doc0, self.recheck_h):
                counts["skipped"] += 1
                self._stats["skipped_recheck"] += 1
                continue

            if doc0 is None:
                # chống trùng tiêu đề giữa nguồn (near-dup không URL trùng)
                dup = self.store.find_title_dup(entry.title.strip().lower())
                if dup is not None and title_similarity(dup["title"], entry.title) \
                        >= NEAR_DUP_TITLE_TH:
                    LOG.info("Chống trùng tiêu đề (lặp gần với doc %s): %s",
                             dup["doc_id"], entry.title[:60])
                    counts["duplicates"] += 1
                    continue

            try:
                doc = self._fetch_article(src, entry, ckey, norm)
            except HttpError as exc:
                counts["quality_rejected"] += 1
                self._stats["fetch_errors"] += 1
                LOG.warning("[!] fetch lỗi %s: %s", entry.url, exc)
                continue
            if doc is None:
                counts["quality_rejected"] += 1
                self._stats["quality_rejected"] += 1
                continue

            res = self.store.upsert_doc(doc)
            ev = {"new": "new", "updated": "updated",
                  "updated_quality": "updated", "unchanged": "unchanged"}.get(
                      res["event"], "unchanged")
            counts[ev] += 1
        self._stats["sources"][src.source_id] = counts
        LOG.info("[OK] Nguồn %s: %s", src.source_id, counts)

    def _list_entries(self, src: Source):
        if src.kind == "api":
            _, payload = self.fetcher.fetch(src.list_url)
            return api_candidates(src, payload)
        if src.kind == "rss":
            _, payload = self.fetcher.fetch(src.feed_url)
            return rss_candidates(src, payload)
        # web: mọi trang listing
        entries = []
        for lu in src.list_urls:
            try:
                _, payload = self.fetcher.fetch(lu)
                entries += web_candidates(src, payload.decode("utf-8", errors="replace"), lu)
            except HttpError as exc:
                LOG.warning("[!] Listing %s lỗi: %s (bỏ qua trang này)", lu, exc)
                self._stats["fetch_errors"] += 1
        return entries

    def _fetch_article(self, src: Source, entry, ckey: str, norm_url: str) -> dict | None:
        """Fetch trang bài viết + trích + lọc. Trả None nếu từ chối (chất lượng/robots)."""
        defaults = self.sset.defaults
        try:
            status, payload = self.fetcher.fetch(entry.url)
        except HttpError:
            raise
        if status in (301, 302, 404, 410, 403):
            return None
        html = payload.decode("utf-8", errors="replace")
        meta = extract_meta(html)
        title = (entry.title or meta["title_html"] or meta["meta_title"]).strip()
        if not title:
            return None
        # Chính sách: nguồn không cho phép full-text → chỉ lưu title + description + URL
        if src.full_text_allowed:
            raw_text = extract_page_text(html)
            text = strip_boilerplate(raw_text)
            text = cut_text(text, defaults.get("max_text_chars", 20000))
            description = (entry.description or meta["meta_description"]).strip()
        else:
            text = ""
            description = cut_text((entry.description or meta["meta_description"]).strip(),
                                   600)

        ok, reason = passes_quality(
            title, text if src.full_text_allowed else description,
            min_title_chars=defaults.get("min_title_chars", 10),
            min_text_chars=defaults.get("min_text_chars", 350) if src.full_text_allowed else 80,
            max_text_chars=defaults.get("max_text_chars", 20000))
        if not ok:
            LOG.debug("[x] Chất lượng từ chối (%s): %s — %s", reason, title[:50], entry.url)
            return None

        return {
            "content_key": ckey,
            "source_id": src.source_id,
            "external_id": entry.external_id,
            "url": entry.url,
            "norm_url": norm_url,
            "title": title[:300],
            "description": (description or "")[:2000],
            "text": text if src.full_text_allowed else "",
            "tags": ",".join(entry.tags or [])[:400],
            "author": (entry.author or meta["author"])[:120],
            "published_at": entry.published_at or meta["published_at"],
            "lang": src.lang,
            "license": src.license,
            "full_text_allowed": int(src.full_text_allowed),
            "content_hash": content_hash(text + title + description),
            "n_chars": len(text) or len(description),
            "quality_status": "ok",
            "status": "active",
            "fetched_at": _now(),
        }


def _fetched_recently(doc_row: dict, hours: float) -> bool:
    import datetime as dt

    try:
        t = dt.datetime.strptime(doc_row["fetched_at"], "%Y-%m-%dT%H:%M:%SZ") \
            .replace(tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - t) < dt.timedelta(hours=float(hours))
    except Exception:  # noqa: BLE001
        return False


def _now() -> str:
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
