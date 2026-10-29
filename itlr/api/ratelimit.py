"""Rate limiting TRONG TIẾN TRÌNH (sliding window) cho API FastAPI.

Giới hạn theo client IP trên các endpoint đắt (chat gọi LLM, search chạy retrieval).
Chỉ dùng một worker và một replica. Mặc định bỏ qua forwarding headers; sau reverse
proxy chỉ bật proxy headers với danh sách IP proxy tin cậy tường minh. Cấu hình qua env (đọc LẠI mỗi lần gọi — đổi runtime không cần restart):

    ITLR_RATE_SEARCH_PER_MIN = 120   (0 = tắt limiter cho bucket này)
    ITLR_RATE_CHAT_PER_MIN   = 30

429 trả kèm Retry-After để client/backoff đúng nghĩa, không âm thầm bỏ qua.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_LOCK = threading.Lock()
# Bucket này -> (IP -> deque timestamps). Giữ trong RAM; chỉ nhãn IP nên nhẹ.
_HITS: dict[str, dict[str, deque[float]]] = defaultdict(dict)
MAX_TRACKED_KEYS = 100_000  # chống phình RAM khi bị dội request giả IP


def _env_int(name: str, default: int) -> int:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < 0:
        return default
    return value


def client_ip(request: Request) -> str:
    host = request.client.host if request.client else ""
    return host or "unknown"


def enforce(request: Request, bucket: str, default_per_min: int) -> None:
    limit = _env_int(f"ITLR_RATE_{bucket}_PER_MIN", default_per_min)
    if limit <= 0:
        return
    key = client_ip(request)
    now = time.monotonic()
    with _LOCK:
        per_ip = _HITS[bucket]
        if key not in per_ip and len(per_ip) >= MAX_TRACKED_KEYS:
            expired = [ip for ip, times in per_ip.items() if not times or now - times[-1] > 60]
            for ip in expired:
                del per_ip[ip]
            if len(per_ip) >= MAX_TRACKED_KEYS:
                raise HTTPException(status_code=429, detail="Rate limiter capacity reached",
                                    headers={"Retry-After": "60"})
        hits = per_ip.setdefault(key, deque())
        while hits and now - hits[0] > 60.0:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Quá nhiều yêu cầu ({bucket}). Thử lại sau ít phút.",
                headers={"Retry-After": "60"},
            )
        hits.append(now)


def reset(state: dict | None = None) -> None:
    """Chỉ dành cho test: dọn sạch đếm rate."""
    with _LOCK:
        _HITS.clear()


def validate_workers() -> None:
    """In-memory buckets require exactly one process; deployment must enforce one replica."""
    for name in ("WEB_CONCURRENCY", "UVICORN_WORKERS"):
        if os.environ.get(name, "1") != "1":
            raise RuntimeError(f"{name} must be 1 with the in-process rate limiter")
