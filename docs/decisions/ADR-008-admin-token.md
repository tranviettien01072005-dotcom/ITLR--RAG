# ADR-008: Reload quản trị phải được xác thực

## Status

Accepted. Historical decision; current runtime evidence is maintained in reports/VALIDATION.md.


Sản phẩm: **ITLR–RAG | Intelligent IT Learning Platform**. Accepted, 2026-10-29.
Vận hành: [deployment](../../deploy/DEPLOY.md).

## Context

`/admin/reload` nạp artifacts từ `CURRENT.json` và thay engine. Gọi không kiểm soát có thể
lạm dụng tài nguyên hoặc kích hoạt nội dung không mong muốn từ filesystem. Mạng nội bộ
không thay thế xác thực cho thao tác này.

## Decision

Mỗi request đọc `ITLR_ADMIN_TOKEN` và so header `X-Admin-Token` bằng `secrets.compare_digest`.
Không cấu hình hoặc token rỗng làm endpoint trả **403**; không có default key.

Sinh secret đủ mạnh, chẳng hạn `secrets.token_urlsafe(32)`, giữ trong environment hoặc file local
ngoài Git, quyền file phù hợp (`chmod 600`). Truyền header qua kênh được bảo vệ; proxy phải
được cấu hình rõ ràng và không công khai token. Không log token hay đưa vào báo cáo.

## Alternatives

Basic auth thêm quản lý username/password cho API nội bộ nhỏ. IP allow-list khó duy trì
trong môi trường địa chỉ thay đổi và vẫn có thể bổ sung token. Bỏ auth trong private network
không đáp ứng ranh giới quản trị.

## Consequences

Không cấu hình token thì reload bị vô hiệu hóa an toàn. Đọc environment mỗi request hỗ trợ
rotation trong process có environment được cập nhật; thay environment của service thường
vẫn cần restart theo cách triển khai. `tests/test_admin_security_cf.py` kiểm thiếu, sai và đúng
token. [.env.example](../../.env.example) chỉ chứa placeholder; secret thật không đưa vào repo.
