# PIPELINE AUDIT — crawl → extract → validate → dedupe → build RAG → export → PostgreSQL (2026-10-31)

| Mục | Giá trị |
|---|---|
| Branch / HEAD | `main` @ `e976375` + thay đổi chưa commit của lượt này |
| Dữ liệu | **178 item thật** (`origin=crawl:…`, id 5001–5188) từ `var/data/itlr_v2_items.csv`; build `20261031-162623-bebdbd7b459f` đã activate |
| Môi trường | PostgreSQL 16 container dùng một lần (port 15433), Web `node dist/server.js` (port 13000/13001), tài khoản test disposable |
| Không dùng | không tạo khóa học/nội dung/URL/tương tác giả; không sửa DB production; không xóa user/enrollment |

## 1. Root cause lỗi 404 khi bấm khóa học

**Nguyên nhân gốc:** sau khi build/activate index, pipeline chỉ dừng ở artifacts. Catalog CSV
`var/data/web_items.csv` chưa được refresh (exporter cũ mở file với mode `x` — no-clobber), nên
PostgreSQL Web không có row cho item mới. Search/chat lấy item từ artifacts → card trỏ
`/courses/<item_id>` (route nội bộ) → DB không có row → 404.

**Kiểm chứng thật (RED → GREEN, cùng một DB disposable):**

| Bước | Lệnh / điều kiện | Kết quả |
|---|---|---|
| Đăng ký user thật trên Web | `POST /register` (CSRF hợp lệ) | 302 `/dashboard` |
| Trước sync | `GET /courses/5129` khi DB trống | **404** |
| Sync catalog thật | `node dist/db/sync-courses.js` với `ITEMS_CSV=var/data/web_items.csv` | `Imported 178 resources; existing enrollments preserved` |
| Sau sync | `GET /courses/5129` | **200** |
| ID không tồn tại | `GET /courses/999999` | **404** (đúng) |
| DB count | `SELECT count(*) FROM courses` | **178** |
| User/enrollment | user test vẫn tồn tại sau sync | không bị xóa |

Phân biệt URL: card khóa học dùng **route nội bộ** `/courses/<item_id>`; link nguồn ngoài
(`it.link`) chỉ xuất hiện ở nút "Mở tài nguyên gốc" với `target="_blank" rel="noopener noreferrer"`.
Không có chỗ nào dùng link ngoài làm route chi tiết.

## 2. Thay đổi

| File | Thay đổi |
|---|---|
| `scripts/export_web_catalog.py` | `--refresh`: merge row crawl mới, **giữ row cộng đồng** Web append, bỏ row crawl cũ khỏi CSV (DB không xóa), ghi atomic (`.tmp` + `os.replace`); snapshot chỉ chứa row thật có `full_text`; CLI (`--source/--dest/--snapshot/--refresh`) + exit code 2 khi lỗi |
| `scripts/verify_web_catalog.py` *(mới)* | So source vs Web: `missing`, `duplicate_ids`, `stale_crawl`, `invalid_links`; exit 1 nếu thiếu/trùng/link sai |
| `scripts/audit_source_links.py` *(mới)* | Audit link nguồn: HTTP status, redirect target, robots policy, rate limit, dedupe; JSON + exit 1 khi 404/lỗi mạng |
| `scripts/refresh_pipeline.py` | Sau build thành công tự chạy export `--refresh` + verify; flag `--sync-web` chạy `npm run sync` khi có `DATABASE_URL` |
| `web/src/services/dataset.ts` | `readLastId` → **max id** (CSV merge không đảm bảo sắp xếp; id trùng sẽ upsert đè khóa học thật) |
| `tests/test_export_web_catalog.py` *(mới)* | 3 test: no-clobber mặc định, merge giữ cộng đồng/không trùng/atomic, bỏ row crawl cũ |
| `tests/test_verify_web_catalog.py` *(mới)* | 3 test: missing/link sai, duplicate/stale, bỏ qua row cộng đồng |
| `tests/test_audit_source_links.py` *(mới)* | 3 test: 404/redirect/dedupe, robots chặn không fetch, lỗi transport |
| `web/src/services/dataset.test.ts` | +1 test: cấp id theo max khi CSV không sắp xếp |

