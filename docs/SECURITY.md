# Bảo mật: trust boundary, kiểm soát và giới hạn

Tài liệu chuẩn cho bảo mật hiện hành. Quyết định liên quan:
[ADR-008](decisions/ADR-008-admin-token.md),
[ADR-009](decisions/ADR-009-security-runtime-boundaries.md). Lịch sử khắc phục:
[web/SECURITY_REMEDIATION.md](../web/SECURITY_REMEDIATION.md) (báo cáo cũ, giữ nguyên).

## 1. Trust boundary

| Vùng | Tin cậy | Ghi chú |
|---|---|---|
| Nguồn crawl, catalog, excerpt | **không** | coi là dữ liệu, không phải instruction; chống prompt injection ở system prompt |
| Nội dung người dùng (chat, post, PDF/ảnh) | **không** | validate/escape; upload kiểm chữ ký |
| Provider LLM | **không** | output không được thực thi; citation phải kiểm |
| Artifacts pickle | tin cậy **có điều kiện** | chỉ từ builder/probe; SHA256 inventory không chống attacker sửa cả manifest |
| Process/DB/proxy | tin cậy theo cấu hình | một host, local filesystem, proxy IP khai báo tường minh |

## 2. Xác thực và phân quyền

- **Web**: đăng nhập phát JWT trong cookie `token` (`HttpOnly`, `SameSite=Lax`,
  `Secure` khi production, hết hạn sau 7 ngày). Payload mang `tv` (token_version) và mỗi
  request so với cột `users.token_version`; đổi/đặt lại mật khẩu tăng version nên mọi JWT
  cũ mất hiệu lực ngay, không cần chờ hết hạn. Route riêng cần `requireAuth`; quản trị
  cần `requireAdminAccess`. Kiểm tra quyền sở hữu (hội thoại, file, bài viết) thực hiện
  theo `user_id`, không dựa vào tham số client.
- **CSRF**: cookie `csrf` + header `x-csrf-token` hoặc field `_csrf`; mọi method không an
  toàn bị kiểm, thiếu/sai trả 403.
- **Thu hồi phiên**: đổi/đặt lại mật khẩu và `POST /account/logout-all` tăng
  `users.token_version`, nên JWT cũ bị từ chối ở request kế tiếp; `POST /logout` chỉ xóa
  cookie của thiết bị hiện tại.
- **Admin API**: `POST /admin/reload` yêu cầu `X-Admin-Token` khớp `ITLR_ADMIN_TOKEN` bằng
  `secrets.compare_digest` trên bytes; env rỗng ⇒ endpoint tắt (403), không có mặc định.
  Mỗi lần auth fail được log để audit (không log token).
- Web không cung cấp bearer token cho trình duyệt; API không có endpoint công khai ghi dữ liệu.

## 3. Kiểm soát đầu vào

- Pydantic cho API: `query` ≤500, `message` ≤2000, `history` ≤20 lượt, content ≤4000;
  `role ∈ {user, assistant}`; `min_pct` 0–100.
- Upload: chỉ PNG/JPEG/GIF/WebP/PDF đã kiểm magic bytes + MIME + giới hạn kích thước
  (≤20 MB tổng, ≤25 MP ảnh); file lỗi bị zero buffer và trả 415. Không nhận Office/video;
  **không phải antivirus**, không render chủ động.
- Không nối SQL/HTML từ input; truy vấn dùng tham số; EJS escape mặc định. Link nguồn được
  chuẩn hóa scheme (chỉ http/https) ở `itlr/core/display.py`.
- Giới hạn tần suất: API 120 search/phút, 30 chat/phút, 10 admin/phút (env override, `0` = tắt);
  Web 300 request/phút toàn cục, 20 lần/15 phút cho auth. 429 kèm `Retry-After`.
  Reset email có thêm cooldown theo **tài khoản** (`RESET_EMAIL_COOLDOWN_SECONDS`, mặc định 60s)
  và chỉ token mới nhất còn hiệu lực, nên không thể spam hộp thư qua nhiều IP.

## 4. Header và cookie

- API: `Content-Security-Policy` chặt (`default-src 'self'`, `object-src 'none'`,
  `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, `Permissions-Policy` tắt camera/mic/geolocation.
- Web: helmet CSP (`script-src 'self'`, không inline script; `frame-src` chỉ YouTube),
  HSTS 180 ngày khi production, `upgrade-insecure-requests`, Referrer policy
  `strict-origin-when-cross-origin`. Tệp tải về/stream media dùng CSP `sandbox; default-src 'none'`.
- `APP_ORIGIN` bắt buộc HTTPS khi `NODE_ENV=production`; không lấy Host header để dựng link
  trong email reset. Cookie không dùng `SameSite=None`.

## 5. Secrets và cấu hình

- Secrets chỉ ở env hoặc file local bị gitignore; `.env.example` chỉ giá trị rỗng/placeholder.
  Có test chặn secret thật trong `.env.example`.
- Web từ chối khởi động nếu `JWT_SECRET` <32 ký tự, `ADMIN_PASSCODE` <16, `DATABASE_URL`
  dùng mật khẩu mặc định, hoặc chạy nhiều worker khi limiter/presence còn trong RAM.
- Không log key, token, cookie, reset token, nội dung chat/tệp. `/metrics` chỉ mở cho loopback
  khi chưa cấu hình token; có token thì đòi token.
- Provider base URL chỉ chấp nhận http/https (không `file:`/`javascript:`).

## 6. Artifacts và chuỗi cung ứng

- Pickle chỉ nạp từ builder tin cậy; `ITLR_REQUIRE_ARTIFACT_MANIFEST=1` kiểm SHA256 inventory
  trước khi nạp. Hash không xác nhận tác giả nếu attacker sửa được cả file và manifest.
- Reload fail-closed: artifacts lỗi/thiếu giữ engine cũ, `/health` trả 503 khi không nạp được.
- Dependencies: `pip-audit` **0 advisory**, `npm audit` **0 vulnerability**, `npm ls minimatch`
  dùng override `^11.0.1` (11.0.3). Không có ignore list lỗ hổng trong CI.
- Bandit: **0 High**, 27 Medium, 46 Low — Medium chủ yếu là pickle và URL do operator cấu
  hình; triage ở [BANDIT_TRIAGE_2026-10-30](../reports/BANDIT_TRIAGE_2026-10-30.md).
  Không dùng `# nosec` để che finding mới.

## 7. Ranh giới hạ tầng

- Một host Linux, một worker/replica mỗi service; limiter/presence/lock không phân tán.
  Không dựa vào chúng cho nhiều host.
- Khi mở Internet: chỉ Caddy publish 443, TLS bắt buộc, proxy IP tin cậy tường minh, không
  expose 3000/8000/5432. Không dùng `docker compose down -v`.
- Staging dùng mật khẩu/secret riêng, artifacts dùng một lần, HF/model mount read-only.

## 8. Giới hạn chưa xác minh

- Không có pentest độc lập, red-team prompt injection, hay đánh giá multi-tenant.
- Chưa có antivirus/CDR cho upload; chỉ kiểm định dạng.
- Không có HSM/KMS; secret nằm trong env/file của host.
- Chưa xác minh chống DoS toàn diện (rate limit RAM, một worker) hay rò rỉ qua log của proxy.
- Human/LLM safety evaluation (refusal đúng, nội dung độc hại) **NOT VERIFIED**.
