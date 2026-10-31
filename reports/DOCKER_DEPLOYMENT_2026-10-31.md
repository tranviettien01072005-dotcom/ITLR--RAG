# DOCKER DEPLOYMENT VERIFICATION — ITLR–RAG (2026-10-31)

| Mục | Giá trị |
|---|---|
| Branch / HEAD | `main` @ `e976375` + thay đổi chưa commit (Docker/docs) |
| Mục tiêu | Full stack local bằng Docker Compose: Web + FastAPI RAG + PostgreSQL 16 + Ollama/Qwen2.5:3b |
| Dữ liệu test | **178 item thật** trong `var/artifacts` (version `20261031-170147-14c44d161680`) và `var/data/web_items.csv`; E5 cache `var/hf` |
| Môi trường | Docker 29.9.2, Compose v2, host i7-8650U/14 GiB; cổng host 5432/8000/3000/11434 đã bị service khác chiếm → test dùng 55432/18000/13000/11534 |
| Evidence | `reports/final-e2e-evidence/docker-local-2026-10-31/` |

## 1. Thay đổi

| File | Nội dung |
|---|---|
| `compose.local.yml` *(mới)* | Full stack HTTP: `postgres` (volume + healthcheck), `ollama` 0.40.13 (volume + healthcheck), `api` (build root Dockerfile, mount `./var`, healthcheck), `web` (build `./web`, mount `./var/data`, healthcheck, depends PG+API healthy). Cổng chỉ bind `127.0.0.1`, đổi được qua `*_PORT`. |
| `compose.host-ollama.yml` *(mới)* | Override dùng Ollama trên host qua `host.docker.internal` + `host-gateway`; ghi rõ phải bind `0.0.0.0` |
| `.env.docker.example` *(mới)* | Một file cấu hình cho stack local; `POSTGRES_PASSWORD` hex để không phải URL-encode; placeholder cho JWT/ADMIN/token |
| `Dockerfile` | Cài `torch==2.15.0+cpu` trước `requirements.txt` để image CPU không kéo wheel CUDA (giảm dung lượng đáng kể) |
| `.gitignore` | Bỏ qua `.env.docker` |
| `README.md` | Mục **Docker Compose (full stack)**: Quick Start, cấu hình, Ollama container/host, dữ liệu & index, migrate/sync, health, cập nhật, backup/restore, stop/restart, troubleshooting 11 mục |
| `deploy/DEPLOY.md`, `docker-compose.yml` | Trỏ tới `compose.local.yml`; ghi rõ root compose chỉ là API + refresh (legacy) |

Không đổi logic nghiệp vụ, schema, RAG, API. Không secret thật trong repo.

## 2. Kiểm chứng thật

| Bước | Lệnh / điều kiện | Kết quả |
|---|---|---|
| Compose config | `docker compose --env-file .env.docker -f compose.local.yml config --quiet` | PASS |
| Build | `... build` | **PASS** — `itlr-local-api:latest`, `itlr-local-web:latest` |
| DB up | `... up -d postgres` | healthy |
| Migration | `run --rm --no-deps web node dist/db/migrate.js` | `schema.sql` applied (idempotent) |
| Sync catalog | `run --rm --no-deps web node dist/db/sync-courses.js` | `Imported 178 resources; existing enrollments preserved` |
| API up | `up -d --no-deps api` | healthy; `/health` → `engine=ready`, **items=178**, fingerprint `20261031-170147…` |
| Search | `POST /api/search` "docker volumes" | **8 hits**, first `5003` |
| Chat SSE (Qwen container) | `POST /api/chat/stream` (UUID question) | events `sources→meta→text→final→done`, `generation_mode=llm_extractive`, `citation_validation.status=valid`, 5 sources |
| Web | `up -d --no-deps web` | `/ready` 200; `/login` 200; register 302 `/dashboard`; `/courses/5129` **200**; `/courses/999999` **404** |
| Container states | `ps` | postgres/api/ollama/web đều **healthy** |
| Shutdown | `stop --timeout 45` | ports 13000/18000/55432 đóng; volume `itlr-local_pgdata`, `itlr-local_ollama_models` giữ nguyên |
| Regression | pytest + vitest | **503 Python PASS**, **163 Web PASS** |

## 3. Lỗi gặp và cách xử lý (đã ghi vào README)

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `failed to bind host port 127.0.0.1:5432` | PostgreSQL/service khác đang dùng cổng | đổi `POSTGRES_PORT` (test dùng 55432); tương tự `API_PORT`, `WEB_PORT`, `OLLAMA_PORT` |
| Container API không gọi được Ollama host | Ollama mặc định bind `127.0.0.1`, container không tới được | chạy `OLLAMA_HOST=0.0.0.0:11434 ollama serve`, hoặc dùng Ollama trong Compose (mặc định) — đã ghi trong README và `compose.host-ollama.yml` |
| Port 11434 bị chiếm khi vừa chạy host Ollama vừa chạy container | cả hai cùng publish 11434 | chỉ chọn một nhánh; nếu cần cả hai, dùng override `ports: !override` hoặc tắt publish |
| `npm run migrate/sync` trong container lỗi | runtime image không có `tsx` | dùng `node dist/db/migrate.js` / `node dist/db/sync-courses.js` (đã ghi trong README) |

## 4. Giới hạn chưa xác minh

- **`ollama pull qwen2.5:3b`** (đường tải model mới trong container) **chưa chạy** vì mạng/dung
  lượng; test dùng model có sẵn trên host mount read-only vào container. Lệnh đã có trong README.
- TLS/Caddy/ACME production không chạy lại trong lượt này (đã có evidence staging §11.3).
- Host-Ollama override: đã xác minh cấu hình merge và lỗi bind loopback; chưa chạy với daemon
  host bind `0.0.0.0` (không được phép restart daemon chia sẻ của người dùng).
- Không test trên máy trắng (image E5 tải lần đầu từ HF); dùng cache `var/hf` sẵn có.
- Không chạy crawl mới (giữ quy tắc không crawl diện rộng); artifacts/catalog là dữ liệu thật đã có.

## 5. Verdict

- **Docker local full stack: PASS scoped** — build, migrate, sync 178 item thật, health 178 item,
  search, chat Qwen `llm_extractive` + citation valid, Web register/course 200/404, shutdown giữ volume.
- **Production: NO-GO** — không đổi: cold SLO 45s (49,80s) và human faithfulness chưa có.
