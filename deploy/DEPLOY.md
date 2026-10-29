# DEPLOY — ITLR-RAG V2 (API + crawler + index theo phiên bản)

Hệ thống gồm 2 phần chạy độc lập về thời gian:

1. **API server** (uvicorn/FastAPI): nạp artifacts *đã kích hoạt* — asyncio-free, CPU.
2. **Refresh pipeline** (dữ liệu): crawl → catalog → build staging → probe → activate.
   Chạy bằng cron/systemd timer/`docker compose run`. Không bao giờ đụng vào artifacts
   đang phục vụ API trước khi qua probe.

Sơ đồ tổng thể xem `README.md` §Kiến trúc. File tổng kết tự động:
`var/data/collect/last_run.json` (crawl), `var/data/last_build.json` (build),
`var/data/collect/last_refresh.json` (refresh) — dùng cho giám sát/cảnh báo.

---

## 1. Máy chủ (không Docker)

### 1.1. Cài đặt

```bash
python3 -m venv .venv             # Python ≥ 3.11
.venv/bin/pip install -r requirements.txt

cp .env.example .env              # điền DEEPSEEK_API_KEY (hoặc dùng Ollama)
# sinh token quản trị — bắt buộc nếu muốn /admin/reload:
# python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Lần chạy đầu cần internet để tải model HF (E5 + reranker):

```bash
.venv/bin/python scripts/refresh_pipeline.py --online --force-build
# sau đó mọi lượt sau chạy offline (model đã cache):
.venv/bin/python scripts/refresh_pipeline.py
```

### 1.2. Chạy API

```bash
HROOT=$(pwd)
set -a; . ./.env; set +a        # nạp env (ẩn file .env: chmod 600 .env)
.venv/bin/uvicorn itlr.api.server:app --host 0.0.0.0 --port 8000
```

Kiểm tra: `curl -s localhost:8000/health`
→ `{"status":"ok","engine":"ready","cf":true|false,"items":N}` (`cf:false` = CF chưa
build — tùy chọn V2, search/chatbot vẫn chạy; `/api/personas`, `/api/for-you` trả 503).

### systemd (API)

`/etc/systemd/system/itlr-api.service`:

```ini
[Unit]
Description=ITLR-RAG API (FastAPI/uvicorn)
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
WorkingDirectory=/opt/itlr-rag
EnvironmentFile=/opt/itlr-rag/.env
ExecStart=/opt/itlr-rag/.venv/bin/uvicorn itlr.api.server:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10
# Model nạp ~1-2 phút (CPU) — không KillMode quá sớm
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now itlr-api
```

### 1.3. Refresh định kỳ

**cron** (crontab -e):

```cron
# 04:00 mỗi ngày: crawl + build + probe + activate (env qua file)
0 4 * * *  cd /opt/itlr-rag && bin/refresh_env.sh >> var/log/refresh.cron.log 2>&1
```

`bin/refresh_env.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
exec .venv/bin/python scripts/refresh_pipeline.py
```

**systemd timer** (thay thế cron):

```ini
# /etc/systemd/system/itlr-refresh.service   (Type=oneshot)
[Unit]
Description=ITLR-RAG refresh (crawl + build V2)
[Service]
Type=oneshot
WorkingDirectory=/opt/itlr-rag
EnvironmentFile=/opt/itlr-rag/.env
ExecStart=/opt/itlr-rag/.venv/bin/python scripts/refresh_pipeline.py
TimeoutStartSec=24h

