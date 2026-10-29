"""Khối văn bản dài → các đoạn nhỏ (chunking) cho embeddings — tránh cắt nội dung.

Vì sao: mô hình embedding có giới hạn ngữ cảnh (E5 ≈ 512 token). Bài dài bị cắt đuôi
khi encode trực tiếp → tín hiệu mờ. Ta chia đoạn có overlap, encode từng đoạn rồi
gộp (mean + chuẩn hóa L2) — giữ 1:1 với item trong index hiện có (không đổi hợp đồng
API), tài liệu dài không mất đuôi.
Đường viền: đơn giản — theo dòng/câu; không phân tích cấu trúc sâu.
"""

from __future__ import annotations

import re

SENT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def chunk_text(text: str, *, max_chars: int = 900, overlap_chars: int = 120,
               min_chars: int = 40) -> list[str]:
    """Trả <list> đoạn ≤ max_chars; rỗng → []. Đoạn ngắn cuối (<min_chars) khớp vào đoạn trước.

    Thuật toán (deterministic, dễ test):
    1) cắt theo câu/không vượt max_chars trừ khi câu riêng lẻ quá dài (_cut_long_gap);
    2) ghép câu liên tiếp; mở lại khi vượt max_chars;
    3) nếu đoạn cuối quá ngắn → gộp với đoạn trước (chứa overlap tự nhiên).
    """
    if not text or not text.strip():
        return []
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    parts: list[str] = []
    cur: list[str] = []
    cur_len = 0

    sentences = _split_sentences(text)
    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        if len(s) > max_chars:
            # câu đơn vượt ngưỡng — cắt thô theo ký tự (hiếm gặp; URL/code dài)
            if cur:
                parts.append(" ".join(cur))
                cur, cur_len = [], 0
            for piece in _cut_by_chars(s, max_chars):
                parts.append(piece)
            continue
        if cur_len + len(s) + 1 > max_chars:
            parts.append(" ".join(cur))
            # overlap: giữ mớ cuối dài tối đa overlap_chars
            tail = " ".join(cur)
            tail = tail[-overlap_chars:] if len(tail) > overlap_chars else tail
            cur, cur_len = [tail], len(tail)
        cur.append(s)
        cur_len += len(s) + 1
    if cur:
        parts.append(" ".join(cur))

    # gộp đoạn cuối quá ngắn
    if len(parts) >= 2 and len(parts[-1]) < min_chars:
        parts[-2] += " " + parts.pop()

    return [p.strip() for p in parts if p.strip()]


def _split_sentences(text: str) -> list[str]:
    return [s for s in SENT_RE.split(text) if s.strip()]


def _cut_by_chars(s: str, max_chars: int) -> list[str]:
    return [s[i:i + max_chars] for i in range(0, len(s), max_chars)]
