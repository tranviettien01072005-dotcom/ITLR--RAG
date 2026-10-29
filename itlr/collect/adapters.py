"""Adapter đọc mục tiêu từ 3 loại nguồn: api (JSON), rss (feedparser), web (HTML).

Mỗi adapter trả Candidate(list[CandidateItem]) — MỚI là "hồ sơ ánh xạ", chưa fetch
trang bài viết; store quyết định fetch or skip (recheck_after_hours + có sẵn).
Vì vậy trong phi_input mỗi adapter chỉ cột truy cập được trong lần đầu.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

LOG = logging.getLogger("itlr.collect")


@dataclass
class CandidateEntry:
    source_id: str
    external_id: str
    url: str
    title: str = ""
    description: str = ""
    author: str = ""
    published_at: str = ""
    tags: list[str] = field(default_factory=list)
    list_rank: int = 0


def iso8601_or_empty(value) -> str:
    """Chuỗi ngày giờ → ISO 8601 (YYYY-MM-DD…); không hợp lệ → ""."""
    if not value:
        return ""
    s = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        # chuẩn hóa + suffix nếu là đầy đủ Z/copy giữ đơn giản
        return s.replace(" ", "T")
    try:
        fs = float(s)
        if fs > 1e12:
            fs /= 1000.0
        return _dt.datetime.fromtimestamp(fs, tz=_dt.timezone.utc) \
            .strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OSError):
        return ""


def _get_path(obj, path: str):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)] if int(part) < len(cur) else None
        else:
            return None
        if cur is None:
            return None
    return cur


def api_candidates(source, payload: bytes | str) -> list[CandidateEntry]:
    """API list JSON → CandidateEntry danh sách."""
    data = json.loads(payload.decode("utf-8", errors="replace"))
    if isinstance(data, dict):
        # cho phép phản hồi dạng {"articles": [...], ...}
        for key in ("articles", "items", "data", "results", "posts"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError(f"API {source.source_id}: payload JSON không phải list "
                         f"các bài (loa Unblock: {type(data).__name__})")
    f = source.fields
    entries = []
    for rank, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        url = _get_path(item, f["url"])
        title = _get_path(item, f["title"])
        if not url or not title:
            LOG.debug("api %s: bỏ entry thiếu url/title", source.source_id)
            continue
        tags_raw = _get_path(item, f.get("tags") or "") or ""
        if isinstance(tags_raw, (list, tuple)):
            tags = [str(t) for t in tags_raw][:8]
        else:
            tags = [t for t in re.split(r"[,;|]", str(tags_raw)) if t.strip()][:8]
        entries.append(CandidateEntry(
            source_id=source.source_id,
            external_id=str(_get_path(item, f.get("id") or "") or url)[:200],
            url=str(url),
            title=str(title)[:300],
            description=str(_get_path(item, f.get("description") or "") or "")[:1000],
            author=str(_get_path(item, f.get("author") or "") or "")[:120],
            published_at=iso8601_or_empty(_get_path(item, f.get("published_at") or "")),
            tags=tags, list_rank=rank))
    return entries


def rss_candidates(source, payload: bytes | str) -> list[CandidateEntry]:
    """RSS/Atom → danh sách mục (feedparser đọc RSS chuẩn hơn tay)."""
    try:
        import feedparser
    except ImportError as exc:  # pragma: no cover
        raise ImportError("Cần feedparser (pip install feedparser)") from exc
    feed = feedparser.parse(payload)
    if feed.get("bozo") and not feed.get("entries"):
        raise ValueError(f"RSS {source.source_id}: feed không đọc được "
                         f"({feed.get('bozo_exception')})")
    entries = []
    for rank, e in enumerate(feed.entries or []):
        link = e.get("link") or ""
        title = (e.get("title") or "").strip()
        if not link or not title:
            continue
        summary = e.get("summary") or ""
        desc = re.sub(r"<[^>]+>", " ", summary)
        tags = [t.term for t in e.get("tags", []) if getattr(t, "term", None)][:8]
        published = e.get("published") or e.get("updated") or ""
        published_at = published if re.match(r"^\d{4}", str(published)) else ""
        if not published_at and e.get("published_parsed"):
            published_at = _dt.datetime(*e["published_parsed"][:7],
                                        tzinfo=_dt.timezone.utc) \
                .strftime("%Y-%m-%dT%H:%M:%SZ")
        entries.append(CandidateEntry(
            source_id=source.source_id,
            external_id=(e.get("guid") or link)[:200],
            url=link, title=title[:300], description=desc[:1000],
            author=(e.get("author") or "")[:120],
            published_at=iso8601_or_empty(published_at) if published_at else "",
            tags=tags, list_rank=rank))
    return entries


def web_candidates(source, listing_html: str, listing_url: str) -> list[CandidateEntry]:
    """Trang liệt kê HTML → URL ứng viên (metadata thô trống, đầy đủ khi fetch trang)."""
    from itlr.collect.extract import extract_listing_links

    links = extract_listing_links(listing_html, listing_url,
                                  same_host_only=True, min_path_len=3)
    out = []
    for rank, url in enumerate(links):
        if source.link_prefix and not url.startswith(source.link_prefix):
            continue
        if source.link_pattern:
            import re as _re

            if not _re.search(source.link_pattern, urlsplit(url).path):
                LOG.debug("web %s: bỏ URL không khớp link_pattern: %s",
                          source.source_id, url)
                continue
        out.append(CandidateEntry(source_id=source.source_id, external_id=url[:200],
                                  url=url, list_rank=rank))
    return out
