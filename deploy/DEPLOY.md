# Cài đặt và vận hành ITLR–RAG

For the complete HTTPS/Web/API/PostgreSQL stack use [the production runbook](PRODUCTION.md) and `compose.production.yml`. The original `docker-compose.yml` remains API/refresh only. Web restarts no longer run migration or catalog sync automatically.

Hướng dẫn cho **ITLR–RAG | Intelligent IT Learning Platform**, cập nhật 2026-10-30. Phạm vi hỗ trợ hiện tại là Linux local, một worker/replica mỗi service và các tiến trình ghi hợp tác qua khóa file. [Validation](../reports/VALIDATION.md) ghi các bước đã thực thi; các cấu hình container chưa được xác nhận bằng một lượt Docker/Compose thực tế.

## Thành phần và điều kiện

| Thành phần | Địa chỉ local | Yêu cầu |
|---|---|---|
| Giao diện chính Express/TypeScript/EJS | `http://localhost:3000` | Node.js 22, PostgreSQL |
| API Python/FastAPI | `http://127.0.0.1:8000` | Python ≥3.11, artifacts và model cache |
| PostgreSQL | Theo `DATABASE_URL` | Database và credentials riêng |
| Ollama tùy chọn | `http://127.0.0.1:11434` | Model generation local |

Một checkout mới chưa chắc có `var/`, model hoặc database. Không suy ra readiness từ việc trang login render được. Chuẩn bị dung lượng cho model và các version artifacts; chưa có mức RAM tối thiểu đã được xác nhận cho toàn corpus. Python 3.14.3 từng được dùng trong kiểm chứng; wheel neural có thể khác theo phiên bản và nền tảng.

Từ repo root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd web
npm ci
cp .env.example .env
```

## Cấu hình

Backend đọc biến môi trường của process qua `itlr/config.py` và tầng LLM. Có thể sao chép root `.env.example` thành `.env` rồi nạp có chủ đích trước lệnh backend:

```bash
cp .env.example .env
set -a
. ./.env
set +a
```

Đây là thao tác source một file shell local tin cậy. Không source file lấy từ nguồn không tin cậy. Web tự đọc `web/.env` khi chạy từ thư mục `web/`; hai file cấu hình không tự thay thế nhau.

| Biến | Cách dùng |
|---|---|
| `DATABASE_URL` (Web) | PostgreSQL URL có mật khẩu riêng; code từ chối các mật khẩu mặc định phổ biến |
| `JWT_SECRET`, `ADMIN_PASSCODE` (Web) | Ngẫu nhiên, lần lượt ≥32 và ≥16 ký tự; bắt buộc cả ở development |
| `PORT`, `RECOMMENDER_URL` (Web) | `3000`, `http://127.0.0.1:8000` |
| `APP_ORIGIN` (Web) | `http://localhost:3000` khi local; production mode bắt buộc HTTPS origin tường minh |
| `WEB_CONCURRENCY`, `TRUSTED_PROXIES` | Một worker; proxy trust rỗng khi kết nối trực tiếp, chỉ khai IP/CIDR proxy thật |
| `ITLR_ADMIN_TOKEN` | Bảo vệ `/admin/reload`; trống nghĩa là tắt endpoint (403) |
| `ITLR_REQUIRE_ARTIFACT_MANIFEST` | Đặt `1` để kiểm SHA256 inventory trước khi nạp pickle |
| `ITLR_ARTIFACTS_DIR`, `ITLR_ITEMS_CSV`, `ITLR_INTERACTIONS_CSV` | Override qua config cho môi trường riêng; không sửa path trong mã nguồn |
| `HF_HOME`, `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` | Cache và chế độ offline của E5/reranker |
| `USE_OLLAMA`, `OLLAMA_MODEL`, `DISABLE_RERANKER` | Chọn generation local và bật/tắt reranker có chủ đích |
| `DEEPSEEK_API_KEY`, `OPENAI_API_KEY` | Chỉ đặt khi được phép gọi provider; bỏ khỏi môi trường khi thử local |

