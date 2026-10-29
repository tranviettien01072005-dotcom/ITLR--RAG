"""Trích nội dung từ trang web bằng BeautifulSoup — nhanh, không cần JS rendering.

Nguyên tắc: lấy khối <article>/<main>; loại bỏ script/style/nav/footer/aside/figure
và các khối rác (share/comment/subscribe/ads... dựa trên class/id). Nội dung CNTT
thường có code — <pre>/<code> giữ nguyên trong luồng text (BeautifulSoup giữ text).
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

LOG = logging.getLogger("itlr.collect")

REMOVE_TAGS = ("script", "style", "noscript", "nav", "footer", "aside", "form",
               "button", "iframe", "video", "audio", "svg", "picture", "source",
               "header", "template", "figcaption")
BLOCK_CLASSES_BAD = (
    "share", "social", "comment", "subscribe", "newsletter", "related", "breadcrumb",
    "sidebar", "footer", "cookie", "banner", "ads", "sponsor", "menu", "popup",
    "pagination", "recommend", "author-card", "cta", "signup", "promo")


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _is_bad(tag) -> bool:
    cls = " ".join(tag.get("class") or []).lower()
    id_ = (tag.get("id") or "").lower()
    return any(b in cls or b in id_ for b in BLOCK_CLASSES_BAD)


def _clean_html_soup(html: str) -> BeautifulSoup:
    soup = _soup(html)
    for tag in list(soup(REMOVE_TAGS)):
        tag.decompose()
    # Chụp danh sách TRƯỚC khi decompose: decompose cha làm tag con stale
    # (attrs=None) — phải bỏ qua, không crash (crash bị nuốt → chuỗi rỗng âm thầm).
    for tag in list(soup.find_all(True)):
        tag.name = tag.name if isinstance(tag.name, str) else "unknown"
        if tag.name in ("html", "body"):
            continue
        if tag.attrs is None:
            continue  # tag đã bị decompose (stale)
        if _is_bad(tag):
            tag.decompose()
    return soup


def _content_count(tag) -> int:
    """Số phần tử mang nội dung thật (p/li/pre/h*/blockquote/code) trong subtree."""
    return sum(1 for t in tag.descendants
               if getattr(t, "name", None) in
               ("p", "li", "pre", "code", "h1", "h2", "h3", "h4", "h5", "h6",
                "blockquote", "td", "dt", "dd"))


def _pick_main(soup):
    """Chọn container CHÍNH bằng mật độ nội dung (deepest arg-max, tie → con sâu hơn).

    Vì sao: chặt 'rác' theo class ở cấp cao dễ chặt nhầm cả bài viết (vd fCC bọc
    nội dung trong div 'post-and-sidebar'). Đo nội dung nên bền và ít phụ thuộc class.
    """
    roots = list(soup.find_all(["article", "main"])) \
        or soup.find_all(attrs={"role": "main"}) or [soup.body or soup]
    best, best_key = None, (-1, -1)
    for root in roots:
        for t in [root, *root.find_all(["div", "section", "article", "main"])]:
            try:
                n = _content_count(t)
            except Exception:  # noqa: BLE001
                continue  # tag stale sau decompose
            if n > best_key[0] or (n == best_key[0] and tuple(
                    d.name for d in t.parents).count("div") > best_key[1]):
                key = (n, tuple(d.name for d in t.parents).count("div"))
                if n > 0:
                    best, best_key = t, key
    return best


def extract_page_text(html: str) -> str:
    """Văn bản chính của bài viết (join các dòng đã dọn). Trả "" nếu không trích được."""
    if not html or not isinstance(html, str):
        return ""
    try:
        soup = _soup(html)
        for tag in list(soup(REMOVE_TAGS)):
            tag.decompose()
        main = _pick_main(soup)
        if main is None:
            LOG.debug("extract_page_text: không tìm thấy container nội dung")
            return ""
        # Rác TRONG vùng nội dung: chỉ chặt nếu không cầm p/li/pre/h bên trong
        for t in list(main.find_all(True)):
            if t.attrs is None:  # stale
                continue
            if _is_bad(t) and _content_count(t) == 0:
                t.decompose()
        text = main.get_text(separator="\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001 — HTML hỏng không được làm chết lượt crawl
        LOG.warning("extract_page_text lỗi (%s) — trả rỗng", exc)
        return ""


def _first_meta(soup: BeautifulSoup, attr_value: str) -> str:
    for attr in ("name", "property"):
        tag = soup.find("meta", attrs={attr: attr_value})
        if tag is not None and tag.get("content"):
            return str(tag.get("content")).strip()
    return ""


def _jsonld_published(soup: BeautifulSoup) -> str:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:  # noqa: BLE001
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            date = node.get("datePublished") or node.get("dateCreated") or ""
            if isinstance(date, str) and date:
                return date
            graph = node.get("@graph")
            if isinstance(graph, list):
                for sub in graph:
                    if isinstance(sub, dict):
                        d = sub.get("datePublished") or ""
                        if isinstance(d, str) and d:
                            return d
    return ""


def extract_meta(html: str) -> dict:
    """Metadata móc: title (og:title + h1), description, published_at, author."""
    if not html or not isinstance(html, str):
        return {}
    soup = _soup(html)
    title = (soup.title.get_text() if soup.title is not None else "") or ""
    h1 = soup.find("h1")
    if h1 is not None:
        title = f"{title.strip()} {h1.get_text(strip=True)}".strip()
    return {
        "title_html": title.strip(),
        "meta_title": _first_meta(soup, "og:title"),
        "meta_description": (_first_meta(soup, "description")
                             or _first_meta(soup, "og:description")),
        "published_at": (_first_meta(soup, "article:published_time")
                         or _first_meta(soup, "article:modified")
                         or _jsonld_published(soup)),
        "author": _first_meta(soup, "author") or _first_meta(soup, "og:site_name"),
    }


def extract_listing_links(html: str, base_url: str, *,
                          same_host_only=True, min_path_len=4,
                          max_links=200) -> list[str]:
    """Danh sách URL ứng viên bài viết từ trang liệt kê (đã đổi tương đối → tuyệt đối).

    Lọc đơn giản: bỏ anchor/mail/tel/data, chỉ cùng host nếu same_host_only,
    path tối thiểu min_path_len ký tự, chống trùng (không phân biệt trailing slash).
    Chuẩn hóa sâu (utm/fragment...) thuộc về url_util.normalize_url — hỗ trợ sau.
    """
    if not html or not isinstance(html, str):
        return []
    try:
        soup = _soup(html)
    except Exception:  # noqa: BLE001
        return []
    base_host = urlsplit(base_url).netloc
    seen: set[str] = set()
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue
        absolute = urljoin(base_url, href)
        sp = urlsplit(absolute)
        if not sp.netloc:
            continue
        if same_host_only and sp.netloc != base_host:
            continue
        if len((sp.path or "").strip("/")) < min_path_len:
            continue
        clean = absolute.split("#")[0]
        key = clean.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
        if len(out) >= max_links:
            break
    return out


BOILERPLATE_EXACT = {
    "skip to content", "skip to main content", "menu", "search",
    "share this:", "like this: like loading...", "loading", "related posts",
    "advertisement", "toggle website search", "save my name, email, and website.",
}


def strip_boilerplate(text: str) -> str:
    """Cắt các dòng boilerplate phổ biến — dùng trước khi lọc chất lượng."""
    if not text:
        return ""
    lines = []
    for ln in text.splitlines():
        l = ln.strip()
        if len(l) < 2:
            continue
        if l.lower() in BOILERPLATE_EXACT:
            continue
        lines.append(ln.rstrip())
    return "\n".join(lines)
