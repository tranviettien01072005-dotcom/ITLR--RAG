"""Kiểm tra bảo vệ /admin/reload + hành vi CF TÙY CHỌN V2 (không cần artifacts build).

Sàn V2:
- API quản trị phải đòi header X-Admin-Token khớp env ITLR_ADMIN_TOKEN; env rỗng ⇒ tắt (403).
- Thiếu cf_model.pkl ⇒ engine vẫn chạy; /api/personas và /api/for-you trả 503 (không 500
  âm thầm) — CF là tính năng tùy chọn, không làm chết search/chatbot.
"""

import os

import pytest
from fastapi.testclient import TestClient

from itlr.engine import CFUnavailable, RecommenderEngine


# ---------------------------------------------------------------------------
# Unit level: engine phải COI CF là tùy chọn
# ---------------------------------------------------------------------------
def test_engine_raise_cf_unavailable_when_no_cf_model():
    eng = RecommenderEngine(items=None, model=None, search_index=None,
                            cf_model=None, chatbot=None)
    with pytest.raises(CFUnavailable):
        eng.personas()
    with pytest.raises(CFUnavailable):
        eng.for_you(1)


# ---------------------------------------------------------------------------
# API level: fake engine (không artifacts) kiểm đường dẫn lỗi CF + admin token
# ---------------------------------------------------------------------------
@pytest.fixture()
def client(monkeypatch):
    from itlr.api import server as srv

    monkeypatch.setenv("USE_OLLAMA", "0")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ITLR_ADMIN_TOKEN", raising=False)  # mặc định: admin TẮT

    fake = RecommenderEngine(items=[], model=None, search_index={},
                             cf_model=None, chatbot=None)

    def _load():  # thay load_engine thật — không cần artifacts
        return fake

    _load.cache_clear = lambda: None
    monkeypatch.setattr(srv, "load_engine", _load)

    with TestClient(srv.app) as c:  # with → lifespan chạy (dùng fake)
        yield c
    # dọn env sau mỗi test cho chắc
    os.environ.pop("ITLR_ADMIN_TOKEN", None)


def test_admin_reload_disabled_without_token(client):
    r = client.post("/admin/reload")
    assert r.status_code == 403
    assert "ITLR_ADMIN_TOKEN" in r.json()["detail"]


def test_admin_reload_wrong_token(client, monkeypatch):
    monkeypatch.setenv("ITLR_ADMIN_TOKEN", "secret-token")
    r = client.post("/admin/reload", headers={"X-Admin-Token": "wrong"})
    assert r.status_code == 403
    assert "X-Admin-Token" in r.json()["detail"]
    r = client.post("/admin/reload")  # thiếu header hoàn toàn
    assert r.status_code == 403


def test_admin_reload_correct_token(client, monkeypatch):
    monkeypatch.setenv("ITLR_ADMIN_TOKEN", "secret-token")
    r = client.post("/admin/reload", headers={"X-Admin-Token": "secret-token"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["reloaded"] is True


def test_health_reports_cf_false(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    # Đọc theo field, không ghim đúng khóa: readiness có thể thêm fingerprint
    # artifacts mà không hợp đồng cũ bị phá vỡ.
    assert body["status"] == "ok" and body["engine"] == "ready"
    assert body["cf"] is False and body["items"] == 0


def test_personas_503_when_cf_missing(client):
    r = client.get("/api/personas")
    assert r.status_code == 503
    assert "cf_model.pkl" in r.json()["detail"]


def test_for_you_503_when_cf_missing(client):
    r = client.post("/api/for-you", json={"persona": 1})
    assert r.status_code == 503
    assert "cf_model.pkl" in r.json()["detail"]
