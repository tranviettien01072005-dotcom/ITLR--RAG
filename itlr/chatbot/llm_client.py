"""LLM client dùng chung — DeepSeek (OpenAI-compatible) là LLM CHÍNH của hệ thống.

Trách nhiệm:
  - Thứ tự ưu tiên provider: DeepSeek → OpenAI → Ollama.
  - Retry với exponential backoff, timeout; lỗi được BÁO RÕ (LLMError) thay vì nuốt âm thầm.
  - Tracking token usage + chi phí ước lượng (theo bảng giá); KHÔNG log API key (luôn mask).
  - Trim messages theo ngân sách context (giữ system, ưu tiên lượt MỚI NHẤT).

DeepSeek CHỈ đảm nhiệm phần SINH CÂU TRẢ LỜI (generation). Retrieval (E5/BGE + BM25/
TF-IDF + RRF + ANN + Cross-Encoder + MMR) giữ nguyên như cũ.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
import urllib.parse
import urllib.request
from contextlib import closing
from dataclasses import dataclass
from threading import Lock
from typing import Iterator, Optional

logger = logging.getLogger("itlr.llm")

DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
}

DEFAULT_MODELS = {
    "deepseek": "deepseek-flash",   # tên model yêu cầu; override qua DEEPSEEK_MODEL
    "openai": "gpt-4o-mini",
    "ollama": "qwen2.5:3b",
}

# Bảng giá USD / 1M tokens (ước tính dùng để báo cáo chi phí; có thể cập nhật khi cần).
PRICE_PER_1M = {
    "deepseek": {"input": 0.27, "output": 1.10},
    "openai": {"input": 0.15, "output": 0.60},
    "ollama": {"input": 0.0, "output": 0.0},
}

DEFAULT_RETRIES = 3          # tổng số lần thử (1 lần + 2 retry)
DEFAULT_BACKOFF_S = 0.8      # giây, nhân đôi mỗi lần retry
STREAM_RETRY_MAX_BACKOFF = 6.4

DEFAULT_TEMPERATURE = 0.3    # thấp: trả lời grounded, ít "sáng tác"
DEFAULT_MAX_TOKENS = 2000

_OLLAMA_CACHE: dict = {"t": 0.0, "v": False, "models": []}

_USAGE: dict = {"total_calls": 0, "total_prompt_tokens": 0,
                "total_completion_tokens": 0, "total_cost_usd": 0.0, "by_provider": {}}
_USAGE_LOCK = Lock()


class LLMError(RuntimeError):
    """Lỗi gọi LLM khi đã cố hết retry (thông báo luôn CHE API key)."""


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    retries: int = 0


def mask_key(value: str) -> str:
    """Che API key trong mọi chuỗi để log/hiển thị: sk-abcdef1234 -> sk-***1234."""
    v = str(value or "")
    if len(v) <= 8:
        return "sk-***"
    return f"{v[:3]}***{v[-4:]}"


def _safe_err_text(exc: BaseException) -> str:
    """Chuỗi lỗi an toàn khi log: che mọi key hiện cấu hình nếu vô tình xuất hiện."""
    text = f"{type(exc).__name__}: {exc}"
    for key in (api_key("deepseek"), api_key("openai")):
        if key:
            text = text.replace(key, mask_key(key))
    return text


def api_key(provider: str) -> Optional[str]:
    """Key cho provider (chỉ deepseek/openai dùng key; ollama không có)."""
    if provider == "deepseek":
        return os.environ.get("DEEPSEEK_API_KEY") or None
    if provider == "openai":
        return os.environ.get("OPENAI_API_KEY") or None
    return None


def default_model(provider: str) -> str:
    env_map = {"deepseek": "DEEPSEEK_MODEL", "openai": "OPENAI_MODEL",
               "ollama": "OLLAMA_MODEL"}
    return os.environ.get(env_map[provider]) or DEFAULT_MODELS[provider]


def base_url(provider: str) -> str:
    env_map = {"deepseek": "DEEPSEEK_BASE_URL", "openai": "OPENAI_BASE_URL",
               "ollama": "OLLAMA_BASE_URL"}
    value = os.environ.get(env_map[provider]) or DEFAULT_BASE_URLS.get(
        provider, "http://localhost:11434")
    if urllib.parse.urlsplit(value).scheme not in ("http", "https"):
        raise LLMError(f"{env_map[provider]} must use http:// or https://")
    return value


def timeout_for(provider: str, stream: bool) -> float:
    name = 'DEEPSEEK_STREAM_TIMEOUT_S' if stream else 'DEEPSEEK_TIMEOUT_S'
    try:
        value = float(os.environ.get(name, '240' if stream else '90'))
    except ValueError as exc:
        raise LLMError(f'{name} must be numeric') from exc
    if not math.isfinite(value) or value <= 0:
        raise LLMError(f'{name} must be finite and positive')
    return value


# ------------------------------- Ollama layer ------------------------------- #


def ollama_reachable() -> bool:
    """Probe /api/tags với TTL 30s — tránh treo khi cấu hình trỏ tới Ollama không chạy."""
    now = time.time()
    if now - _OLLAMA_CACHE.get("t", 0) > 30:
        base = base_url("ollama").rstrip("/")
        try:
            with urllib.request.urlopen(base + "/api/tags", timeout=3) as r:
                data = json.loads(r.read())
            _OLLAMA_CACHE["models"] = [m.get("name", "") for m in data.get("models", [])]
            _OLLAMA_CACHE["v"] = True
        except Exception:
            _OLLAMA_CACHE["models"] = []
            _OLLAMA_CACHE["v"] = False
        _OLLAMA_CACHE["t"] = now
    return _OLLAMA_CACHE["v"]


def ollama_model() -> str:
    """Chọn model Ollama: OLLAMA_MODEL nếu đặt và có sẵn; nếu không tự chọn đã pull."""
    env_model = os.environ.get("OLLAMA_MODEL")
    ollama_reachable()
    models = _OLLAMA_CACHE.get("models", [])
    if env_model and (not models or env_model in models):
        return env_model
    if not models:
        return env_model or DEFAULT_MODELS["ollama"]
    for pref in ("qwen2.5:3b", "qwen2.5:1.5b"):
        if pref in models:
            return pref
    return next((m for m in models if "qwen2.5" in m), models[0])


def ollama_chat(messages, *, num_predict: int = 384, temperature: float = 0.5) -> str:
    """Gọi Ollama non-stream. Raise (caller dịch thành lỗi nghiệp vụ nếu muốn)."""
    payload = json.dumps({
        "model": ollama_model(),
        "messages": messages,
        "stream": False,
        "keep_alive": "2h",
        "options": {"num_predict": int(num_predict), "temperature": float(temperature)},
    }).encode()
    req = urllib.request.Request(
        base_url("ollama").rstrip("/") + "/api/chat",
        data=payload, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_for("ollama", stream=False)) as resp:
        data = json.loads(resp.read())
    return (data.get("message") or {}).get("content", "").strip()


def _stream_ollama(messages, *, num_predict: int = 384, temperature: float = 0.5) -> Iterator[str]:
    """Ollama stream=true — yield từng mảnh văn bản ngay khi sinh."""
    payload = json.dumps({
        "model": ollama_model(),
        "messages": messages,
        "stream": True,
        "keep_alive": "2h",
        "options": {"num_predict": int(num_predict), "temperature": float(temperature)},
    }).encode()
    req = urllib.request.Request(
        base_url("ollama").rstrip("/") + "/api/chat",
        data=payload, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_for("ollama", stream=True)) as resp:
        for raw in resp:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            piece = (obj.get("message") or {}).get("content", "")
            if piece:
                yield piece
            if obj.get("done"):
                break


# --------------------------- Provider orchestration --------------------------- #


def provider_status() -> str:
    """Provider đang được cấu hình: 'deepseek' | 'openai' | 'ollama' | 'none'."""
    if api_key("deepseek"):
        return "deepseek"
    if api_key("openai"):
        return "openai"
    if str(os.environ.get("USE_OLLAMA", "")).lower() in ("0", "false", "no"):
        return "none"
    return "ollama" if ollama_reachable() else "none"


def llm_available() -> bool:
    """Có LLM dùng được không (DeepSeek/OpenAI key cấu hình, hay Ollama đang chạy)."""
    return provider_status() != "none"


def reset_cache() -> None:
    """Xóa cache probe Ollama + usage (dùng cho test / admin reload)."""
    global _OLLAMA_CACHE, _USAGE
    _OLLAMA_CACHE = {"t": 0.0, "v": False, "models": []}
    with _USAGE_LOCK:
        _USAGE = {"total_calls": 0, "total_prompt_tokens": 0,
                  "total_completion_tokens": 0, "total_cost_usd": 0.0,
                  "by_provider": {}}


def _record_usage(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = PRICE_PER_1M.get(provider, {"input": 0.0, "output": 0.0})
    cost = round(prompt_tokens / 1e6 * price["input"]
                 + completion_tokens / 1e6 * price["output"], 8)
    with _USAGE_LOCK:
        _USAGE["total_calls"] += 1
        _USAGE["total_prompt_tokens"] += int(prompt_tokens)
        _USAGE["total_completion_tokens"] += int(completion_tokens)
        _USAGE["total_cost_usd"] = round(_USAGE["total_cost_usd"] + cost, 8)
        bucket = _USAGE["by_provider"].setdefault(
            provider, {"calls": 0, "prompt": 0, "completion": 0, "cost_usd": 0.0})
        bucket["calls"] += 1
        bucket["prompt"] += int(prompt_tokens)
        bucket["completion"] += int(completion_tokens)
        bucket["cost_usd"] = round(bucket["cost_usd"] + cost, 8)
    return cost


def usage_snapshot() -> dict:
    with _USAGE_LOCK:
        return {
            "total_calls": _USAGE["total_calls"],
            "total_prompt_tokens": _USAGE["total_prompt_tokens"],
            "total_completion_tokens": _USAGE["total_completion_tokens"],
            "total_cost_usd": _USAGE["total_cost_usd"],
            "by_provider": dict(_USAGE["by_provider"]),
        }


def trim_messages(messages: list, char_budget: int = 16000) -> list:
    """Trim hội thoại về ngân sách ~token (1 token ~= 4 ký tự).

    Bảo toàn: system (đã giữ làm head) luôn giữ; ưu tiên các lượt MỚI NHẤT.
    """
    if not messages:
        return []
    head = messages[:1] if messages[0].get("role") == "system" else []
    rest = messages[len(head):]
    budget = char_budget - sum(len(m.get("content", "")) for m in head)
    picked: list = []
    for msg in reversed(rest):
        content = msg.get("content", "")
        if budget - len(content) < 0 and picked:
            break
        budget -= len(content)
        picked.append(msg)
    picked.reverse()
    return head + picked


def _make_client(provider: str, api_key_value: str, timeout_s: float):
    """Tạo OpenAI-compatible client. Tách hàm để test thay bằng mock.

    max_retries=0: tự quản retry ở tầng chat()/stream() (đồng nhất giữa provider).
    """
    from openai import OpenAI

    return OpenAI(api_key=api_key_value, base_url=base_url(provider),
                  timeout=timeout_s, max_retries=0)


def _completions_kwargs(provider: str, messages, *, stream: bool,
                        temperature: float, max_tokens: int) -> dict:
    return {
        "model": default_model(provider),
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": bool(stream),
    }


def _retries() -> int:
    try:
        return max(1, int(os.environ.get("DEEPSEEK_RETRIES", DEFAULT_RETRIES)))
    except ValueError as exc:
        raise LLMError('DEEPSEEK_RETRIES must be an integer') from exc


def chat(messages, *, track_usage: "str | None" = None,
         temperature: float = DEFAULT_TEMPERATURE,
         max_tokens: int = DEFAULT_MAX_TOKENS,
         char_budget: int = 16000) -> LLMResult:
    """Gọi LLM non-stream theo thứ tự ưu tiên; trả LLMResult.

    Raise LLMError khi chưa cấu hình LLM hoặc đã cố hết retry-limit (KHÔNG nuốt lỗi).
    track_usage: nhãn (vd tên truy vấn) chỉ dùng cho log OBSERVABILITY.
    """
    provider = provider_status()
    if provider == "none":
        raise LLMError("chưa cấu hình LLM (key trống và Ollama không chạy)")

    if provider in ("deepseek", "openai"):
        messages = trim_messages(messages, char_budget=char_budget)
        timeout_s = timeout_for(provider, stream=False)
        backoff = DEFAULT_BACKOFF_S
        for attempt in range(1, _retries() + 1):
            try:
                with closing(_make_client(provider, api_key(provider) or "", timeout_s)) as client:
                    kwargs = _completions_kwargs(provider, messages, stream=False,
                                                 temperature=temperature, max_tokens=max_tokens)
                    resp = client.chat.completions.create(**kwargs)
                    text = (resp.choices[0].message.content or "").strip()
                    usage = getattr(resp, "usage", None)
                    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                    total = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)
                    cost = _record_usage(provider, prompt_tokens, completion_tokens)
                    logger.info("llm chat ok provider=%s model=%s attempt=%d tokens=%d cost=%.6f%s",
                                provider, default_model(provider), attempt, total, cost,
                                f" tag={track_usage}" if track_usage else "")
                    return LLMResult(text=text, provider=provider,
                                     model=default_model(provider),
                                     prompt_tokens=prompt_tokens,
                                     completion_tokens=completion_tokens,
                                     total_tokens=total, cost_usd=cost, retries=attempt - 1)
            except Exception as exc:  # noqa: BLE001
                if attempt == _retries():
                    raise LLMError(
                        f"{provider} chat thất bại sau {_retries()} lần thử "
                        f"({_safe_err_text(exc)})") from exc
                time.sleep(backoff)
                backoff *= 2
        raise LLMError("không thể gọi LLM")  # không tới được (cho type checker)

    # Ollama fallback
    try:
        text = ollama_chat(messages, num_predict=max_tokens, temperature=temperature)
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"ollama chat thất bại ({_safe_err_text(exc)})") from exc
    return LLMResult(text=text, provider="ollama", model=ollama_model())


def stream(messages, *, temperature: float = DEFAULT_TEMPERATURE,
           max_tokens: int = DEFAULT_MAX_TOKENS,
           char_budget: int = 16000) -> Iterator[str]:
    """Yield từng mảnh text theo thứ tự ưu tiên DeepSeek → OpenAI → Ollama.

    Lỗi TRƯỚC khi streaming được mảnh nào -> raise LLMError (caller rơi về fallback).
    Lỗi GIỮA STREAM (đã có mảnh) -> raise LLMError, phần đã stream giữ nguyên (caller
    quyết định hiển thị thông báo lỗi nối thêm).
    """
    provider = provider_status()
    if provider == "none":
        raise LLMError("chưa cấu hình LLM (key trống và Ollama không chạy)")

    if provider in ("deepseek", "openai"):
        messages = trim_messages(messages, char_budget=char_budget)
        timeout_s = timeout_for(provider, stream=True)
        backoff = DEFAULT_BACKOFF_S
        got_any = False
        for attempt in range(1, _retries() + 1):
            try:
                with closing(_make_client(provider, api_key(provider) or "", timeout_s)) as client:
                    kwargs = _completions_kwargs(provider, messages, stream=True,
                                                 temperature=temperature, max_tokens=max_tokens)
                    with closing(client.chat.completions.create(**kwargs)) as response:
                        for chunk in response:
                            delta = chunk.choices[0].delta.content
                            if delta:
                                got_any = True
                                yield delta
                    return
            except Exception as exc:  # noqa: BLE001
                if got_any:
                    raise LLMError(
                        f"{provider} stream đứt giữa chừng ({_safe_err_text(exc)})") from exc
                if attempt == _retries():
                    raise LLMError(
                        f"{provider} stream thất bại sau {_retries()} lần thử "
                        f"({_safe_err_text(exc)})") from exc
                if backoff <= STREAM_RETRY_MAX_BACKOFF:
                    time.sleep(backoff)
                backoff *= 2
        raise LLMError(f"{provider} stream không sinh được mảnh nào")

    yield from _stream_ollama(messages, num_predict=max_tokens, temperature=temperature)
