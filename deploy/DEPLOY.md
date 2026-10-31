# Cài đặt local và vòng đời dữ liệu

Hướng dẫn cho **ITLR–RAG | Intelligent IT Learning Platform** trên Linux local: cài đặt,
cấu hình, nạp dữ liệu, build/probe/activate index, chạy API + Web, xử lý sự cố. HTTPS/Compose
một host: [PRODUCTION](PRODUCTION.md). Kiến trúc: [ARCHITECTURE](../docs/ARCHITECTURE.md).

Giới hạn hiện hành: một worker/replica mỗi service, local filesystem, khóa file Linux.
Restart container **không** tự migrate/seed/activate.

**Docker full stack local** (Web + API + PostgreSQL + Ollama/Qwen): dùng
[`compose.local.yml`](../compose.local.yml) và hướng dẫn trong
[README §Docker Compose](../README.md#docker-compose-full-stack). Production TLS: [PRODUCTION](PRODUCTION.md).
Root `docker-compose.yml` chỉ còn API + refresh job (legacy), không phải full stack.

## Thành phần

| Thành phần | Địa chỉ local | Yêu cầu |
|---|---|---|
| Web Express/TypeScript/EJS | `http://localhost:3000` | Node.js 22, PostgreSQL |
| API FastAPI | `http://127.0.0.1:8000` | Python ≥3.11 (đã kiểm với 3.14.4), artifacts + model cache |
| PostgreSQL | theo `DATABASE_URL` | database + credentials riêng |
| Ollama (tùy chọn) | `http://127.0.0.1:11434` | model generation local |

Checkout mới không tự có `var/`, model hay database. Login render được không chứng minh
RAG hay DB đã sẵn sàng.

## Cài đặt

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd web
npm ci
cp .env.example .env
```

Root `.env.example` là tài liệu cấu hình; lệnh Python không tự nạp `.env`. Nếu muốn dùng
file local, source có chủ đích:

```bash
cp .env.example .env    # điền giá trị
set -a; . ./.env; set +a
```

Không source file `.env` từ nguồn không tin cậy.

## Cấu hình

### Python / API

| Biến | Mặc định / ý nghĩa |
|---|---|
| `ITLR_ARTIFACTS_DIR` | override thư mục artifacts: có thể trỏ **root có `CURRENT.json`** (tự resolve version) hoặc **version/staging phẳng** có `MANIFEST.json`; mặc định `var/artifacts` |
| `ITLR_ITEMS_CSV`, `ITLR_INTERACTIONS_CSV` | override CSV catalog/interactions |
| `ITLR_REQUIRE_ARTIFACT_MANIFEST=1` | kiểm SHA256 inventory trước khi nạp pickle |
| `ITLR_ADMIN_TOKEN` | bảo vệ `/admin/reload` và `/metrics`; rỗng ⇒ tắt (403) |
| `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` | provider chính (mặc định `deepseek-flash`) |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` | provider OpenAI-compatible |
| `USE_OLLAMA=1`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_TIMEOUT` | provider local; timeout phải hữu hạn dương |
| `EMBEDDING_MODEL`, `RERANKER_MODEL`, `DISABLE_RERANKER` | preset E5/BGE và reranker |
| `ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET` | giới hạn prompt view mỗi chunk; mặc định `None` ([ADR-013](../docs/decisions/ADR-013-evidence-excerpt-budget.md)) |
| `ITLR_RATE_SEARCH_PER_MIN`, `ITLR_RATE_CHAT_PER_MIN`, `ITLR_RATE_ADMIN_PER_MIN` | rate limit theo IP; `0` = tắt bucket |
| `HF_HOME`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` | cache và chế độ offline của model |
| `ITLR_REAL_ONLY=1` | refresh pipeline chỉ dùng nguồn thật |

### Web

| Biến | Yêu cầu |
|---|---|
| `DATABASE_URL` | PostgreSQL URL, mật khẩu riêng, không dùng mặc định phổ biến |
| `JWT_SECRET` | ≥32 ký tự, ngẫu nhiên |
| `ADMIN_PASSCODE` | ≥16 ký tự, ngẫu nhiên |
| `APP_ORIGIN` | origin tuyệt đối; production bắt buộc HTTPS |
| `RECOMMENDER_URL` | `http://127.0.0.1:8000` (local) / `http://api:8000` (Compose) |
| `PORT`, `WEB_CONCURRENCY=1`, `TRUSTED_PROXIES` | một worker; chỉ khai IP/CIDR proxy thật |
| `ITEMS_CSV` | đường dẫn CSV catalog (Compose: `/app/var/data/web_items.csv`) |
| `SMTP_*`, `RESET_TOKEN_TTL_MINUTES`, `RESET_EMAIL_COOLDOWN_SECONDS` | tùy chọn; thiếu SMTP thì không gửi email; cooldown chống spam reset (mặc định 60s) |

Sinh secret: `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'` — không đưa
kết quả vào commit/log/report. Giữ `.env` 0600 và ngoài Git.

## Nạp dữ liệu

Chọn một nguồn: import snapshot curated (118 trang thật) hoặc crawl có kiểm soát.

```bash
.venv/bin/python scripts/import_curated_snapshot.py
# hoặc
.venv/bin/python scripts/collect_data.py --sources help
.venv/bin/python scripts/collect_data.py
```

Crawler ghi `var/data/collect/crawl.db` + `last_run.json`; robots/rate limit không thay thế
việc kiểm giấy phép. Rolling feed không phải danh mục đầy đủ — không suy ra bài bị xóa chỉ
vì vắng mặt.

## Build, probe, activate

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  USE_OLLAMA=0 DISABLE_RERANKER=1 \
  .venv/bin/python scripts/build_all_v2.py --real-only --no-activate
```

- `--real-only` chỉ lấy nguồn thật; bỏ cờ có thể ghép legacy synthetic.
- `--with-cf` sinh interactions synthetic và CF (tùy chọn; thiếu CF thì personas/for-you 503).
- `--online` chỉ khi chủ động cho phép tải model.
- Tên CLI V2 giữ vì tương thích; builder lưu chunk vectors cho đường V3.

Probe kiểm cấu trúc, hàng/cột, NaN, norm, ID, self-retrieval và nạp engine trong subprocess;
kết quả trong `MANIFEST.json` là kiểm tra kỹ thuật, không phải đánh giá chất lượng.

Sau khi build/activate, **đồng bộ catalog Web** — bỏ bước này thì item mới có trong search/chat
nhưng PostgreSQL chưa có row, người dùng bấm khóa học sẽ nhận 404:

```bash
.venv/bin/python scripts/export_web_catalog.py --refresh   # merge, giữ row cộng đồng
.venv/bin/python scripts/verify_web_catalog.py             # fail nếu thiếu id/link sai
cd web && npm run sync                                    # upsert PostgreSQL, không xóa enrollment
```

`--refresh` cập nhật row crawl, thêm item mới, giữ row cộng đồng do Web append và bỏ row crawl
cũ khỏi CSV (PostgreSQL không xóa row). `scripts/refresh_pipeline.py` tự chạy export + verify sau
build; thêm `--sync-web` (cần `DATABASE_URL`) để chạy luôn `npm run sync`. Audit link nguồn
(HTTP status/redirect/robots/404) chạy riêng vì cần mạng:

```bash
.venv/bin/python scripts/audit_source_links.py --csv var/data/web_items.csv --limit 50 --json /tmp/link-audit.json
```

Activate version đã probe (không có `--no-activate` thì builder tự activate sau probe):

```python
from itlr import versioning
versioning.activate(version="TEN_VERSION_DA_PROBE")
```

Sau đó reload API:

```bash
curl -fsS -X POST http://127.0.0.1:8000/admin/reload -H "X-Admin-Token: $ITLR_ADMIN_TOKEN"
```

`/health` trả `artifacts.version` + `manifest_sha256` của engine đang phục vụ; reload lỗi giữ
engine cũ. Rollback: `versioning.rollback()` + reload. Không đọc `CURRENT.json` thay cho
fingerprint engine.

## Chạy API và Web

Model local: [LOCAL_MODELS](LOCAL_MODELS.md). API một worker, loopback, không proxy header
khi không có proxy tin cậy:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  USE_OLLAMA=0 DISABLE_RERANKER=1 ITLR_REQUIRE_ARTIFACT_MANIFEST=1 \
  .venv/bin/python -m uvicorn itlr.api.server:app \
  --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
```

Database Web (chỉ với DB đích đã kiểm tra):

```bash
cd web
npm run migrate
cd ..
.venv/bin/python scripts/export_web_catalog.py
cd web
npm run seed      # upsert, không reset enrollment
npm run build
npm start         # hoặc npm run dev
```

`npm run sync` để đồng bộ catalog về sau. Exporter từ chối đích đã tồn tại để không truncate
tài liệu cộng đồng; chuẩn bị đích mới rồi merge theo quy trình duyệt.

## Refresh định kỳ

`scripts/refresh_pipeline.py` chạy crawl → build khi có thay đổi → activate sau probe;
`--no-build` chỉ crawl. Không có cờ `--real-only`, dùng `ITLR_REAL_ONLY=1`. CLI dùng pipeline
lock, refresh parent dùng refresh lock — chỉ đúng cho writer dùng cùng cơ chế khóa trên Linux
local. Bật timer/cron là hành động vận hành riêng.

## Xử lý sự cố

| Hiện tượng | Kiểm tra / hành động |
|---|---|
| `/login` 200 nhưng thao tác lỗi | `GET /ready`, credentials/schema PostgreSQL |
| API `/health` 503 | log lỗi artifacts/model; build/probe staging tin cậy, không thêm dữ liệu giả |
| `/api/personas`, `/api/for-you` 503 | `cf` trong `/health`; CF là tùy chọn |
| Admin reload 403 | `ITLR_ADMIN_TOKEN` đã đặt và header đúng; không bỏ auth |
| `/metrics` 403 | chưa đặt token thì chỉ loopback; đặt token thì phải gửi header |
| Model offline không nạp | `HF_HOME`, cache, quyền đọc; chỉ tải online có chủ đích |
| Stream dừng/citation lỗi | đọc `error`/`final`; provisional không phải đáp án; kiểm chunk id |
| Bấm khóa học bị 404 dù search thấy item | catalog Web chưa sync sau build: chạy `export_web_catalog.py --refresh`, `verify_web_catalog.py`, `npm run sync`; DB cũ không tự xóa enrollment |
| Activate lỗi sau khi đổi pointer | đọc `CURRENT.json` + history trước khi retry |
| Upload 415 | chỉ PNG/JPEG/GIF/WebP/PDF, ≤20 MB, magic bytes đúng |
| TestClient treo trong sandbox | chạy ngoài sandbox theo quyền được cấp; không skip test |

## Giới hạn

- Không hỗ trợ nhiều host: limiter/presence trong RAM, khóa file local.
- Không có transaction xuyên artifacts ↔ PostgreSQL ↔ CSV; đổi index cần maintenance window.
- Docker/HTTPS/backup/Chrome là gate riêng: xem [PRODUCTION](PRODUCTION.md) và
  [certification](../reports/FINAL_E2E_CERTIFICATION.md).
