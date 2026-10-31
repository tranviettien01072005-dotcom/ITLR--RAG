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
from contextlib import asynccontextmanager, aclosing  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import List, Optional, Union  # noqa: E402

from fastapi import Depends, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import (  # noqa: E402
    FileResponse,
    JSONResponse,
    PlainTextResponse,
)  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field, field_validator  # noqa: E402

from itlr.api.streaming import ClosingStreamingResponse
from itlr.api import ratelimit  # noqa: E402
from itlr.observability import metrics as obs  # noqa: E402
from itlr.observability.tracing import init_tracing, span  # noqa: E402
from itlr.engine import load_engine  # noqa: E402
from itlr.retrieval.service import DEFAULT_SEARCH_MIN_PCT  # noqa: E402
from itlr.versioning import VersionError  # noqa: E402

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
RATE_ADMIN_DEFAULT = 10


def _artifact_load_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Artifacts chưa build hoặc integrity hỏng (chạy scripts/build_all_v2.py: "
               "staging → probe → activate)")


def _engine():
    """load_engine nhưng thiếu artifacts/integrity hỏng ⇒ 503 (không để 500 âm thầm)."""
    try:
        return load_engine()
    except (FileNotFoundError, VersionError):
        raise _artifact_load_error()


def _rate_dependency(bucket: str, default_per_min: int):
    def dep(request: Request) -> None:
        ratelimit.enforce(request, bucket=bucket, default_per_min=default_per_min)
    return dep

