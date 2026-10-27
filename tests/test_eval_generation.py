"""Test metrics cho eval/eval_generation.py — chất lượng GENERATION đo được không cần LLM judge:

  - citation_stats: mọi [item_id:ID] phải THẬT (tồn tại catalog) và (tốt nhất) nằm trong
    context mà mô hình được cấp -> đo tỷ lệ CITE SAI = trực tiếp chống hallucination.
  - ngram_grounded_ratio: xấp xỉ độ "nằm trên bằng chứng" bằng n-gram trùng với nguồn.
  - relevancy_proxy: độ phủ token của câu trả lời với câu hỏi.
Các proxy được ghi rõ LÀ XẤP XỈ trong report; đánh giá LLM-judge cần API key riêng.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    """Nạp module eval từ đường dẫn (eval/ không phải package — giữ đúng hiện trạng)."""
    path = ROOT / "eval" / "eval_generation.py"
    assert path.exists(), "eval/eval_generation.py phải tồn tại"
    spec = importlib.util.spec_from_file_location("eval_generation_probe", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def eg():
    return _load()


def test_extract_citations(eg):
    text = "A [item_id:12] rồi B [item_id:99] và không cite."
    assert eg.extract_citations(text) == [12, 99]
    assert eg.extract_citations("không có citation") == []


def test_citation_stats(eg):
    # valid = tồn tại trong catalog; in-context = id mà mô hình thực sự được cấp
    # cites [12,99,7]; valid={12,7} -> 2/3 tồn tại; context={12} -> 1/3 nằm trong context.
    assert eg.citation_stats([12, 99, 7], context={12}, valid={12, 7}) == {
        "citations": 3, "valid_ratio": 2 / 3, "in_context_ratio": 1 / 3
    }
    assert eg.citation_stats([], context=set(), valid={1})["citations"] == 0


def test_ngram_grounded_ratio(eg):
    src = ["Machine Learning là nhánh của AI tập trung vào dữ liệu và mô hình."]
    assert eg.ngram_grounded_ratio(
        "Machine Learning là nhánh của AI tập trung vào dữ liệu.", src) >= 0.99
    # hoàn toàn xa lạ -> gần 0 (đặt biên trên 0.2 cho câu vô liên quan)
    assert eg.ngram_grounded_ratio(
        "Bánh mì nướng giòn hãy còn nóng răn đăn thú vị bên cà phê đường phố.", src) <= 0.2
    # trộn bằng chứng + sáng tác -> trung gian
    mid = eg.ngram_grounded_ratio(
        "Machine Learning là nhánh của AI. Xe bán tải chạy dốc cao khoang lọc gió.", src)
    assert 0.0 < mid < 0.9


def test_relevancy_proxy(eg):
    assert eg.relevancy_proxy(
        "Docker là gì và dùng để làm gì?", "Docker dùng container để đóng gói ứng dụng.") > 0.1
    assert eg.relevancy_proxy(
        "Chủ nghĩa hiện thực trong văn học Nga thế kỷ 19?",
        "Óc chó bổ dưỡng chứa maicable omega-3 cho tim mạch.") < 0.05


def test_refusal_measurement(eg):
    """Tỷ lệ từ chối đúng: response của câu ngoài chủ đề phải chứa tín hiệu từ chối."""
    assert eg.is_refusal(
        "Câu hỏi này nằm ngoài lĩnh vực công nghệ thông tin, mình không thể tư vấn.")
    assert not eg.is_refusal("Docker giúp đóng gói ứng dụng nhanh và gọn.")
