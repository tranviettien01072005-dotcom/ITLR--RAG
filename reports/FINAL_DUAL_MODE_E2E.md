# FINAL DUAL-MODE E2E — Native vs Docker (2026-10-31)

| Mục | Giá trị |
|---|---|
| Branch / HEAD | `main` @ `e976375` + thay đổi chưa commit (observability + config fix + docs) |
| Artifacts | version `20261031-170147-14c44d161680`, manifest `d802fe44da4f30f1…`, **178 item thật** |
| Model | `qwen2.5:3b` (Ollama 0.40.13) + E5-base cache `var/hf` |
| Evidence | `reports/final-e2e-evidence/dual-mode-2026-10-31/` (native/, docker/, logs, SSE) |
| Không làm | không reset DB, không `down -v`, không commit/push, không API trả phí |

## 1. Pre-flight

- Python 3.14.4, Node 22.22.1, Docker 29.9.2/Compose v5.6.1; Ollama host có `qwen2.5:3b`;
  artifacts active 178 item; `var/data/web_items.csv` 178 row crawl thật.
- Cổng 5432/8000/11434 đang bị dịch vụ khác dùng → dùng namespace riêng:
  native API **18080**, Web **13080**, PostgreSQL **15434**; Docker API **18000**, Web **13000**, PG **55432**.
- Không có PostgreSQL server native (`pg_ctl/initdb` không tồn tại) và host PG yêu cầu mật khẩu
  không có → **Native dùng PostgreSQL 16 container** làm DB cô lập, app chạy native (ghi rõ ở §5).

## 2. MODE A — Native (app processes, không Compose)

```bash
# PostgreSQL 16 disposable (15434) + schema + sync 178 item
docker run -d --name itlr-e2e-pg -e POSTGRES_PASSWORD=... -p 127.0.0.1:15434:5432 postgres:16-bookworm
psql ... -f web/src/db/schema.sql
DATABASE_URL=... ITEMS_CSV=var/data/web_items.csv node dist/db/sync-courses.js   # Imported 178

# API native
ITLR_ARTIFACTS_DIR=$PWD/var/artifacts USE_OLLAMA=1 OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  .venv/bin/python -m uvicorn itlr.api.server:app --port 18080 --workers 1 --no-proxy-headers

# Web native
DATABASE_URL=... RECOMMENDER_URL=http://127.0.0.1:18080 PORT=13080 node dist/server.js
```

| Kiểm tra | Kết quả |
|---|---|
| `/health` | 200, `engine=ready`, **items=178**, fingerprint version đúng |
| `/api/search` "docker compose" | 200, **8 kết quả** |
| `/api/chat/stream` (Qwen host) | `sources→meta→text→final→done`, **llm_extractive**, citation **valid** |
| Web `/ready`, `/login` | 200 |
| Đăng ký tài khoản qua form (CSRF) | 302 `/dashboard` |
| `/courses/5129` / `/courses/999999` | **200 / 404** |
| `/search?q=docker` | 200 |
| Chat qua Web SSE | final + done, citation valid, **messages 0 → 2** (lưu user+assistant) |
| Hủy giữa stream (`--max-time 3`) | timeout client, **messages 2 → 2** (không lưu partial) |
| Logout → dashboard | 302 logout, dashboard 302 về login |
| Login lại | 302 `/dashboard`, dashboard 200 |
| CSRF thiếu khi POST chat | **403** |
| Admin page khi chưa admin | 302 về `/admin/login` |
| Metrics không token / Bearer | API **403 / 200**; Web **403 / 200** |

## 3. MODE B — Docker Compose full stack

```bash
docker compose --env-file .env.docker -f compose.local.yml build api
docker compose ... up -d postgres
docker compose ... run --rm --no-deps web node dist/db/migrate.js      # schema idempotent
docker compose ... run --rm --no-deps web node dist/db/sync-courses.js # Imported 178
docker compose ... -f compose.host-ollama-like models override up -d ollama api web
```

| Kiểm tra | Kết quả |
|---|---|
| Build API/Web | PASS (image `itlr-local-api`, `itlr-local-web`) |
| Migrate + sync | PASS, 178 item, enrollment giữ nguyên |
| Container | postgres/ollama/api/web healthy; `/health` 178 item |
| `/api/search` | **8 kết quả** |
| `/api/chat/stream` (Qwen container) | `llm_extractive`, citation valid, final+done |
| Web register + `/courses/5129` | 302 → dashboard; **200**; id lạ **404** |
| Web search page | 200 |
| Chat qua Web + PostgreSQL | **messages 2 → 4**, final+done |
| Hủy giữa stream | **messages 4 → 4** (không partial) |
| Restart `api web` | health 200/200, session cookie còn hiệu lực, course 200, **messages vẫn 4** |
| Stop | ports đóng, **volume giữ** (`pgdata`, `promdata`, `lokidata`, `tempodata`, …) |

