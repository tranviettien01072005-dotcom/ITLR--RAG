# ADR-008: Bảo vệ API quản trị bằng token (`/admin/reload`)

## Trạng thái
Accepted

## Ngày
2026-10-29

## Bối cảnh
`/admin/reload` ngắt cache engine và nạp lại artifacts từ con trỏ CURRENT.json —
năng lực vận hành nhưng cũng là khả năng DoS (spam reload liên tục) và leo thang (nạp artifacts
tùy ý từ đĩa). Sàn dự án: mọi endpoint đụng tới trạng thái hệ thống phải có auth; không có
key mặc định.

## Quyết định
- **Env `ITLR_ADMIN_TOKEN`** là khóa cấu hình duy nhất; đọc tại thời điểm MỖI request (không
  cache) — rotate token không cần restart.
- **Env trống / không đặt** ⇒ endpoint coi như TẮT: mọi request nhận 403 kèm hướng dẫn cấu hình.
  Thiết kế có chủ đích: fail-closed, không có "mặc định trống cho phép".
- **Header `X-Admin-Token`** so sánh bằng `secrets.compare_digest` (chống timing side-channel).
- Vận hành: sinh token `secrets.token_urlsafe(32)`, giữ trong `.env` (chmod 600, ngoài git);
  proxy thật (nginx/traefik) chỉ pass header này vào mạng nội bộ.

## Phương án đã cân nhắc
- **Basic auth**: cần thêm username/password form + TLS; heavier — token đơn header đủ cho API
  nội bộ (đã có firewall/LAN).
- **IP allow-list**: môi trường docker/cloud dynamic IP khó bền vững; token bền hơn.
- **No auth trong private network**: không — reload là vector vận hành dễ lạm dụng; mạng nội bộ
  chia sẻ nhiều người vẫn cần phân quyền.

## Hệ quả
- Tests: `tests/test_admin_security_cf.py` — 3 ca (tắt khi trống · sai token · đúng token).
- DEPLOY.md §1.2 hướng dẫn sinh token + curl; .env.example có placeholder + hướng dẫn.
- Sàn "no secrets in repo giữ": chỉ ví dụ, giá trị thật sinh cục bộ.
