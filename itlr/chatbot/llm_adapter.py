"""Adapt provider calls to chatbot history, logging and fallback contracts."""

import logging

logger = logging.getLogger("itlr.chatbot")


def try_llm_response(system_prompt, user_message, history=None, *, output_schema=None):
    """Sinh câu trả lời bằng LLM QUA llm_client (DeepSeek → OpenAI → Ollama).

    Hợp đồng giữ nguyên: trả str khi thành công, None khi lỗi/không cấu hình -> caller
    rơi về bộ tổng hợp cục bộ. Lỗi được GHI LOG rõ (không nuốt âm thầm) trước khi trả None.
    """
    from itlr.chatbot import llm_client

    messages = _messages(system_prompt, user_message, history)
    try:
        return llm_client.chat(messages, **({"output_schema": output_schema} if output_schema is not None else {})).text
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


def try_llm_response_stream(system_prompt, user_message, history=None, *, strict=False, output_schema=None):
    """Bản streaming của try_llm_response QUA llm_client (DeepSeek → OpenAI → Ollama).

    Text đã yield là provisional. strict=True truyền LLMError cho caller để final
    loại bỏ câu trả lời dở dang; strict=False log lỗi rồi kết thúc iterator."""
    from itlr.chatbot import llm_client

    messages = _messages(system_prompt, user_message, history)
    try:
        yield from llm_client.stream(messages, **({"output_schema": output_schema} if output_schema is not None else {}))
    except llm_client.LLMError as exc:
        if strict:
            raise
        logger.warning("try_llm_response_stream LLMError: %s", exc)
        return


def _messages(system_prompt, user_message, history):
    return [{"role": "system", "content": system_prompt}, *_history_msgs(history),
            {"role": "user", "content": user_message}]


async def try_llm_response_astream(system_prompt, user_message, history=None, *, output_schema=None):
    from contextlib import aclosing
    from itlr.chatbot import llm_client
    options = {"output_schema": output_schema} if output_schema is not None else {}
    async with aclosing(llm_client.astream(_messages(system_prompt, user_message, history), **options)) as response:
        async for chunk in response:
            yield chunk