# /etc/systemd/system/itlr-refresh.timer
[Unit]
Description=Chạy itlr-refresh mỗi ngày 04:00
[Timer]
OnCalendar=*-*-* 04:00:00
Persistent=true
RandomizedDelaySec=900
[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now itlr-refresh.timer
```

Refresh pipeline tự an toàn: **tất cả nguồn lỗi ⇒ không build**; build fail/probe fail
⇒ **không activate** (index đang sống không đổi) — xem §1.5.

---

## 2. Docker

```bash
docker compose up -d                # API trên :8000, mount ./var từ host
docker compose api ps               # healthcheck: start-period 5 phút (model nạp CPU)
```

Build refresh job trong container:

```bash
docker compose run --rm refresh     # crawl + build (--force-build định sẵn trong compose)
# lần đầu, model chưa cache:
docker compose run --rm refresh python scripts/refresh_pipeline.py --force-build --online
```

Ghi chú:
- Volume `./var` chứa **artifact theo phiên bản** + SQLite + HF cache — sao chép
  `./var` để backup. Không chạy API và refresh trong CÙNG container: model nạp RAM
  lớn, dễ gây OOM khi cùng chạy — dùng service `refresh` riêng (như trên).
- File `.env` bên trong container được nạp qua `env_file`; `ITLR_ADMIN_TOKEN` từ host.

---

## 3. Vận hành index theo phiên bản

Cấu trúc `var/artifacts/`:

```
CURRENT.json                     # con trỏ: {version, dir} — đọc lại mỗi lần nạp engine
CURRENT.json.history.json        # nhật ký activate/rollback
versions/<YYYYMMDD-HHMMSS>/      # artifacts đầy đủ + MANIFEST.json (probe ok/fail)
```

- **Kích hoạt**: chỉ phiên bản có manifest `probe: ok` mới được `activate()`.
  Con trỏ ghi nguyên tử (tmp + rename). Engine (`itlr.config.current_dir()`) cố định
  thư mục active trong toàn bộ một lần load để không trộn hai phiên bản.
- **Rollback** (quay về phiên bản activate liền trước):

  ```bash
  .venv/bin/python -c 'from itlr import versioning; print(versioning.rollback())'
  sudo systemctl restart itlr-api   # (hoặc POST /admin/reload với X-Admin-Token)
  ```

- **Reload nóng** (không restart tiến trình):

  ```bash
  export ITLR_ADMIN_TOKEN=<token trong .env>
  curl -X POST localhost:8000/admin/reload -H "X-Admin-Token: $ITLR_ADMIN_TOKEN"
  # {ok: true, reloaded: true, items: N, cf: true}
  ```

  Config nào `ITLR_ADMIN_TOKEN` trống/bỏ đặt ⇒ endpoint trả 403 (admin API tắt).
- **GC**: `garbage_collect(keep=3)` — giữ 3 phiên bản gần nhất sau mỗi build thành công.

## 4. Kiểm tra sau deploy

```bash
curl -s localhost:8000/health                        # engine ready + cf + number of items
curl -s localhost:8000/metrics | head                # request/latency-lite
curl -s localhost:8000/api/suggested                # prompts gợi ý chatbot sẵn sàng
cat var/data/collect/last_run.json                  # lượt crawl cuối (totals, by_source)
cat var/data/last_build.json                        # phiên bản đã activate + steps + probe
```

Kiểm thử nhanh hồi quy:

```bash
.venv/bin/python -m pytest tests/ -q            # kết quả phiên hiện tại: reports/FINAL_REMEDIATION.md
```

## 5. Giám sát & cảnh báo (gợi ý tối thiểu)

| Tín hiệu | Đọc ở | Điều kiện cảnh báo |
|----------|-------|--------------------|
| Crawl lỗi toàn nguồn | `/health` 503 + last_run.json | last_refresh.json `crawl_rc` ≠ 0 |
| Build/probe fail | last_refresh.json `build_rc` | ≠ 0 (index vẫn hoạt động phiên bản cũ) |
| API chết | systemd/healthcheck + `/health` | không 200 |
| Độ trễ cao | `/metrics` | route_latency_ms_* vượt SLO của bạn |

## 6. An toàn & giấy phép

- `.env` chmod 600, nằm ngoài git (`.gitignore`). Token quản trị dùng random ≥ 32 bytes.
- Crawler tôn trọng robots.txt + rate limit + User-Agent minh bạch
  (`ITLR-RAG/2.0; academic-research-crawler`).
- Nguồn mặc định đều ghi rõ license trong `configs/collect.sources.json`
  (dev.to API full-text; freeCodeCamp News & MDN Blog: CC BY-SA — snippet-only với
  VnExpress vì chưa có giấy phép mở; mỗi doc lưu `origin`, `crawl_license`, `crawl_lang`).
- Dữ liệu tương tác CF (nếu bật --with-cf) là **giả lập seed 7** — ghi rõ ở ADR-005;
  tuyệt đối không dùng làm dữ liệu thật cho báo cáo đánh giá.

## 7. Security remediation (2026-10-29)

Chưa đủ bằng chứng production-ready: xem `reports/FINAL_REMEDIATION.md`.
API chỉ một worker và một replica (limiter trong RAM). Docker bind host loopback;
command mặc định `--workers 1 --no-proxy-headers`. Nếu cần IP client qua proxy,
chỉ dùng `--proxy-headers --forwarded-allow-ips=<IP proxy thực>` và proxy phải ghi đè
forwarding headers. Không dùng `*`. Web dùng `TRUSTED_PROXIES` với CIDR thực.

Production đặt `ITLR_REQUIRE_ARTIFACT_MANIFEST=1`. Build/probe phải do builder tin cậy;
mount artifacts read-only cho API. Hash SHA256 phát hiện file thay đổi, không thay thế
chữ ký hay quyền filesystem. Manifest cũ thiếu inventory phải trusted re-probe trước activate.
`/live` là liveness; `/health` là readiness engine, trả 503 khi chưa build.

Web riêng: Node 22+, PostgreSQL; `cd web`, `npm ci`, cấu hình `web/.env` từ mẫu
với JWT/admin/DB credentials riêng, `npm run migrate`, `npm run build`, `npm start`.
`/health` kiểm tra process; `/ready` kiểm tra PostgreSQL. Không public upload documents
trước khi xác minh scanning/isolation và các giới hạn ghi trong `web/SECURITY_REMEDIATION.md`.

Kiểm chứng trước release: `python -m pytest tests/`, `cd web && npm run typecheck &&
npm run lint && npm test && npm run build && npm audit --audit-level=high`;
`python -m pip_audit` và `python -m bandit -r itlr scripts -lll`.
CI có gates nhưng một workflow chưa chạy trên GitHub không phải bằng chứng CI xanh.

### Crawler inventory policy (audit 2026-10-29)

Sources default to `listing_is_complete: false`. Use this for rolling RSS feeds,
API pages and news listings: absent URLs remain active. Set the JSON boolean
`listing_is_complete: true` only for an authoritative complete inventory where
absence proves removal. Both this flag and `full_text_allowed` require JSON
booleans, not strings or integers. Existing records already marked missing need
separate URL verification before restoration. Serialize refresh jobs; overlapping
build/version history writes have not been verified safe.

### V3 shared retrieval and lifecycle state (2026-10-30)

A rebuilt version containing `chunk_embeddings.pkl` uses the shared chunk retrieval
service for search, chatbot semantic retrieval and off-topic scoring. Old versions
remain readable and use V2 retrieval. V3 generated output requires selected chunk
citations; identity validation does not prove semantic faithfulness. Calibrate the
cosine threshold on real off-topic queries before release.

New transitions embed history inside CURRENT.json, with file/directory fsync.
The separate history JSON is a compatibility mirror. After a process interruption,
inspect CURRENT.json as the authoritative committed state before retrying; the
pointer may be committed even if updating the compatibility mirror failed.
Rollback reads embedded history. Do not edit history independently. Local Linux
filesystem behavior is tested; multi-host/network storage is not supported by
these tests. No existing version needs a data migration or destructive rebuild.
