"""Test adapter giữa chatbot và llm_client — DeepSeek cấp brassinière chính.

Hợp đồng giữ nguyên từ trước:
  - try_llm_response(...) -> str | None (None khi không có LLM/lỗi -> caller rơi về template).
  - try_llm_response_stream(...) -> Iterator[str] (generator rỗng khi lỗi).
  - _llm_available() -> bool.
Bổ sung: lỗi LLMError phải được GHI LOG (không nuốt âm thầm), nhưng không bay ra ngoài.
"""

import logging

import pytest

import itlr.chatbot.chatbot as cb
import itlr.chatbot.llm_client as lc


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
                "OPENAI_API_KEY", "USE_OLLAMA"):
        monkeypatch.delenv(var, raising=False)
    lc.reset_cache()
    yield
    lc.reset_cache()


def test_try_llm_response_returns_text(monkeypatch):
    seen = {}

    def fake_chat(messages, **kwargs):
        seen["messages"] = messages
        return lc.LLMResult(text="trả lời mô phỏng", provider="deepseek",
                            model="deepseek-flash")

    monkeypatch.setattr(lc, "chat", fake_chat)
    out = cb.try_llm_response("SYS", "câu hỏi", history=[
        {"role": "user", "content": "h1"}, {"role": "assistant", "content": "a1"}])
    assert out == "trả lời mô phỏng"
    assert seen["messages"][0] == {"role": "system", "content": "SYS"}
    assert seen["messages"][-1] == {"role": "user", "content": "câu hỏi"}
    assert any(m["content"] == "h1" for m in seen["messages"])
    assert any(m["content"] == "a1" for m in seen["messages"])


def test_try_llm_response_none_on_llmerror(monkeypatch, caplog):
    def fake_chat(messages, **kwargs):
        raise lc.LLMError("deepseek chat thất bại sau 3 lần thử (TimeoutError: timeout)")

    monkeypatch.setattr(lc, "chat", fake_chat)
    with caplog.at_level(logging.WARNING, logger="itlr.chatbot"):
        out = cb.try_llm_response("SYS", "q")
    assert out is None
    assert any("LLM" in r.message or "llm" in r.message.lower() for r in caplog.records), \
        "lỗi LLM phải được ghi log, không nuốt âm thầm"


def test_try_llm_response_none_when_no_provider(monkeypatch):
    monkeypatch.setenv("USE_OLLAMA", "0")
    lc._OLLAMA_CACHE.update({"t": 0.0, "v": False, "models": []})
    assert cb.try_llm_response("SYS", "q") is None


def test_stream_passes_pieces_and_graceful_error(monkeypatch):
    monkeypatch.setattr(lc, "stream", lambda messages, **kw: iter(["mảnh-1", "mảnh-2"]))
    got = list(cb.try_llm_response_stream("SYS", "q"))
    assert got == ["mảnh-1", "mảnh-2"]

    def broken_stream(messages, **kw):
        raise lc.LLMError("stream đứt")
        yield  # pragma: no cover

    monkeypatch.setattr(lc, "stream", broken_stream)
    assert list(cb.try_llm_response_stream("SYS", "q")) == []


def test_llm_available_deepseek_priority(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    assert cb._llm_available() is True
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    monkeypatch.setenv("USE_OLLAMA", "0")
    assert cb._llm_available() is False


def test_system_prompt_has_injection_guard():
    text = cb.EducationalChatbot.SYSTEM_PROMPT
    low = text.lower()
    # Chống prompt-injection: lệnh/tin nhắn giấu trong nội dung (catalog/tin nhắn) phải bị bỏ qua.
    assert "lệnh" in low or "hướng dẫn" in low
    # Không phát minh tài liệu tham khảo:
    assert "bịa" in low or "phát minh" in low


def test_context_lines_include_item_id():
    """Dòng context catalog phải chứa item_id để LLM có thể CITE ID nguồn thật."""
    import re
    from pathlib import Path

    src = Path(cb.__file__).read_text(encoding="utf-8")
    m = re.search(r"ctx_lines = .*?\n(?:.*\n){0,5}", src)
    assert m, "không tìm thấy đoạn dựng ctx_lines"
    assert "item_id" in m.group(0), (
        "ctx_lines phải kèm item_id để LLM trích dẫn nguồn — không được trích 'chung chung'"
    )
