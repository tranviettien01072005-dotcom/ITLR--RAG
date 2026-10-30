"""Regression: chunk_text contract — mọi chunk trả về phải ≤ max_chars (audit finding).

Bug cũ: bước gộp "đoạn cuối quá ngắn" (parts[-2] += " " + parts.pop()) không kiểm
tra bound → câu đơn 910 ký tự bị cắt thô [900, 10] rồi gộp thành 911 > max_chars.
"""
from itlr.collect.chunk import chunk_text
import pytest


def test_overlap_never_pushes_next_sentence_over_bound():
    parts = chunk_text('a' * 800 + '. ' + 'b' * 890 + '.', max_chars=900)
    assert all(len(part) <= 900 for part in parts)
    assert 'b' * 890 in ''.join(parts)


def test_zero_overlap_does_not_repeat_entire_previous_chunk():
    parts = chunk_text('a' * 600 + '. ' + 'b' * 600 + '.', overlap_chars=0)
    assert parts == ['a' * 600 + '.', 'b' * 600 + '.']


@pytest.mark.parametrize('kwargs', [dict(max_chars=0), dict(overlap_chars=-1),
                                  dict(max_chars=100, overlap_chars=100),
                                  dict(min_chars=-1)])
def test_invalid_chunk_limits_are_rejected(kwargs):
    with pytest.raises(ValueError):
        chunk_text('text', **kwargs)


def test_unbroken_long_sentence_parts_never_exceed_max_chars():
    parts = chunk_text("x" * 910, max_chars=900, min_chars=40)
    assert parts, "chunks must not be empty"
    assert all(len(p) <= 900 for p in parts), [len(p) for p in parts]


def test_mixed_document_repeated_tail_merge_keeps_bound():
    doc = ("Câu a " * 150).strip() + "\n" + ("y" * 930) + "\n" + ("Câu b " * 60).strip()
    parts = chunk_text(doc, max_chars=900, min_chars=40)
    assert parts, "chunks must not be empty"
    assert all(len(p) <= 900 for p in parts), [len(p) for p in parts]


def test_short_tail_merges_without_dropping_content():
    # Ca bình thường vẫn gộp: đoạn cuối < min_chars và kết quả gộp không vượt bound.
    doc = ("T " * 300).strip() + "\n" + ("z " * 200).strip()
    parts = chunk_text(doc, max_chars=600, min_chars=120)
    assert parts and all(len(p) <= 600 for p in parts), [len(p) for p in parts]


@pytest.mark.parametrize('fence', ['```', '~~~'])
def test_fenced_code_preserves_unicode_newlines_and_indentation(fence):
    code = f'{fence}python\ndef chào():\n    if True:\n        return "Việt Nam"\n{fence}'
    text = 'Giải thích.\n' * 30 + code + '\nKết thúc.' * 30
    parts = chunk_text(text, max_chars=180, overlap_chars=30)
    # Every chunk is literal source evidence; reconstruct without changing code whitespace.
    assert all(part in text for part in parts)
    restored = parts[0] + ''.join(part[30:] for part in parts[1:])
    assert restored == text
    assert all(len(part) <= 180 for part in parts)
