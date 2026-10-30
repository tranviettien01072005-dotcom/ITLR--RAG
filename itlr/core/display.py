"""Catalog display formatting; independent of retrieval scoring and models."""

import re


def _collapse_repeats(text):
    """Gộp CỤM TỪ lặp liên tiếp do dịch máy lỗi (từ đơn lẫn cụm 2-4 từ):
        "kỹ thuật thuật thuật toán"        -> "kỹ thuật toán"
        "Kỹ thuật Kỹ thuật Kỹ thuật ..."   -> "Kỹ thuật"
    Làm theo token (an toàn, không backtracking); so khớp không phân biệt hoa thường."""
    toks = str(text).split()
    if len(toks) < 2:
        return str(text)
    changed = True
    while changed:
        changed = False
        for k in range(4, 0, -1):
            i, res, n = 0, [], len(toks)
            while i < n:
                seg = [t.lower() for t in toks[i:i + k]]
                if i + 2 * k <= n and seg == [t.lower() for t in toks[i + k:i + 2 * k]]:
                    res.extend(toks[i:i + k])
                    j = i + k
                    while j + k <= len(toks) and [t.lower() for t in toks[j:j + k]] == seg:
                        j += k
                    i = j
                    changed = True
                else:
                    res.append(toks[i])
                    i += 1
            toks = res
    return " ".join(toks)


_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,;:!?])")
_SPACE_BEFORE_PERIOD_RE = re.compile(r"\s+\.(?=\s|$)")
_SPACE_AFTER_COMMA_RE = re.compile(r"([,;:])(?=[A-Za-zÀ-ỹ])")
_SENTENCE_GLUE_RE = re.compile(r"(?<=[a-zà-ỹ]{2})([.!?])(?=[A-ZÀ-Ỹ][a-zà-ỹ])")


def clean_display_text(text):
    """Làm sạch mô tả/tiêu đề catalog cho HIỂN THỊ (sửa lỗi DỊCH MÁY an toàn, không viết lại câu):
    gộp từ lặp liên tiếp, sửa khoảng trắng quanh dấu câu, tách câu bị dính, viết hoa chữ đầu.
    KHÔNG đụng truy hồi/chấm điểm (chỉ áp ở tầng hiển thị)."""
    s = _collapse_repeats(str(text))
    s = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", s)
    s = _SPACE_BEFORE_PERIOD_RE.sub(".", s)
    s = _SPACE_AFTER_COMMA_RE.sub(r"\1 ", s)
    s = _SENTENCE_GLUE_RE.sub(r"\1 ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[0].upper() + s[1:] if s else s


def clean_link(link):
    """Chỉ giữ link http(s) hợp lệ; placeholder ('Đang cập nhật') / rỗng -> '' để KHÔNG render
    link hỏng (`[Mở tài nguyên](Đang cập nhật)`)."""
    s = str(link).strip()
    return s if s.lower().startswith(("http://", "https://")) else ""
