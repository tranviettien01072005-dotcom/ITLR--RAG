# ITLR-RAG V2 — image chạy API (FastAPI + uvicorn).
#
# Container mount `var/` từ host để dùng chung artifacts/SQLite:
#   docker compose up -d
# Build index lần đầu / refresh: xem deploy/DEPLOY.md.
#
# Lưu ý: image KHÔNG chứa model HF — model được tải lúc runtime vào volume
# `var/hf` (HF_HOME). Không build artifacts lúc docker build (giữ image nhẹ,
# và artifacts thuộc về dữ liệu runtime, có phiên bản + được probe/activate).

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/var/hf \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

# Chỉ copy file khai báo deps trước — tận dụng cache layer khi đổi code
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Code + cấu hình + eval (eval cần để eval mọi thứ cũng chạy được trong image)
COPY itlr ./itlr
COPY eval ./eval
COPY configs ./configs
COPY scripts ./scripts
COPY pytest.ini ./

# Smoke-import: bắt lỗi deps thiếu ngay lúc build image, không đợi khi chạy
RUN python -c "import itlr.api.server" \
    && python -c "import itlr.collect.runner; import itlr.indexv2; import itlr.versioning"

# Dữ liệu runtime (artifacts + SQLite crawl.db + HF cache) sống ngoài image
RUN mkdir -p /app/var/artifacts /app/var/data/collect /app/var/hf

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
  CMD python -c "import sys,urllib.request; \
r=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8); \
sys.exit(0 if r.status==200 else 1)" || exit 1

CMD ["uvicorn", "itlr.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
