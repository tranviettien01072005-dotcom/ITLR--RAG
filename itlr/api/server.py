"""Web API (FastAPI) cho hệ thống gợi ý + chatbot — thay Streamlit, không cần streamlit.

Chạy: uvicorn itlr.api.server:app --host 0.0.0.0 --port 8000  (hoặc python -m itlr.api)
"""

import os
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import itlr.utils.runtime_patches  # noqa: F401,E402  (dọn nhiễu console trước khi nạp model)

import json  # noqa: E402
import time  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import List, Optional, Union  # noqa: E402

from fastapi import Depends, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import (  # noqa: E402
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field, field_validator  # noqa: E402

from itlr.api import ratelimit  # noqa: E402
from itlr.engine import load_engine  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Sàn nhập: chặn payload khổng lồ trước khi tới engine/LLM (DoS + lãng phí token).
QUERY_MAX_CHARS = 500
CHAT_MESSAGE_MAX_CHARS = 2000
CHAT_HISTORY_MAX_MSGS = 20
CHAT_CONTENT_MAX_CHARS = 4000
INTERESTED_MAX_ITEMS = 200

# Rate mặc định (per IP/phút). 0 qua env = tắt bucket đó.
RATE_SEARCH_DEFAULT = 120
RATE_CHAT_DEFAULT = 30


def _engine():
    """load_engine nhưng thiếu artifacts ⇒ 503 (không để 500 âm thầm)."""
    try:
        return load_engine()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Artifacts chưa build (chạy scripts/build_all_v2.py)")


def _rate_dependency(bucket: str, default_per_min: int):
    def dep(request: Request) -> None:
        ratelimit.enforce(request, bucket=bucket, default_per_min=default_per_min)
    return dep

_search_rate = _rate_dependency("SEARCH", RATE_SEARCH_DEFAULT)
_chat_rate = _rate_dependency("CHAT", RATE_CHAT_DEFAULT)


def _log(msg):
    """Log an toàn — không để lỗi mã hóa console làm chết app startup."""
    try:
        print(msg)
    except Exception:
        try:
            import sys as _sys
            _sys.stdout.write(msg.encode("ascii", "replace").decode() + "\n")
        except Exception:
            pass


def _prewarm_ollama():
    """Nạp sẵn model Ollama vào RAM (chạy nền) để câu hỏi chatbot đầu tiên không bị cold-start
    ~90s (nguyên nhân hay gây timeout ở câu đầu). Bỏ qua nếu đã có API key OpenAI hoặc
    USE_OLLAMA bị tắt tường minh — khớp cách _llm_available tự phát hiện Ollama."""
    _prewarm_ollama_skip = bool(
        os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    if _prewarm_ollama_skip:
        _log("[i] Có key LLM cloud (DeepSeek/OpenAI) — bỏ qua pre-warm Ollama.")
        return
    if str(os.environ.get("USE_OLLAMA", "")).lower() in ("0", "false", "no"):
        return
    import threading
    import urllib.request

    def _warm():
        url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "ping"}],
                              "stream": False, "keep_alive": "2h",
                              "options": {"num_predict": 1}}).encode()
        try:
            req = urllib.request.Request(f"{url}/api/chat", data=payload,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=300).read()
            _log(f"[OK] Đã pre-warm Ollama ({model}) — chatbot sẵn sàng trả lời nhanh.")
        except Exception as e:  # noqa: BLE001
            _log(f"[!] Pre-warm Ollama lỗi (bỏ qua): {e}")

    threading.Thread(target=_warm, daemon=True).start()


@asynccontextmanager
async def lifespan(_app):
    """Nạp artifacts ngay khi khởi động để lỗi thiếu artifacts lộ sớm, request đầu nhanh."""
    ratelimit.validate_workers()
    try:
        load_engine()
        _log("[OK] Engine sẵn sàng — API tại http://localhost:8000")
        _prewarm_ollama()
    except FileNotFoundError:
        _log(
            "[!] Chưa có model artifacts. Hãy build trước:\n"
            "    python scripts/build_all_v2.py\n"
            "(catalog V2 (legacy + crawl) -> build_model -> build_embeddings_v2 -> probe -> activate)\n"
            "CF (cf_model.pkl) là tùy chọn: không có thì /api/personas, /api/for-you trả 503."
        )
    yield


app = FastAPI(title="IT Learning Recommender API", version="1.0.0", lifespan=lifespan)


_METRICS = {"requests_total": 0, "errors_total": 0, "by_route": {}}