Có thể sinh secret local bằng `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`; không đưa kết quả vào commit hoặc báo cáo. Giữ `.env` ngoài Git và hạn chế quyền đọc. SMTP là tùy chọn; khi thiếu cấu hình, hệ thống không gửi email reset và không được log reset token. Model name/base URL và giá LLM trong code không phải xác nhận dịch vụ/giá hiện hành của provider.

## Chuẩn bị dữ liệu và index

Chọn một trong hai nguồn dữ liệu đầu vào: import [snapshot curated](../data/README.md) để bootstrap offline hoặc thu thập giới hạn từ cấu hình đã kiểm quyền sử dụng. Hai cách đều ghi SQLite và metadata local.

```bash
.venv/bin/python scripts/import_curated_snapshot.py
```

Hoặc kiểm danh sách rồi chạy crawler:

```bash
.venv/bin/python scripts/collect_data.py --sources help
.venv/bin/python scripts/collect_data.py
```

Crawler ghi `var/data/collect/crawl.db`, `last_run.json`; robots/rate-limit không thay thế việc kiểm tra giấy phép. `full_text_allowed` và `listing_is_complete` phải là JSON boolean. Rolling feed mặc định không phải danh mục đầy đủ, vì vậy không tự đánh dấu bài missing chỉ do vắng mặt.

Build/probe một version mới và giữ quyền chuyển index cho bước riêng:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  HF_HOME="$PWD/var/hf" USE_OLLAMA=0 DISABLE_RERANKER=1 \
  .venv/bin/python scripts/build_all_v2.py --real-only --no-activate