_search_rate = _rate_dependency("SEARCH", RATE_SEARCH_DEFAULT)
_chat_rate = _rate_dependency("CHAT", RATE_CHAT_DEFAULT)
_admin_rate = _rate_dependency("ADMIN", RATE_ADMIN_DEFAULT)


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
        # Single source for provider defaults/validation lives in llm_client.
        from itlr.chatbot.llm_client import LLMError, base_url, default_model
        try:
            url = base_url("ollama").rstrip("/")
            model = default_model("ollama")
        except LLMError as exc:
            _log(f"[!] Cấu hình Ollama không hợp lệ — bỏ qua pre-warm: {exc}")
            return
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "ping"}],
                              "stream": False, "keep_alive": "2h",
                              "options": {"num_predict": 1}}).encode()
        try:
            req = urllib.request.Request(f"{url}/api/chat", data=payload,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as response:
                response.read()
            _log(f"[OK] Đã pre-warm Ollama ({model}) — chatbot sẵn sàng trả lời nhanh.")
        except Exception as e:  # noqa: BLE001
            _log(f"[!] Pre-warm Ollama lỗi (bỏ qua): {e}")

    threading.Thread(target=_warm, daemon=True).start()


def _provider_label() -> str:
    """Bounded provider label; no model prompts or keys."""
    if str(os.environ.get("USE_OLLAMA", "")).lower() in ("1", "true", "yes"):
        return "ollama"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "template"


@asynccontextmanager
async def lifespan(_app):
    """Nạp artifacts ngay khi khởi động để lỗi thiếu artifacts lộ sớm, request đầu nhanh."""
    ratelimit.validate_workers()
    if init_tracing("itlr-api"):
        _log("[i] OpenTelemetry tracing bật (OTLP exporter).")
    try:
        load_engine()
        _log("[OK] Engine sẵn sàng — API tại http://localhost:8000")
        _prewarm_ollama()
    except (FileNotFoundError, VersionError) as exc:
        _log(
            f"[!] Artifacts chưa sẵn sàng ({exc.__class__.__name__}). Hãy build trước:\n"
            "    python scripts/build_all_v2.py\n"
            "(staging → probe → activate; chi tiết: python -m itlr.indexv2)\n"
            "CF (cf_model.pkl) là tùy chọn: không có thì /api/personas, /api/for-you trả 503."
        )
    yield


app = FastAPI(title="IT Learning Recommender API", version="1.0.0", lifespan=lifespan)


_METRICS = {"requests_total": 0, "errors_total": 0, "by_route": {}}


@app.middleware("http")
async def _trace_request(request: Request, call_next):
    with span("http.request", method=request.method) as current:
        response = await call_next(request)
        route = request.scope.get("route")
        if current is not None:
            current.set_attribute("route", getattr(route, "path", "unmatched"))
            current.set_attribute("status", response.status_code)
        return response


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
    from fastapi import Request as _Req  # local alias keeps module import order stable
    route = request.scope.get("route")
    route_path = getattr(route, "path", "unmatched")
    obs.observe_http(route_path, request.method, resp.status_code, dt_ms / 1000.0)
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
    except (FileNotFoundError, VersionError):
        raise _artifact_load_error()
    fingerprint = getattr(eng, "artifact_fingerprint", None) or {}
    items = int(len(eng.items)) if getattr(eng, "items", None) is not None else 0
    obs.set_artifact_info(fingerprint.get("version"), fingerprint.get("manifest_sha256"), items)
    return {"status": "ok", "engine": "ready",
            "cf": bool(getattr(eng, "cf_model", None) is not None),
            "items": items,
            "artifacts": fingerprint or None}


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


@app.get("/metrics/prometheus", response_class=PlainTextResponse)
def prometheus_metrics(request: Request):
    """Prometheus text format behind the same auth as /metrics (token or loopback)."""
    if not _metrics_allowed(request):
        if _admin_token_expected():
            raise HTTPException(status_code=403, detail="Cần header X-Admin-Token.")
        raise HTTPException(status_code=403, detail="/metrics chỉ mở cho loopback.")
    body, content_type = obs.render_metrics()
    return PlainTextResponse(body, media_type=content_type)


class SearchReq(BaseModel):
    query: str = Field(min_length=1, max_length=QUERY_MAX_CHARS)
    type: Optional[str] = Field(default=None, max_length=50)
    min_pct: int = Field(default=DEFAULT_SEARCH_MIN_PCT, ge=0, le=100)


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


def _history_payload(req: ChatReq) -> List[dict]:
    """Provider history shape (role/content only) shared by chat and stream."""
    return [{"role": m.role, "content": m.content} for m in req.history]


def _cf_unavailable_detail() -> str:
    return ("Collaborative Filtering chưa khả dụng (cf_model.pkl không có — tính năng tùy "
            "chọn V2). Search, chatbot và evaluation không bị ảnh hưởng.")


@app.post("/api/search", dependencies=[Depends(_search_rate)])
def api_search(req: SearchReq):
    eng = _engine()
    item_type = req.type if req.type in ("Khóa học", "Tài liệu") else None
    started = time.perf_counter()
    with span("retrieval.search"):
        result = eng.search(req.query, item_type=item_type, min_pct=req.min_pct)
        obs.observe_retrieval("search", time.perf_counter() - started)
    return result


_CHAT_ERROR_MSG = (
    "Xin lỗi, mình gặp trục trặc khi xử lý câu hỏi này. Bạn thử gửi lại hoặc diễn đạt khác giúp mình nhé."
)


@app.post("/api/chat", dependencies=[Depends(_chat_rate)])
def api_chat(req: ChatReq):
    eng = _engine()
    history = _history_payload(req)
    provider = _provider_label()
    with span("generation.chat", provider=provider):
        try:
            started = time.perf_counter()
            result = eng.chat(req.message, history=history)
            mode = str(result.get("generation_mode") or "unknown")
            obs.observe_llm(provider, mode, time.perf_counter() - started)
            obs.observe_generation(mode, ((result.get("citation_validation") or {}).get("status")))
        except Exception as e:  # noqa: BLE001
            _log(f"[!] /api/chat lỗi: {e}")
            obs.observe_generation("error", None)
            # 503: lỗi TẠM THỜI ở tầng chatbot/LLM — client thấy rõ lỗi kiểu HTTP,
            # báo cáo lỗi không còn bị che bởi HTTP 200 "giả thành công".
            return JSONResponse(
                status_code=503,
                content={"response": _CHAT_ERROR_MSG, "recommendations": [],
                         "intent": "error"})
    return result


@app.post("/api/chat/stream", dependencies=[Depends(_chat_rate)])
async def api_chat_stream(req: ChatReq):
    """Trả lời chatbot dạng SSE — mỗi frame là 1 dòng `data: {json}` rồi dòng trống.

    Text là provisional; chỉ final xác nhận completion/citation. Async provider I/O
    đóng socket khi client disconnect và giữ total deadline ngay cả khi provider đứng.
    Lỗi giữa stream dùng frame json vì headers đã được gửi.
    """
    eng = _engine()
    history = _history_payload(req)

    def _frame(obj):
        return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"

    async def _frames():
        # Legacy engines retain their sync contract; current engines use cancellable I/O.
        from starlette.concurrency import iterate_in_threadpool
        events = (eng.achat_stream(req.message, history=history) if hasattr(eng, "achat_stream")
                  else iterate_in_threadpool(eng.chat_stream(req.message, history=history)))
        provider = _provider_label()
        started = time.perf_counter()
        ttft: float | None = None
        final: dict | None = None
        result = "aborted"
        try:
            async with aclosing(events):
                async for ev, data in events:
                    if ev == "text":
                        if ttft is None:
                            ttft = time.perf_counter() - started
                            obs.observe_ttft(provider, ttft)
                        yield _frame({"type": "text", "text": data})
                    elif ev == "sources":
                        yield _frame({"type": "sources", "sources": data})
                    elif ev in {"meta", "final"}:
                        if ev == "final":
                            final = data
                        yield _frame({"type": ev, **data})
            yield _frame({"type": "done"})
            result = "done"
        except Exception as e:  # noqa: BLE001
            _log(f"[!] /api/chat/stream lỗi: {e}")
            result = "error"
            yield _frame({"type": "error", "message": _CHAT_ERROR_MSG})
            yield _frame({"type": "final", "response": _CHAT_ERROR_MSG, "intent": "error",
                          "sources": [], "recommendations": [], "provisional": False,
                          "generation_mode": "error", "generation_error": "stream_failed"})
            yield _frame({"type": "done"})
        finally:
            elapsed = time.perf_counter() - started
            if final is not None:
                mode = str(final.get("generation_mode") or "unknown")
                obs.observe_llm(provider, mode, elapsed)
                obs.observe_generation(
                    mode, ((final.get("citation_validation") or {}).get("status")))
            obs.observe_sse(result, elapsed)

    async def gen():
        with span("sse.chat", provider=_provider_label()):
            # Explicitly close the inner generator: an abandoned `async for` would only be
            # finalized later, delaying engine/provider cleanup on client disconnect.
            async with aclosing(_frames()) as frames:
                async for frame in frames:
                    yield frame

    return ClosingStreamingResponse(
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
    # compare_digest với str chỉ nhận ASCII; header không tin cậy có thể non-ASCII
    # (UTF-8 thật hoặc ISO-8859-1 của proxy) → so trên bytes để luôn 403, không 500.
    return secrets.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _metrics_allowed(request: Request) -> bool:
    """Token cấu hình ⇒ đòi token (prod). Không token ⇒ chỉ loopback (dev local).

    Chấp nhận `X-Admin-Token` hoặc `Authorization: Bearer <token>` để Prometheus
    (credentials_file) scrape được mà không phải tắt auth.
    """
    expected = _admin_token_expected()
    if expected:
        if _admin_authorized(request):
            return True
        import secrets
        header = request.headers.get("authorization", "")
        given = header[7:] if header.startswith("Bearer ") else ""
        try:
            return secrets.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))
        except (UnicodeError, ValueError):
            return False
    return ratelimit.client_ip(request) in _LOOPBACK_HOSTS


