# Chạy và triển khai thử ITLR–RAG

Cập nhật 2026-10-30. Mục tiêu là môi trường học tập có thể tái lập, không phải xác nhận sẵn sàng
vận hành thương mại. [README](../README.md) là hướng dẫn tổng quan; [validation](../reports/VALIDATION.md)
phân biệt kiểm chứng thực tế và phần còn thiếu.

## Thành phần

| Dịch vụ | Cổng local | Vai trò |
|---|---|---|
| Web Express | 3000 | Giao diện chính trong web/ |
| Python FastAPI | 8000 | Retrieval và chatbot |
| PostgreSQL | Theo DATABASE_URL | Tài khoản, tài nguyên, học tập, hội thoại |
| Ollama tùy chọn | 11434 | Generation local không cần API trả phí |

Một process mỗi service. Tham số proxy phải chỉ rõ proxy tin cậy; không mặc định tin mọi header.
Dùng Linux local cho khóa flock. Chưa chứng minh phối hợp nhiều host hoặc network filesystem.

## Thiết lập web local

Tại repo root, tạo venv và cài `requirements.txt`. Trong `web/`:

```bash
npm ci
cp .env.example .env
```

Điền database riêng của đồ án, secret ký JWT ≥32 ký tự và admin passcode ≥16 ký tự.
Có thể sinh giá trị bằng `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`.
Không commit file cấu hình thật hoặc sao chép secret vào báo cáo.

- `DATABASE_URL`: PostgreSQL có tài khoản/mật khẩu riêng.
- `RECOMMENDER_URL=http://127.0.0.1:8000`.
- `PORT=3000`, `APP_ORIGIN=http://localhost:3000` khi thử HTTP local.
- `WEB_CONCURRENCY=1`, `TRUSTED_PROXIES=` nếu không qua proxy.
- SMTP tùy chọn; không cấu hình thì email reset không được gửi. Không bật logging reset token.

Chỉ áp schema vào database được tạo riêng, không làm thử trên database người dùng không thuộc đồ án:

```bash
npm run migrate
```

Từ repo root, export catalog index active nếu cần seed:

```bash
.venv/bin/python scripts/export_web_catalog.py
```

Trong `web/`:

```bash
npm run seed
npm run build
npm start
```

Build bao gồm JS, views, public assets và schema SQL; Docker tái sử dụng cùng bước này.
Seed dùng upsert, không reset database hoặc xóa enrollment. Không dùng xóa volume để xử lý lỗi.

## Backend và local model

Theo [LOCAL_MODELS](LOCAL_MODELS.md) cho Ollama/E5. Tắt DeepSeek/OpenAI key khi chỉ thử local.
Có thể đặt `USE_OLLAMA=0` để thử template/extractive. Không gắn nhãn template là đánh giá LLM.
Backend mặc định lắng nghe loopback, một worker, không tự tin forwarded headers.
`ITLR_REQUIRE_ARTIFACT_MANIFEST=1` bật kiểm tra SHA256 trước khi đọc artifacts.
Không unpickle nội dung không đáng tin; SHA256 chỉ kiểm tra tính toàn vẹn trong vùng artifact tin cậy.

## Build và đổi index

```bash
.venv/bin/python scripts/collect_data.py
.venv/bin/python scripts/build_all_v2.py --real-only --no-activate
```

Lần đầu model chưa cache dùng `--online` có chủ đích. Tên CLI V2 được giữ tương thích; builder mới
lưu chunk vectors. Không copy artifacts trực tiếp vào version active. Probe phải pass trước activate.
CF synthetic tùy chọn `--with-cf`; thiếu CF làm các endpoint CF trả 503, không hỏng search.

Với một version đã probe, có thể dùng Python API quản lý tại repo root:

```python
from itlr import versioning
versioning.activate(version="TEN_VERSION_DA_PROBE")
# Chỉ rollback khi cần, không thực thi cùng activate như lệnh khởi động:
# versioning.rollback()
```

Đây là ví dụ, không phải yêu cầu tự activate khi đọc hướng dẫn. Sau thay đổi index, gọi
`POST /admin/reload` với `X-Admin-Token` đã cấu hình. Token trống phải trả 403.
Reload giữ engine cũ nếu bản mới lỗi; request đang chạy có thể tiếp tục dùng bản đã nạp.

`CURRENT.json` atomically chứa pointer và transition history, có fsync file/directory.
History file riêng là mirror tương thích. Nếu lỗi sau pointer commit, đọc CURRENT.json trước retry.
Test process-exit/restart không chứng minh khả năng chịu mất điện của ổ đĩa/controller.
GC giữ current, previous và staging chưa probe; không xóa thủ công thư mục khi job đang chạy.

CLI crawl/build dùng pipeline lock; refresh parent dùng khóa riêng để tránh chồng lượt refresh.
Các tác vụ ghi trực tiếp không dùng khóa nằm ngoài bảo đảm này.
Rolling feed mặc định `listing_is_complete: false`; chỉ đặt true cho inventory đầy đủ có thẩm quyền.
Hai cờ policy và `full_text_allowed` phải là JSON boolean. Không tự phục hồi hàng loạt records missing.

## Container và môi trường triển khai

Root `docker-compose.yml` hiện mô tả API và refresh; **không phải stack đầy đủ Web + PostgreSQL**.
Web có Dockerfile riêng. Dockerfile được kiểm tra bằng đọc cấu hình/build app; chưa xác minh Docker
image/Compose chạy thực tế trong phiên này. Không dùng readiness trang login thay DB readiness.

Nếu chạy web với `NODE_ENV=production`, cấu hình HTTPS origin tường minh và secure cookies sau TLS.
Mount dữ liệu runtime ra ngoài image; backup PostgreSQL và artifacts trước migration hoặc đổi nguồn.
Thông báo giấy phép và nguồn tài liệu nằm trong `data/`; không tự gán MIT cho mã đồ án.

## Kiểm tra và xử lý sự cố

- Web `/ready` phải kiểm tra database; `/login` chỉ chứng minh trang public render được.
- API `/health` kiểm tra engine, số item và CF; `/live` là liveness.
- Thiếu artifacts: build/probe trước; không tạo dữ liệu giả để qua health.
- Model offline thiếu cache: kiểm tra HF_HOME, dùng bước tải có phép; không fallback model âm thầm.
- Sai nguồn trích dẫn: trả insufficient evidence, không chỉ thay ID cho qua validator.
- Không công khai port/admin/secret chỉ để giải quyết lỗi local.

Test suite, dependency consistency và kiểm tra Markdown theo [README](../README.md#kiểm-thử-và-đánh-giá).