```

Nếu chưa cache model, thêm `--online` khi đã có mạng và chủ động cho phép tải. Tên CLI V2 giữ vì tương thích; builder hiện lưu chunk vectors cho đường V3. `--real-only` chỉ lấy nguồn thật; nếu bỏ cờ, catalog có thể ghép legacy synthetic. `--with-cf` sinh interactions synthetic và build CF, chỉ dùng khi cần tính năng này. Không copy file vào version active hoặc bỏ probe để làm readiness pass.

Probe kiểm cấu trúc artifacts, hàng/dimension/NaN/norm/ID, TF-IDF self-retrieval và nạp engine trong subprocess. Kết quả trong `MANIFEST.json` là kiểm tra kỹ thuật, chưa thay thế evaluation chất lượng độc lập. SHA256 kiểm toàn vẹn của artifacts từ builder tin cậy; pickle vẫn có thể thực thi mã và không được nhận từ nguồn tùy ý.

## Khởi chạy API và Web

Với model đã cache và version đã chọn, xem [lệnh Ollama/E5 local](LOCAL_MODELS.md). Có thể đặt `USE_OLLAMA=0` để thử template/extractive; không báo cáo kết quả đó như generation LLM. API lắng nghe loopback, một worker, `--no-proxy-headers` khi không có proxy tin cậy.

Tạo PostgreSQL database riêng trước khi áp schema. Từ `web/`:

```bash
npm run migrate
```

Từ repo root export catalog của index active:

```bash
.venv/bin/python scripts/export_web_catalog.py
```

Quay lại `web/`:

```bash
npm run seed
npm run build
npm start
```

Seed cần `var/data/web_items.csv`, dùng upsert và không reset enrollments. Dùng `npm run sync` khi đồng bộ catalog về sau; kiểm database đích trước mọi lệnh ghi. Development có thể chạy `npm run dev`. Build copy JavaScript, EJS views, public assets và schema SQL vào `dist/`; Dockerfile Web gọi cùng lệnh build.

## Chuyển version, reload và rollback

`build_all_v2.py` không có `--no-activate` sẽ tự activate sau probe và chạy GC. Để duyệt version trước khi chuyển, dùng `--no-activate` rồi gọi API Python với đúng ID đã probe:

```python
from itlr import versioning
versioning.activate(version="TEN_VERSION_DA_PROBE")
```

Sau khi pointer đổi, reload API qua `POST /admin/reload` với header `X-Admin-Token` chứa secret đang cấu hình, hoặc restart process. Không in header/token vào log. Reload nạp engine mới trước khi hoán đổi; bản lỗi bị từ chối và engine đã nạp tiếp tục phục vụ. Request đang chạy có thể dùng state cũ.

Khi cần quay lại, gọi `versioning.rollback()` rồi reload/restart API. Không chạy rollback như một phần mặc định của khởi động. Giữ bản backup của PostgreSQL và artifacts trước migration hoặc đổi nguồn.

`CURRENT.json` atomically chứa pointer và transition history; file `CURRENT.json.history.json` là mirror tương thích. Nếu báo lỗi sau pointer commit, đọc pointer trước khi retry để tránh tạo chuyển trạng thái ngoài ý muốn. Test process-exit/restart chứng minh phạm vi hồi phục trong process; chưa chứng minh mất điện, controller hoặc network filesystem. GC giữ current/previous và staging chưa probe; không xóa thư mục thủ công khi job đang chạy.

## Refresh tự động và container

`scripts/refresh_pipeline.py` chạy crawl, build khi có tài liệu mới/cập nhật và activate sau probe; `--no-build` chỉ crawl, vẫn ghi dữ liệu ingestion. CLI không có cờ `--real-only`: đặt `ITLR_REAL_ONLY=1` trong môi trường job nếu cần index chỉ nguồn thật. Không để job mặc định vô tình đưa legacy synthetic trở lại catalog đã chọn real-only.

CLI crawl/build dùng pipeline lock; refresh parent dùng refresh lock. Bảo đảm chỉ áp dụng cho writers dùng cùng cơ chế khóa trên Linux local. Timer/service mẫu trong thư mục này cần kiểm lại đường dẫn và môi trường trên máy đích; bật timer là hành động vận hành riêng.

Root `docker-compose.yml` chỉ mô tả API và refresh, **chưa bao gồm Web + PostgreSQL**. Web có Dockerfile riêng. Compose API hiện mount `./var` read-write; nếu triển khai thực tế cần tách mount theo trách nhiệm, đặc biệt cho API đọc artifacts, thay vì suy diễn cấu hình mẫu đã cô lập quyền ghi. Không dùng `docker compose down -v` hoặc xóa volume để xử lý lỗi.

Nếu mở truy cập ngoài máy local, cần TLS, origin/cookie đúng, reverse proxy ghi đè forwarded headers, backup và giới hạn CPU/RAM/đĩa. Limiter/presence trong RAM yêu cầu một process/replica; chưa có hỗ trợ nhiều host. [ADR-009](../docs/decisions/ADR-009-security-runtime-boundaries.md) và [security remediation](../web/SECURITY_REMEDIATION.md) ghi các ranh giới hiện tại.

## Kiểm tra và xử lý sự cố

| Hiện tượng | Kiểm tra và hành động |
|---|---|
| `/login` 200 nhưng thao tác tài khoản lỗi | Web `/ready` và PostgreSQL credentials/schema; login public không chứng minh DB readiness |
| API `/health` 503 | Đọc lỗi artifacts/model và pointer thực tế; build/probe staging tin cậy, không thêm dữ liệu giả để qua check |
| `/api/personas` hoặc `/api/for-you` 503 | Kiểm `cf` trong health; thiếu CF là trạng thái tính năng tùy chọn |
| Admin reload 403 | Kiểm token đã cấu hình và header trên kênh nội bộ; không bỏ auth để sửa lỗi |
| Offline model không nạp được | Kiểm `HF_HOME`, cache, quyền đọc và model metadata; chỉ tải online có chủ đích |
| Stream dừng hoặc citation không hợp lệ | Đọc `error`/`final`, không giữ provisional như đáp án hoàn chỉnh; kiểm evidence và chunk IDs |
| Build báo lỗi sau activate | Đọc `CURRENT.json`/history trước retry; pointer có thể đã commit dù mirror lỗi |
| TestClient treo trong sandbox | Dùng kiểm chứng ngoài sandbox theo quyền được cấp; không skip tests |

Chạy [bộ kiểm thử](../README.md#kiểm-thử-và-đánh-giá) trước bàn giao. Docker, authenticated browser E2E, SMTP, load toàn corpus và storage power-loss vẫn là các cổng kiểm chứng riêng; readiness/login smoke không thay thế chúng.

Code ownership and dependency direction: [architecture map](../docs/ARCHITECTURE.md).