@app.post("/admin/reload", dependencies=[Depends(_admin_rate)])
def admin_reload(request: Request):
    """Nạp lại artifacts mà không cần tắt/mở lại tiến trình — gọi sau khi
    build_all_v2.py kích hoạt phiên bản mới, để search/chatbot dùng dữ liệu mới ngay.

    Bảo vệ: BẮT BUỘC header `X-Admin-Token` khớp env `ITLR_ADMIN_TOKEN`; bucket rate
    "ADMIN" giới hạn dò token (env `ITLR_RATE_ADMIN_PER_MIN`, 0 = tắt). Env rỗng
    (chưa cấu hình) ⇒ 403 + API coi như tắt — tránh ai cũng reload được server. Mỗi lần
    auth hụt được GHI LOG (audit) — thay vì bỏ qua im im.
    """
    if not _admin_token_expected():
        raise HTTPException(status_code=403,
                            detail="Admin reload bị tắt: chưa cấu hình ITLR_ADMIN_TOKEN "
                                   "(đặt env rồi khởi động lại server).")
    if not _admin_authorized(request):
        _log(f"[!] /admin/reload auth fail từ {ratelimit.client_ip(request)}")
        raise HTTPException(status_code=403, detail="Sai hoặc thiếu header X-Admin-Token.")
    try:
        if hasattr(load_engine, "reload"):
            eng = load_engine.reload()
        else:  # Test/provider adapters retain the historical cache interface.
            load_engine.cache_clear()
            eng = load_engine()
    except (FileNotFoundError, VersionError):
        raise _artifact_load_error()
    n = len(eng.items) if hasattr(eng, "items") else None
    fingerprint = getattr(eng, "artifact_fingerprint", None) or {}
    obs.set_artifact_info(fingerprint.get("version"), fingerprint.get("manifest_sha256"), n)
    return {"ok": True, "reloaded": True, "items": n,
            "cf": bool(getattr(eng, "cf_model", None) is not None),
            "artifacts": fingerprint or None}


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
