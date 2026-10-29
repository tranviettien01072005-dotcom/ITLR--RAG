"""Regression: API phải mở đáng tin — rate limit, sàn nhập, semantics lỗi đúng.

Trước fix:
  - /api/chat lỗi engine/LLM trả HTTP 200 với msg lỗi -> cán bộ giám sát không thấy hỏng.
  - Không có rate limit -> dội 10k request vào chat = đốt LLM/đie API.
  - Không sàn ký tự -> payload 2MB ngấm vào retriever.
  - /metrics công khai -> lộ nhịp truy vấn cho kẻ quét.

Không cần artifacts: engine giả như test_admin_security_cf.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from itlr.api import ratelimit
from itlr.engine import RecommenderEngine


class _StubEngine(RecommenderEngine):
    """Engine giả phản hồi nhanh — phục vụ rate limit + validation, không artifacts."""

    def search(self, query, item_type=None, min_pct=0.9, **kwargs):  # noqa: D102
        return {"results": [], "display": query, "note": "", "corrected": False}

    def chat(self, message, history=None, **kwargs):  # noqa: D102
        return {"response": "trả lời giả", "recommendations": [], "intent": "chat"}


class _ExplodingChatEngine(_StubEngine):
    """Engine giả mà chat luôn nổ — phục vụ path lỗi 503."""

    def chat(self, message, history=None, **kwargs):  # noqa: D102
        raise RuntimeError("LLM chết mô phỏng")


@pytest.fixture()
def client(monkeypatch):
    from itlr.api import server as srv

    monkeypatch.setenv("USE_OLLAMA", "0")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ITLR_ADMIN_TOKEN", raising=False)
    # Mỗi test bắt đầu từ rate limiter sạch.
    ratelimit.reset()

    fake = _StubEngine(items=[], model=None, search_index={},
                       cf_model=None, chatbot=None)

    def _load():
        return fake

    _load.cache_clear = lambda: None
    monkeypatch.setattr(srv, "load_engine", _load)
    with TestClient(srv.app) as c:
        yield c
    ratelimit.reset()
    os.environ.pop("ITLR_ADMIN_TOKEN", None)


# ---------------------------------------------------------------------------
# Sàn nhập (validation fail-fast -> 422, không âm thầm cắt)
# ---------------------------------------------------------------------------
def test_search_rejects_oversized_query(client):
    r = client.post("/api/search", json={"query": "q" * 501})
    assert r.status_code == 422


def test_search_rejects_out_of_range_min_pct(client):
    assert client.post("/api/search", json={"query": "docker", "min_pct": 150}).status_code == 422
    assert client.post("/api/search", json={"query": "docker", "min_pct": -1}).status_code == 422


def test_chat_rejects_oversized_message_and_history(client):
    assert client.post("/api/chat", json={"message": "m" * 2001}).status_code == 422
    bad_history = [{"role": "user", "content": "x"}] * 21
    assert client.post("/api/chat", json={"message": "hi", "history": bad_history}).status_code \
        == 422
    assert client.post(
        "/api/chat", json={"message": "hi",
                           "history": [{"role": "nope", "content": "x"}]}).status_code == 422


def test_for_you_rejects_huge_interested_list(client):
    r = client.post("/api/for-you", json={"persona": 1, "interested": list(range(201))})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Rate limit (per IP, sliding window; env đổi runtime)
# ---------------------------------------------------------------------------
def test_chat_rate_limit_429_then_recovers(client, monkeypatch):
    monkeypatch.setenv("ITLR_RATE_CHAT_PER_MIN", "1")
    ok = client.post("/api/chat", json={"message": "hỏi hợp lệ"})
    assert ok.status_code == 200
    limited = client.post("/api/chat", json={"message": "hỏi thứ hai"})
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers

    monkeypatch.setenv("ITLR_RATE_CHAT_PER_MIN", "0")  # tắt limiter tường minh
    assert client.post("/api/chat", json={"message": "hỏi lại"}).status_code == 200


def test_search_rate_limit_independent_of_chat(client, monkeypatch):
    monkeypatch.setenv("ITLR_RATE_SEARCH_PER_MIN", "1")
    assert client.post("/api/search", json={"query": "a"}).status_code == 200
    assert client.post("/api/search", json={"query": "a"}).status_code == 429
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 200


# ---------------------------------------------------------------------------
# Semantics lỗi: 503 thay cho 200 giả
# ---------------------------------------------------------------------------
def test_chat_engine_crash_returns_503(client, monkeypatch):
    from itlr.api import server as srv

    boom = _ExplodingChatEngine(items=[], model=None, search_index={},
                                cf_model=None, chatbot=None)
    def _load():
        return boom

    _load.cache_clear = lambda: None
    monkeypatch.setattr(srv, "load_engine", _load)
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 503
    assert r.json()["intent"] == "error"


def test_missing_artifacts_returns_503(client, monkeypatch):
    from itlr.api import server as srv

    def _boom():
        raise FileNotFoundError("không có artifacts")

    _boom.cache_clear = lambda: None
    monkeypatch.setattr(srv, "load_engine", _boom)
    for path, payload in [
        ("/api/search", {"query": "x"}),
        ("/api/chat", {"message": "x"}),
        ("/api/chat/stream", {"message": "x"}),
        ("/api/personas", None),
    ]:
        if payload is None:
            r = client.get(path)
        else:
            r = client.post(path, json=payload)
        assert r.status_code == 503, (path, r.status_code)


# ---------------------------------------------------------------------------
# /metrics không còn công khai
# ---------------------------------------------------------------------------
def test_metrics_requires_admin_token_for_remote(client, monkeypatch):
    # TestClient host = "testclient" (không phải loopback) -> phải đòi token.
    assert client.get("/metrics").status_code == 403

    monkeypatch.setenv("ITLR_ADMIN_TOKEN", "s3cret")
    assert client.get("/metrics").status_code == 403  # có token đòi mà chưa đưa
    ok = client.get("/metrics", headers={"X-Admin-Token": "s3cret"})
    assert ok.status_code == 200
    assert "requests_total" in ok.text


def test_metrics_open_for_loopback_without_token(client, monkeypatch):
    """Không đặt token + client loopback (dev local) vẫn xem được metric (unit check)."""
    from itlr.api import server as srv

    class _FakeReq:
        class client:  # noqa: N801
            host = "127.0.0.1"
        headers = {}

    assert srv._metrics_allowed(_FakeReq()) is True
    _FakeReq.client.host = "203.0.113.9"  # remote
    assert srv._metrics_allowed(_FakeReq()) is False
