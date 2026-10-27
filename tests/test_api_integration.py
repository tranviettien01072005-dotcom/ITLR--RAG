"""Kiểm tra integration API FastAPI (chỉ chạy khi artifacts ĐÃ build).

Chạy sau `python scripts/build_all.py`. Không cần LLM: đặt USE_OLLAMA=0 + xóa key
để ép nhánh template — toàn bộ endpoint phải hoạt động deterministically.
"""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    not (ROOT / "var" / "artifacts" / "embeddings.pkl").exists(),
    reason="cần artifacts đã build (scripts/build_all.py)")


@pytest.fixture(scope="module")
def client():
    os.environ["USE_OLLAMA"] = "0"
    os.environ.pop("DEEPSEEK_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)

    from fastapi.testclient import TestClient

    from itlr.api import server as srv
    srv.load_engine.cache_clear()
    with TestClient(srv.app) as c:     # with -> lifespan chạy (nạp engine)
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_search_endpoint(client):
    r = client.post("/api/search", json={"query": "học docker kubernetes cơ bản",
                                         "min_pct": 70})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["results"], list)
    if data["results"]:
        top = data["results"][0]
        assert "item_id" in top and "title" in top


def test_chat_template_mode_works(client):
    r = client.post("/api/chat", json={"message": "Docker là gì và dùng để làm gì?",
                                       "history": []})
    assert r.status_code == 200
    data = r.json()
    assert data["response"], "template mode phải trả câu trả lời không trống"
    assert "intent" in data


def test_chat_stream_sse_frames(client):
    with client.stream("POST", "/api/chat/stream",
                       json={"message": "Git khác SVN thế nào?", "history": []}) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        frames = []
        for line in r.iter_lines():
            if line.startswith("data: "):
                frames.append(line)
        assert frames and any('"type": "done"' in f for f in frames)


def test_for_you_with_persona(client):
    personas = client.get("/api/personas").json()
    assert isinstance(personas, list) and len(personas) > 0
    uid = personas[0]["uid"]
    r = client.post("/api/for-you", json={"persona": uid})
    assert r.status_code == 200
    recs = r.json().get("recs", [])
    assert isinstance(recs, list)
