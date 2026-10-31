# HTTP API và route Web

Hai bề mặt HTTP: **API Python** (FastAPI, cổng 8000) và **Web** (Express, cổng 3000).
Web gọi API qua HTTP nội bộ; client cuối chỉ nên đi qua Web/Caddy.

## 1. API Python (`itlr/api/server.py`)

Base URL local: `http://127.0.0.1:8000`. OpenAPI: `/docs`, `/openapi.json`.
Một worker (`--workers 1`); rate limit lưu trong RAM theo IP.

### Endpoint

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | `/live` | — | liveness, luôn `{"status":"ok"}` |
| GET | `/health` | — | readiness: engine đã nạp artifacts, số items, CF, fingerprint |
| GET | `/metrics` | token nếu có cấu hình, ngược lại chỉ loopback | Prometheus text: đếm request, latency TB/max theo route |
| POST | `/api/search` | rate `SEARCH` (120/phút mặc định) | tìm kiếm lai |
| POST | `/api/chat` | rate `CHAT` (30/phút) | chat non-stream (sync) |
| POST | `/api/chat/stream` | rate `CHAT` | chat SSE |
| POST | `/admin/reload` | `X-Admin-Token` + rate `ADMIN` (10/phút) | nạp lại artifacts sau activate |
| GET | `/api/personas` | — | danh sách persona; 503 nếu thiếu CF model |
| POST | `/api/for-you` | — | gợi ý theo persona; 503 nếu thiếu CF model |
| GET | `/api/suggested` | — | gợi ý catalog |
| GET | `/` | — | thông tin/health rút gọn cho UI tĩnh phụ |

Rate limit đọc lại mỗi request: `ITLR_RATE_SEARCH_PER_MIN`, `ITLR_RATE_CHAT_PER_MIN`,
`ITLR_RATE_ADMIN_PER_MIN` (`0` = tắt bucket đó). Vượt ngưỡng → `429` + `Retry-After`.
Client IP lấy từ kết nối trực tiếp; chỉ tin forwarding header khi proxy được khai báo.

### Request/response

**`POST /api/search`**

```json
{"query": "docker volumes", "type": "Tài liệu", "min_pct": 84}
```

- `query`: 1–500 ký tự; `type`: `"Khóa học" | "Tài liệu"` (giá trị khác bị bỏ qua);
  `min_pct`: 0–100, mặc định 84.
- Trả `{"results":[{"item_id","title","type","category","description","topics",
  "instructor","platform","link","origin","crawl_license","crawl_lang","crawl_hash",
  "source_updated_at","source_fetched_at","level","score","chunk_id","excerpt"}]}`.

**`POST /api/chat`** — `{"message": "...", "history": [{"role":"user","content":"..."}]}`;
`message` ≤2000 ký tự, tối đa 20 lượt history, mỗi content ≤4000 ký tự. Trả JSON kết quả
chat (`response`, `intent`, `sources`, `recommendations`, `generation_mode`,
`citation_validation`, …). Lỗi tầng chatbot/LLM → `503` với `intent="error"`.

**`POST /api/chat/stream`** — cùng body; trả `text/event-stream`, mỗi frame:

```
data: {"type":"sources","sources":[...]}

data: {"type":"meta","intent":"...","generation_mode":"llm_extractive"}

data: {"type":"final","response":"...","sources":[...],"citation_validation":{...}}

data: {"type":"done"}
```

- `text` (nếu có) là **provisional**; chỉ `final` là kết quả đã qua xử lý.
- `done` chỉ đóng stream, không chứng minh thành công; lỗi giữa stream phát frame
  `{"type":"error",...}` rồi `final` mode `error` và `done`.
- Citation: `final.citation_validation.status` (`valid|missing|invalid`) và
  `evidence_binding` (`verbatim` ở chế độ `llm_extractive`).

**`POST /admin/reload`** — header `X-Admin-Token` phải khớp `ITLR_ADMIN_TOKEN`; env rỗng
⇒ endpoint tắt (403). Trả fingerprint mới. Reload nạp engine trước khi swap; lỗi giữ engine cũ.

**`GET /health`** ví dụ:

```json
{"status":"ok","engine":"ready","cf":false,"items":118,
 "artifacts":{"version":"docker-a","manifest_sha256":"29098b37…"}}
```

`artifacts` chỉ đổi sau reload thành công; đây là fingerprint của engine đang phục vụ,
không phải nội dung `CURRENT.json`. Thiếu artifacts/model → `503`.

## 2. Web (`web/src/`)

Base URL local: `http://localhost:3000`.

### Health

| Path | Ý nghĩa |
|---|---|
| `GET /health` | liveness process |
| `GET /ready` | kiểm PostgreSQL; không chứng minh RAG readiness |

### Xác thực và CSRF

- Đăng nhập đặt cookie JWT tên `token` (`HttpOnly`, `SameSite=Lax`, `Secure` khi
  `NODE_ENV=production`). Không có API token dạng bearer cho trình duyệt.
- Cookie `csrf` (không HttpOnly) sinh theo phiên; request ghi phải gửi lại giá trị qua
  header `x-csrf-token` hoặc field `_csrf`. Thiếu/sai → 403.
- Giới hạn: 300 request/phút/IP toàn cục; 20 lần/phút/15 phút cho login/register/reset
  (bỏ qua request thành công).

### Nhóm route

| Nhóm | Ví dụ |
|---|---|
| Auth | `GET/POST /login`, `/register`, `/forgot`, `/reset/:token`, `/account`, `POST /logout` |
| Trang | `/`, `/search`, `/courses/:id`, `/dashboard`, `/blog`, `/chat`, `/learning` |
| Học tập | `POST /api/learning/diagnostic`, `POST /api/learning/progress` |
| Chat | `POST /api/chat`, `POST /api/chat/stream` (SSE), `GET /api/conversations`, `DELETE /api/conversations/:id` |
| Tài liệu | `POST /api/courses/:id/attachments`, `GET /api/download/:id`, `GET /api/attachment/:id/text`, `DELETE /api/attachments/:id` |
| Cộng đồng | `POST /api/posts/:id/like`, `POST /api/posts/:id/comments`, `POST /api/friends/request`, `GET /api/messages/:userId` |
| Quản trị | `/admin/login`, `/admin/`, `GET /admin/pending`, `POST /admin/lessons/:id/approve`, `POST /admin/user/:id/role` |

Upload: chỉ nhận ảnh raster (PNG/JPEG/GIF/WebP) hoặc PDF, có kiểm chữ ký và kích thước
(≤20 MB tổng); nội dung lạ bị từ chối `415` và buffer bị zero. Đây là kiểm tra định dạng,
không phải antivirus.

### Contract SSE ở Web

Web chuyển tiếp stream của API và **chỉ lưu final** khi nhận đủ `final` + `done` và EOF
sạch. Event đến sau `done`, stream bị cắt hoặc final thiếu `done` không được coi là hoàn
tất; partial/provisional không được lưu thành câu trả lời.

## 3. Giới hạn chung

- Một worker/replica mỗi service: limiter, presence và khóa artifacts đều trong process
  hoặc file local. Không scale ngang nếu chưa thay cơ chế.
- Không có CORS mở; Web gọi API qua mạng nội bộ. Nếu tách host, cần TLS và proxy tin cậy
  tường minh ([PRODUCTION](../deploy/PRODUCTION.md)).
- Không log body chat, cookie, token hay nội dung tệp.
