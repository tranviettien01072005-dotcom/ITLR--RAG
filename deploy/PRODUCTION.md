# Single-host deployment runbook

Thiết kế cho **một host Linux** với Caddy → Web → API/PostgreSQL, local filesystem, một
worker/replica mỗi service. Không phải thiết kế Cloud Run/multi-host: khóa artifacts, SQLite
và limiter trong RAM đều giả định một tiến trình.

## 1. Trạng thái kiểm chứng

| Hạng mục | Trạng thái |
|---|---|
| Compose single-host cô lập (Caddy TLS nội bộ, PG16, E5, Qwen, Chrome 11/11, backup/restore, tamper, reload/rollback, restart) | **PASS scoped** — [certification §11](../reports/FINAL_E2E_CERTIFICATION.md) |
| Public DNS + ACME thật, cloud provisioning | **NOT VERIFIED** |
| Multi-host/HA, soak dài, capacity | **NOT VERIFIED** |
| SLO 45s với Qwen trên CPU | **FAIL** (prefill 40–51s; §12) |
| Production data migration | **BLOCKED** — chưa thực hiện, không nằm trong phạm vi |

Staging PASS không phải production-ready. **Verdict hiện hành: NO-GO production** — không
promote khi các gate dưới còn mở.

## 2. Điều kiện

- Host Linux riêng, Docker Engine + Compose v2, DNS trỏ về host, TCP 80/443 (và UDP 443 nếu
  muốn HTTP/3). Giới hạn SSH cho quản trị.
- Không expose 3000/8000/5432. Không dùng chung database với môi trường khác.
- Artifacts đã build/probe và model cache offline (`var/hf`), không rebuild/activate dữ liệu
  thật chỉ để thử template.

## 3. Cấu hình

Sao chép từng `deploy/*.env.example` thành `deploy/{compose,postgres,web,api}.env`, quyền
`600`, giá trị ngẫu nhiên riêng. Mật khẩu trong `DATABASE_URL` phải khớp `postgres.env` và
được URL-encode. `POSTGRES_*` chỉ khởi tạo volume rỗng — đổi không có nghĩa là rotate mật
khẩu DB đang chạy. Đặt `SITE_DOMAIN` và `APP_ORIGIN` nhất quán (HTTPS). Dùng image tag bất
biến; ghim digest cho release có kiểm soát.

```bash
dc() { docker compose --env-file deploy/compose.env -f compose.production.yml "$@"; }
dc config --quiet          # luôn dùng --quiet để không in credential
dc build api web
dc up -d postgres
dc run --rm --no-deps web node dist/db/migrate.js
dc run --rm --no-deps web node dist/db/sync-courses.js
dc up -d api web proxy
dc ps
```

Migration/sync là **job release tường minh**; restart Web không tự chạy. Chuẩn bị CSV bằng
`scripts/export_web_catalog.py` trước khi sync (upsert, không xóa enrollment).

Ghi chú quyền: Web chạy UID 1000, cần đọc `var/data` và CSV; API image hiện chạy bằng user
mặc định của base image (root) và mount `./var` read-write — hạ quyền API/volume là
hardening gate chưa hoàn tất.

## 4. Kiểm tra sau khi dựng

```bash
dc ps
dc logs --since 15m --tail 200 api web proxy
curl --fail https://$SITE_DOMAIN/health
curl --fail https://$SITE_DOMAIN/ready
dc exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8).status)"
```

- Web `/health` = liveness; `/ready` = PostgreSQL. Không chứng minh RAG readiness.
- API `/health` trả `engine`, `items`, `cf`, `artifacts{version,manifest_sha256}`; fingerprint
  chỉ đổi sau reload thành công. So với release manifest đã duyệt, không đọc `CURRENT.json`
  thay thế.
- Kiểm HTTPS, cookie `Secure`, CSRF, client IP sau proxy và SSE qua endpoint công khai trước
  khi promote.

## 5. Quan sát

Theo dõi: dung lượng đĩa, RAM/OOM, restart container, DB availability, API health, tỉ lệ 5xx
và latency. `/metrics` (API) trả đếm request + latency TB/max theo route (đòi
`X-Admin-Token` nếu đã cấu hình). Không có alert external được cấu hình.

Không log body chat, nội dung tệp hay secret. Web SIGTERM drain kết nối tối đa ~20s, đóng SSE
còn lại rồi drain pool DB; hard deadline 25s, Compose cho 30s.

## 6. Backup và phục hồi

Dừng Web và mọi job ghi (crawler/refresh) trong cửa sổ backup; API có thể tiếp tục đọc
artifacts active.

```bash
umask 077
mkdir -p deploy/backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dc exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > deploy/backups/db-$stamp.dump
tar -czf deploy/backups/var-$stamp.tgz var
sha256sum deploy/backups/db-$stamp.dump deploy/backups/var-$stamp.tgz > deploy/backups/$stamp.sha256
```

Kiểm exit code từng lệnh; ghi image tag + version artifacts. Restore **trên instance staging
riêng** trước: xác minh hash/path, `pg_restore` vào database mới, trỏ Web staging vào đó rồi
kiểm account/progress/catalog. Không chạy `pg_restore --clean`, không ghi đè `var` đang chạy,
không `docker compose down -v`. Backup/restore 15 bảng đã drill trong staging (§11.3); restore
trên VM thật chưa thực hiện.

## 7. Release và rollback

Giữ image tag cũ, cặp backup DB/var và version artifacts trước đó. Đổi index/catalog cần
maintenance window: stop Web → build/probe/activate → reload/restart API → export + sync CSV
→ start Web → kiểm provenance. Không có transaction xuyên dịch vụ; bước lỗi thì giữ Web dừng
và phục hồi cặp khớp trước khi nhận traffic.

- Rollback code: đổi `API_IMAGE`/`WEB_IMAGE` về tag cũ rồi recreate. Rollback artifacts:
  `versioning.rollback()` + reload. Rollback code **không** hoàn tác schema/dữ liệu — phải
  restore backup đã test.
- Trước khi promote: Docker build, restore drill, luồng PostgreSQL thật, browser/SSE, chất
  lượng RAG và đo tải phải PASS trên staging Linux.

## 8. Xử lý sự cố

| Hiện tượng | Hành động |
|---|---|
| Caddy không cấp cert | DNS/port 80/443, log Caddy; staging nội bộ dùng CA nội bộ + trust tường minh |
| Web 502/503 | `dc ps`, log web; `/ready` DB; API health |
| API 503 | thiếu artifacts/model; xem log, không thêm dữ liệu giả |
| SSE cắt giữa stream | kiểm provider/timeout; final không có `done` không được lưu |
| Reload 403 | token/header; không tắt auth |
| Reload 503 | artifacts/manifest lỗi; engine cũ vẫn phục vụ |
| Restart mất dữ liệu | kiểm volume `postgres_data`; không `down -v` |
| 429 hàng loạt | limiter/IP sau proxy; khai `TRUSTED_PROXIES` đúng, không tắt limiter production |
| Container bị OOM | giới hạn mem Compose, kích thước model/context, hardware |

## 9. Gate mở trước production

1. SLO 45s: phần cứng đạt prefill ≥65–70 tok/s + chạy lại frozen/cold-warm.
2. Human faithfulness/entailment (`null`) và đánh giá refusal.
3. Soak dài, cold concurrency >1, queue depth, multi-host/HA.
4. Hardening API non-root, quyền volume tối thiểu, secret rotation.
5. Public DNS/ACME + restore drill trên VM thật.
