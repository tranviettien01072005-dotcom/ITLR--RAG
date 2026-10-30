"""Adapt provider calls to chatbot history, logging and fallback contracts."""

import logging

logger = logging.getLogger("itlr.chatbot")


def try_llm_response(system_prompt, user_message, history=None):
    """Sinh câu trả lời bằng LLM QUA llm_client (DeepSeek → OpenAI → Ollama).

    Hợp đồng giữ nguyên: trả str khi thành công, None khi lỗi/không cấu hình -> caller
    rơi về bộ tổng hợp cục bộ. Lỗi được GHI LOG rõ (không nuốt âm thầm) trước khi trả None.
    """
    from itlr.chatbot import llm_client

    messages = [{"role": "system", "content": system_prompt}]
    messages += _history_msgs(history)
    messages.append({"role": "user", "content": user_message})
    try:
        return llm_client.chat(messages).text
    except llm_client.LLMError as exc:
        logger.warning("try_llm_response: LLM lỗi -> fallback template (%s)", exc)
        return None


def _history_msgs(history):
    """List {role, content}, chỉ user/assistant, 6 lượt gần nhất."""
    out = []
    for msg in (history or [])[-6:]:
        if msg.get("role") in ("user", "assistant"):
            out.append({"role": msg["role"], "content": msg["content"]})
    return out


def try_llm_response_stream(system_prompt, user_message, history=None, *, strict=False):
    """Bản streaming của try_llm_response QUA llm_client (DeepSeek → OpenAI → Ollama).

    Text đã yield là provisional. strict=True truyền LLMError cho caller để final
    loại bỏ câu trả lời dở dang; strict=False log lỗi rồi kết thúc iterator."""
    from itlr.chatbot import llm_client

    messages = [{"role": "system", "content": system_prompt}]
    messages += _history_msgs(history)
    messages.append({"role": "user", "content": user_message})
    try:
        yield from llm_client.stream(messages)
    except llm_client.LLMError as exc:
        if strict:
            raise
        logger.warning("try_llm_response_stream LLMError: %s", exc)
        return