## 4. AUTO-FIX — RED → GREEN

**Lỗi:** Native API `/health` **503 VersionError** dù artifacts 178 item đang active.

- **Root cause:** `ITLR_ARTIFACTS_DIR` trỏ vào root `var/artifacts` (có `CURRENT.json`) bị dùng
  trực tiếp làm thư mục artifacts; loader tìm `MANIFEST.json` ở root → fail. Docker không lộ vì
  không set biến này.
- **RED:** `tests/test_config_artifact_override.py` — override root có pointer trả sai thư mục
  (`1 failed`).
- **Fix:** `itlr/config.py` `_resolve_active_dir`: nếu override chứa `CURRENT.json` thì resolve
  version qua `versioning.current_dir`; staging phẳng (có `MANIFEST.json`, không pointer) vẫn
  dùng trực tiếp.
- **GREEN:** test PASS; Native `/health` 200/178; **cả hai mode E2E PASS**.
- Regression suite: **510 passed / 0 skip**.

## 5. Quality gates & observability

| Gate | Kết quả |
|---|---|
| Python pytest | **510 passed / 0 skip**, 76s |
| Python coverage | **4109/6019 = 68,27%** |
| Web vitest | **166 passed / 32 file**, lines **52,41%** |
| typecheck / lint / build (Web) | PASS |
| compileall / pip check | PASS |
| pip-audit / npm audit / Bandit | **0 / 0 / 0 High** |
| Monitoring profile (Prometheus/Grafana/Loki/Tempo/OTel) | **PASS** (smoke trước đó trong phiên, không re-run sau fix config-only): 5/5 target, 13 panel, 10 alert, trace `sse.chat`, Loki log, ~383 MiB |
| Latency cold prompt (CPU, trước đó) | **49,80s / 45s SLO → FAIL**; warm ~0,33s; TTFT đo qua metrics/trace |
| Human faithfulness | **NOT VERIFIED** |

Không tạo benchmark/faithfulness mới; các số là measured hoặc được ghi rõ nguồn.

## 6. Ma trận Native vs Docker

| Hạng mục | Native | Docker |
|---|---|---|
| PostgreSQL migrate/sync 178 | PASS (container DB) | PASS |
| RAG artifacts 178 + fingerprint | PASS | PASS |
| Search, chat Qwen SSE, citation | PASS | PASS |
| Web register/login, course, search | PASS | PASS (lớp logout/CSRF chỉ test native) |
| Persistence chat | PASS | PASS |
| Cancellation không lưu partial | PASS | PASS |
| Restart giữ dữ liệu | NOT VERIFIED (không restart native) | **PASS** |
| Metrics/auth | PASS | PASS (trước đó) |
| Monitoring stack | N/A (profile Docker) | PASS (trước đó) |
| Host-native PostgreSQL | **BLOCKED** (không có binary/quyền) | N/A |
| Windows 11/WSL2 | **NOT VERIFIED** | **NOT VERIFIED** |
| Host-Ollama override | N/A (host Ollama dùng trực tiếp) | **NOT VERIFIED** (đã ghi điều kiện bind 0.0.0.0; test dùng model mount) |

## 7. Rủi ro còn lại

1. Cold prompt >45s trên CPU (49,80s) — production blocker; cần hardware/GPU.
2. Human faithfulness chưa có người chấm (`null`).
3. Native mode chưa có PostgreSQL host thật (thiếu binary/quyền) — DB container isolation.
4. Docker test dùng model host mount, chưa chạy `ollama pull`; host-Ollama override chưa test
   end-to-end (chỉ config + lỗi loopback đã ghi docs).
5. Windows/WSL2 chưa chạy thật.
6. Monitoring chưa soak dài; cAdvisor privileged/promtail docker.sock là trade-off bảo mật.
7. Native restart persistence và Docker logout/CSRF chưa test chéo.

## 8. Verdict

- **LOCAL READY** — cả Native (app) và Docker full stack khởi động thật, RAG 178 item, Qwen thật,
  Web/DB/SSE/persistence/cancel hoạt động; gates xanh.
- **DEMO READY (scoped)** — demo single-host với dữ liệu thật, kèm cảnh báo cold latency ~50s,
  không SLA, không human evaluation.
- **PRODUCTION NO-GO** — cold SLO 45s và human faithfulness chưa đạt; chưa HA/Windows/soak.