Không đổi: schema DB, API, business rules, retrieval/ranking/prompt/model, dữ liệu thật,
enrollment. Không xóa file.

## 3. Audit pipeline theo từng tầng

| Tầng | Kết quả / bằng chứng |
|---|---|
| Crawl | `itlr/collect/http.py`: robots fail-closed (RFC 9309), Crawl-delay, rate limit theo host + jitter, retry 429/5xx, chặn đích private/credential. Dữ liệu thật hiện có 178 item crawl |
| Extract / validate | `extract.py` + `quality.py` (độ dài, boilerplate, `passes_quality`); không sửa/không bịa nội dung |
| Deduplicate | `content_key` + `normalize_url`; runner skip theo recheck window và near-dup title 0,80. Lượt này **không crawl lại**; dedupe được kiểm bằng test hiện có và audit dedupe link |
| Provenance | export giữ `origin`, `crawl_license`, `crawl_lang`, `crawl_hash`, `source_*`; kiểm 178/178 row có `origin=crawl:`; không có row synthetic |
| Build RAG | version `20261031-162623-bebdbd7b459f`, probe ok, activated |
| Export | `--refresh` → 178 row; snapshot tạm `/tmp/…` để không sửa snapshot repo |
| Verify | `ok:true`, `missing:[], duplicate_ids:[], invalid_links:[]` |
| Sync PostgreSQL | 178 row; upsert, enrollment/user giữ nguyên |
| HTTP/redirect/canonical | Audit mẫu 6 link MDN: 6×200, 0 transport error, 0 robots denied; redirect chỉ khác trailing slash và đã được `normalize_url` coi là cùng URL |
| 404 detection | Audit script đánh dấu `missing`; verify script phát hiện item RAG thiếu row Web |

## 4. Quality gates (chạy mới)

| Gate | Kết quả | Trạng thái |
|---|---|---|
| Python pytest | **503 passed / 0 skip**, 66,3s | PASS |
| Python coverage | **3949/5839 = 67,63%** | PASS |
| compileall / pip check | PASS | PASS |
| Web vitest | **163 passed / 30 file** | PASS |
| Web coverage | lines **725/1409 = 51,45%**; statements 48,31% | PASS |
| typecheck / lint / build | PASS | PASS |
| pip-audit / npm audit / Bandit | 0 / 0 / 0 High | PASS |
| Secret scan / `git diff --check` | 0 hit / PASS | PASS |
| Ghi chú flake | Lượt full-suite đầu có 2 test CLI `build_all_v2 --dry-run` timeout 120s dưới tải; chạy riêng **2 passed 0,15s** và full-suite lần 2 **503 passed**. Không sửa test/không nới timeout | PASS (rerun) |

## 5. Giới hạn chưa xác minh

- **Không crawl lại diện rộng** (theo quy tắc phiên): 178 item là dữ liệu thật đã có; robots/
  rate/dedupe được xác minh bằng code + test, không phải bằng lượt crawl mới.
- Audit link mới chạy **mẫu 6 link** (cùng host MDN); 172 link còn lại chưa audit đầy đủ vì phụ
  thuộc mạng và rate limit. Dùng `scripts/audit_source_links.py` (không `--limit`) trên máy có
  mạng để hoàn tất.
- Chưa kiểm trên PostgreSQL production; DB dùng một lần đã xóa, không có dữ liệu thật bị thay đổi.
- Canonical mới chuẩn hóa theo `normalize_url` (scheme/host/path/trailing slash); chưa xử lý
  mọi biến thể canonical do site khai báo (`<link rel=canonical>`) — ngoài phạm vi audit link.
- `--sync-web` trong refresh pipeline chưa chạy tự động trong cron; cần `DATABASE_URL` và quyết
  định vận hành (đã ghi trong DEPLOY).
- Pipeline không có transaction xuyên artifacts ↔ PostgreSQL; release vẫn cần maintenance window.

## 6. Verdict

- **Pipeline completeness: PASS scoped** — lỗi 404 đã sửa tận gốc (export refresh + verify +
  sync), có regression test và kiểm chứng thật 404 → 200 trên dữ liệu 178 item.
- **PRODUCTION: NO-GO** — không thay đổi: cold SLO 45s = 49,80s trên CPU hiện tại và human
  faithfulness chưa có người chấm.
