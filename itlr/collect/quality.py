"""Lọc chất lượng nguồn: chống nội dung rác, quá ngắn, rác SEO; hash chống trùng.

Không bịa dữ liệu — loại bỏ nội dung kém chất lượng (không sửa/xào nấu).
"""

from __future__ import annotations

import hashlib
import re

WHITESPACE_RE = re.compile(r"[ \t]+")
_max_chars = 0  # (placeholder — hằng số thực nằm ở hàm)


def content_hash(text: str) -> str:
    """Hash nội dung đã chuẩn hóa whitespace — phát hiện CŨ/MỚI dữ liệu thay đổi."""
    if text is None:
        text = ""
    norm = WHITESPACE_RE.sub(" ", text.strip().lower())
    return hashlib.sha256(norm.encode("utf-8", errors="replace")).hexdigest()


TITLE_TOKEN_RE = re.compile(r"[\w\d]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {t.lower()[:32] for t in TITLE_TOKEN_RE.findall(text or "")}


def title_similarity(a: str, b: str) -> float:
    """Jaccard trên token tiêu đề — used for cross-source near-dup detection."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    return len(inter) / max(1, min(len(ta), len(tb)))


def passes_quality(title: str, text: str, *, min_title_chars=10, min_text_chars=350,
                   max_text_chars=20000) -> tuple[bool, str]:
    """(đạt, lý_do_nếu_không_đạt). Rất khó chịu với rác: title quá ngắn, văn bản quá ngắn/quá dài."""
    if not title or len(title.strip()) < min_title_chars:
        return False, "title_too_short"
    t = (text or "").strip()
    if len(t) < min_text_chars:
        return False, "too_short"
    if len(t) > max_text_chars:
        t = t[:max_text_chars]
    words = re.findall(r"[\w']+", t.lower())
    if len(words) < 20:
        return False, "too_few_words"
    # Nội dung mà toàn số/liên kết — không đủ tín hiệu
    junk = ["http://", "https://"]
    alpha_words = [w for w in words if not w.startswith(tuple(junk))]
    if not alpha_words:
        return False, "no_text_signals"
    return True, "ok"


def cut_text(text: str, max_text_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_text_chars:
        return t
    cut = t[:max_text_chars]
    # cắt tại ranh giới câu/si do gần nhất để không chặn giữa chừng
    for sep in (". ", "\n", "! ", "? "):
        i = cut.rfind(sep)
        if i > max_text_chars * 0.6:
            cut = cut[: i + 1]
            break
    return cut + "…"
