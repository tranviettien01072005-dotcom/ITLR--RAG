"""Tiện ích URL cho crawler: chuẩn hóa bền vững + khóa nội dung chống trùng.

Nguyên tắc: cùng "một bài viết" phải cho ra MỘT khóa bất kể tham số tracking,
http/https, trailing slash, fragment... để chống trùng lặp thật sự.
"""

from __future__ import annotations

import hashlib
import urllib.parse

# Tham số tracking đại loại (mọi tiền tố utm_*) — bỏ khi chuẩn hóa.
STRIP_PARAMS_PREFIXES = ("utm", "gclid", "fbclid", "mc_cid", "mc_eid",
                         "ref_src", "ref_url", "igshid", "msclkid",
                         "spm", "scm", "share_token")
# Tham số giữ nguyên nếu không khớp tiền tố loại bỏ.
_ALLOWED_LISTING_PARAMS = {"page", "per_page", "tag", "tags", "q", "top"}


def normalize_url(url) -> str | None:
    """Chuẩn hóa URL về dạng đại diện ổn định; trả None nếu không phải URL hợp lệ.

    - http → https (cùng host)
    - host lowercase; path giữ nguyên chữ (một số site phân biệt hoa/thường)
    - bỏ fragment, bỏ tham số tracking, sắp xếp tham số còn lại, bỏ ?/trailing slash dư
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url:
        return None
    raw = url.replace("\\", "/")
    try:
        parts = urllib.parse.urlsplit(raw)
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    scheme = "https" if parts.scheme == "http" else parts.scheme
    host = parts.netloc.lower()
    # Bỏ cổng mặc định
    if host.endswith(":443"):
        host = host[:-4]
    path = parts.path or "/"
    # Decode phần trăm-encoding an toàn (không đổi ký tự phân cách)
    try:
        path = urllib.parse.unquote(path)
    except ValueError:
        pass
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=False)
    kept = [(k, v) for (k, v) in pairs
            if not k.lower().startswith(STRIP_PARAMS_PREFIXES)]
    ordered = "&".join(
        urllib.parse.quote(str(k), safe="") + "=" + urllib.parse.quote(str(v), safe="")
        for k, v in sorted(kept)
    )
    q = f"?{ordered}" if ordered else ""
    norm_path = path.rstrip("/") or "/"
    out = f"{scheme}://{host}"
    if norm_path == "/" and not q:
        return out
    return out + ("" if norm_path == "/" else norm_path) + q


def content_key(url) -> str:
    """Khóa nội dung bền vững theo thời gian (content key) từ URL đã chuẩn hóa.

    Dùng làm khóa mapping item_id (item_map) — cùng bài viết cỏn cho chung khóa
    bất kể margin tracking. Tiền tố "u:" là dữ liệu đã thu thập theo URL.
    """
    norm = normalize_url(url)
    if not norm:
        return ""
    digest = hashlib.sha1(norm.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"u:{digest}"


def same_site(url_a, url_b) -> bool:
    """True nếu 2 URL cùng trang chủ (host sau khi bỏ www.)."""
    def host(u):
        n = normalize_url(u)
        if not n:
            return None
        h = urllib.parse.urlsplit(n).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    ha, hb = host(url_a), host(url_b)
    return bool(ha) and ha == hb