@app.middleware("http")
async def _track_metrics(request: Request, call_next):
    t0 = time.perf_counter()
    _METRICS["requests_total"] += 1
    try:
        resp = await call_next(request)
    except Exception:
        _METRICS["errors_total"] += 1
        raise
    dt_ms = (time.perf_counter() - t0) * 1000.0
    matched = request.scope.get("route")
    route = getattr(matched, "path", "unmatched")
    r = _METRICS["by_route"].setdefault(route, {"count": 0, "ms_sum": 0.0, "ms_max": 0.0})
    r["count"] += 1
    r["ms_sum"] += dt_ms
    r["ms_max"] = max(r["ms_max"], dt_ms)
    if resp.status_code >= 500:
        _METRICS["errors_total"] += 1
    resp.headers["Content-Security-Policy"] = ("default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return resp


@app.get("/live")
def live():
    return {"status": "ok"}


@app.get("/health")
def health():
    """Liveness/readiness: engine đã nạp được artifacts chưa + CF đang bật/tắt."""
    try:
        eng = load_engine()
    except FileNotFoundError:
        raise HTTPException(status_code=503,
                            detail="Artifacts chưa build (chạy scripts/build_all_v2.py)")
    return {"status": "ok", "engine": "ready",
            "cf": bool(getattr(eng, "cf_model", None) is not None),
            "items": int(len(eng.items)) if getattr(eng, "items", None) is not None else 0}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics(request: Request):
    """Phơi metric quan sát hệ thống dạng text (đếm request, độ trễ TB/đỉnh mỗi route).

    Bảo vệ: khi đặt ITLR_ADMIN_TOKEN thì /metrics đòi X-Admin-Token (prod); không đặt
    token thì chỉ cho phép client loopback (dev gỡ lỗi local) — không phải endpoint
    công khai cung cấp nhịp truy vấn cho kẻ quét.
    """
    if not _metrics_allowed(request):
        if _admin_token_expected():
            raise HTTPException(status_code=403, detail="Cần header X-Admin-Token.")
        raise HTTPException(
            status_code=403,
            detail="/metrics chỉ mở cho loopback khi chưa cấu hình ITLR_ADMIN_TOKEN.")
    lines = [
        f"requests_total {_METRICS['requests_total']}",
        f"errors_total {_METRICS['errors_total']}",
    ]
    for route, r in sorted(_METRICS["by_route"].items()):
        avg = r["ms_sum"] / r["count"] if r["count"] else 0.0
        safe = route.replace('"', "")
        lines.append(f'route_requests_total{{path="{safe}"}} {r["count"]}')
        lines.append(f'route_latency_ms_avg{{path="{safe}"}} {avg:.2f}')
        lines.append(f'route_latency_ms_max{{path="{safe}"}} {r["ms_max"]:.2f}')
    return "\n".join(lines) + "\n"


class SearchReq(BaseModel):
    query: str = Field(min_length=1, max_length=QUERY_MAX_CHARS)
    type: Optional[str] = Field(default=None, max_length=50)
    min_pct: int = Field(default=90, ge=0, le=100)


class ChatMsg(BaseModel):
    role: str = Field(min_length=1, max_length=20)
    content: str = Field(min_length=1, max_length=CHAT_CONTENT_MAX_CHARS)

    @field_validator("role")
    @classmethod
    def _known_role(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("role phải là 'user' hoặc 'assistant'")
        return v


class ChatReq(BaseModel):
    message: str = Field(min_length=1, max_length=CHAT_MESSAGE_MAX_CHARS)
    history: List[ChatMsg] = []

    @field_validator("history")
    @classmethod
    def _history_cap(cls, v: List[ChatMsg]) -> List[ChatMsg]:
        if len(v) > CHAT_HISTORY_MAX_MSGS:
            raise ValueError(f"history tối đa {CHAT_HISTORY_MAX_MSGS} tin nhắn")
        return v


class ForYouReq(BaseModel):
    persona: Union[int, str]
    interested: List[int] = []

    @field_validator("interested")
    @classmethod
    def _interested_cap(cls, v: List[int]) -> List[int]:
        if len(v) > INTERESTED_MAX_ITEMS:
            raise ValueError(f"interested tối đa {INTERESTED_MAX_ITEMS} item")
        return v


def _cf_unavailable_detail() -> str:
    return ("Collaborative Filtering chưa khả dụng (cf_model.pkl không có — tính năng tùy "
            "chọn V2). Search, chatbot và evaluation không bị ảnh hưởng.")


@app.post("/api/search", dependencies=[Depends(_search_rate)])
def api_search(req: SearchReq):
    eng = _engine()
    item_type = req.type if req.type in ("Khóa học", "Tài liệu") else None
    return eng.search(req.query, item_type=item_type, min_pct=req.min_pct)


_CHAT_ERROR_MSG = (
    "Xin lỗi, mình gặp trục trặc khi xử lý câu hỏi này. Bạn thử gửi lại hoặc diễn đạt khác giúp mình nhé."
)


@app.post("/api/chat", dependencies=[Depends(_chat_rate)])
def api_chat(req: ChatReq):
    eng = _engine()
    history = [{"role": m.role, "content": m.content} for m in req.history]
    try:
        result = eng.chat(req.message, history=history)
    except Exception as e:  # noqa: BLE001
        _log(f"[!] /api/chat lỗi: {e}")
        # 503: lỗi TẠM THỜI ở tầng chatbot/LLM — client thấy rõ lỗi kiểu HTTP,
        # báo cáo lỗi không còn bị che bởi HTTP 200 "giả thành công".
        return JSONResponse(
            status_code=503,
            content={"response": _CHAT_ERROR_MSG, "recommendations": [],
                     "intent": "error"})
    return result


@app.post("/api/chat/stream", dependencies=[Depends(_chat_rate)])
def api_chat_stream(req: ChatReq):
    """Trả lời chatbot dạng SSE — mỗi frame là 1 dòng `data: {json}` rồi dòng trống.

    Model local (Ollama) chậm ~30-135s/câu; nếu chờ cả câu, proxy/Heroku (timeout 30s) trả
    503 trước khi xong. Stream đẩy chữ ngay khi sinh nên không chạm hard-timeout.
    Lỗi TRƯỚC khi stream bắt đầu ⇒ 503 thật; lỗi giữa stream ⇒ frame json vì không thể
    đổi status sau khi header đã gửi.
    """
    eng = _engine()
    history = [{"role": m.role, "content": m.content} for m in req.history]

    def _frame(obj):
        return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"

    def gen():
        try:
            for ev, data in eng.chat_stream(req.message, history=history):
                if ev == "text":
                    yield _frame({"type": "text", "text": data})
                elif ev == "sources":
                    yield _frame({"type": "sources", "sources": data})
                elif ev in {"meta", "final"}:
                    yield _frame({"type": ev, **data})
        except Exception as e:  # noqa: BLE001
            _log(f"[!] /api/chat/stream lỗi: {e}")
            yield _frame({"type": "error", "message": _CHAT_ERROR_MSG})
            yield _frame({"type": "final", "response": _CHAT_ERROR_MSG, "intent": "error",
                          "sources": [], "recommendations": [], "provisional": False,
                          "generation_mode": "error", "generation_error": "stream_failed"})
        yield _frame({"type": "done"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _admin_token_expected() -> str:
    """Token quản trị đọc TẠI THỜI ĐIỂM GỌI (env có thể đổi reload runtime).
    Rỗng ⇒ API quản trị BỊ TẮT (không có mặc định — an toàn trước tiên)."""
    return str(os.environ.get("ITLR_ADMIN_TOKEN", "")).strip()


def _admin_authorized(request: Request) -> bool:
    import secrets

    expected = _admin_token_expected()
    given = request.headers.get("X-Admin-Token", "")
    if not expected:
        return False
    return secrets.compare_digest(given, expected)


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _metrics_allowed(request: Request) -> bool:
    """Token cấu hình ⇒ đòi token (prod). Không token ⇒ chỉ loopback (dev local)."""
    if _admin_token_expected():
        return _admin_authorized(request)
    return ratelimit.client_ip(request) in _LOOPBACK_HOSTS


@app.post("/admin/reload")
def admin_reload(request: Request):
    """Nạp lại artifacts mà không cần tắt/mở lại tiến trình — gọi sau khi
    build_all_v2.py kích hoạt phiên bản mới, để search/chatbot dùng dữ liệu mới ngay.

    Bảo vệ: BẮT BUỘC header `X-Admin-Token` khớp env `ITLR_ADMIN_TOKEN`. Env rỗng
    (chưa cấu hình) ⇒ 403 + API coi như tắt — tránh ai cũng reload được server.
    """
    if not _admin_token_expected():
        raise HTTPException(status_code=403,
                            detail="Admin reload bị tắt: chưa cấu hình ITLR_ADMIN_TOKEN "
                                   "(đặt env rồi khởi động lại server).")
    if not _admin_authorized(request):
        raise HTTPException(status_code=403, detail="Sai hoặc thiếu header X-Admin-Token.")
    try:
        if hasattr(load_engine, "reload"):
            eng = load_engine.reload()
        else:  # Test/provider adapters retain the historical cache interface.
            load_engine.cache_clear()
            eng = load_engine()
    except FileNotFoundError:
        raise HTTPException(status_code=503,
                            detail="Reload xong pointers nhưng artifacts chưa build được nạp "
                                   "(chạy scripts/build_all_v2.py).")
    n = len(eng.items) if hasattr(eng, "items") else None
    return {"ok": True, "reloaded": True, "items": n,
            "cf": bool(getattr(eng, "cf_model", None) is not None)}


@app.get("/api/personas")
def api_personas():
    from itlr.engine import CFUnavailable

    try:
        return _engine().personas()
    except CFUnavailable:
        raise HTTPException(status_code=503, detail=_cf_unavailable_detail())


@app.post("/api/for-you")
def api_for_you(req: ForYouReq):
    from itlr.engine import CFUnavailable

    try:
        return _engine().for_you(req.persona, interested_item_ids=req.interested)
    except CFUnavailable:
        raise HTTPException(status_code=503, detail=_cf_unavailable_detail())
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail="Không tìm thấy persona này.")


@app.get("/api/suggested")
def api_suggested():
    from itlr.chatbot.chatbot import SUGGESTED_PROMPTS, EducationalChatbot

    return {"prompts": SUGGESTED_PROMPTS, "welcome": EducationalChatbot.WELCOME_MESSAGE}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
