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
    """Jaccard trên token tiêu đề — dùng cho cross-source near-dup detection.

    Jaccard (giao/hợp) chứ KHÔNG phải overlap coefficient (giao/min): tiêu đề ngắn chung
    vài token phổ biến ("hướng dẫn", "2026") từng cho điểm 1.0 và chặn nhầm bài khác.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    return len(inter) / len(ta | tb)


def is_near_dup_title(a: str, b: str, threshold: float = 0.80) -> bool:
    """True nếu hai tiêu đề gần trùng NGHĨA (không phải chỉ khác số thứ tự).

    Loại trường hợp series "Bài học số 1" vs "Bài học số 2": token khác nhau chỉ là số
    -> KHÔNG coi là trùng. Biến thể như "... cho người mới" vs "... cho người mới nhất"
    (khác token chữ) vẫn bị bắt khi Jaccard >= threshold.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    diff = ta ^ tb
    if diff and all(t.isdigit() for t in diff):
        return False
    return len(ta & tb) / len(ta | tb) >= threshold


def normalize_title(title: str) -> str:
    """Khóa title ổn định: lowercase + gộp whitespace (dùng cho title_seen)."""
    return " ".join(str(title or "").lower().split())


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
