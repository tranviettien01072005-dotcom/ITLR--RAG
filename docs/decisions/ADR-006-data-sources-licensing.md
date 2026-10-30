# ADR-006: Chính sách nguồn, quyền nội dung và provenance

## Status

Accepted. Historical decision; current runtime evidence is maintained in reports/VALIDATION.md.


Sản phẩm: **ITLR–RAG | Intelligent IT Learning Platform**. Accepted, 2026-10-29.
Nguồn hiện hành: [data guide](../../data/README.md), [source config](../../configs/collect.sources.json).

## Context

Catalog legacy 5.000 items là synthetic. Collection cần tài nguyên có URL, tác giả, ngày lấy,
hash và chính sách lưu rõ ràng. Metadata license trong config là hồ sơ vận hành tại checkpoint,
không phải xác nhận pháp lý cho mọi bài hoặc quyền thương mại của nền tảng.

## Decision

| Nguồn tại checkpoint | Cách lấy | Metadata quyền đã ghi | Chính sách cấu hình |
|---|---|---|---|
| DEV Community, tag python | JSON API | Nội dung thuộc tác giả; config dẫn ToS/CC BY-SA và yêu cầu kiểm tra lại | Full text khi được phép |
| freeCodeCamp News | RSS + HTML | CC BY-SA 4.0, cần xác minh theo bài/nguồn | Full text, attribution và link |
| MDN Web Docs Blog | RSS + HTML | CC BY-SA 2.5, cần xác minh theo bài/nguồn | Full text, attribution và link |
| VnExpress Công nghệ | HTML listing | Chưa có giấy phép mở | Chỉ title, mô tả ngắn và URL |

Người thêm nguồn phải kiểm quyền, robots và điều khoản trước khi bật collection. Public API hoặc
robots cho phép không tự cấp quyền sao chép. Giữ credit, link gốc, tác giả và nghĩa vụ license;
không gán một giấy phép chung cho nội dung bên thứ ba.

`full_text_allowed` và `listing_is_complete` phải là JSON boolean. Nguồn snippet-only bị loại
khỏi export văn bản qua `docs_for_index()`. Feed rolling không phải inventory đầy đủ: bài vắng
khỏi feed không được tự đánh dấu đã xóa. Quyền thay đổi phải được ghi khi refetch; thu hồi quyền
chặn export mới mà không tự xóa snapshot hoặc artifacts đã active.

`item_map` trong SQLite gán ID ổn định theo hash URL chuẩn hóa, ID mới bắt đầu trên max legacy ID.
Lọc listing bằng `link_pattern`, lọc `too_short`, content-hash trùng và tiêu đề tương tự ≥0.8;
quyết định lưu `quality_status`. Catalog giữ `origin`, `crawl_license`, `crawl_lang`, `crawl_hash`,
URL, platform và tác giả.

## Alternatives

HTTPX + BeautifulSoup đáp ứng các nguồn hiện có mà không cần browser JS/Scrapy. Request cần
kiểm HTTP status, robots/rate-limit từng host kể cả redirect, retry/backoff cho 429/5xx/timeout,
cache robots/Crawl-delay và chuẩn hóa URL bỏ tracking params. Mỗi source có `max_items_per_run`.
Nguồn mới như GitHub/Coursera cần đánh giá API key và điều khoản riêng; không mặc nhiên được phép.

## Consequences

Checkpoint đầu ghi khoảng 85 docs: DEV 25, freeCodeCamp 10, MDN 25, VnExpress 25; một số bài
freeCodeCamp bị lọc do text quá ngắn. Đây là số lịch sử, không phải corpus hiện hành hoặc
benchmark tốc độ nguồn. Đọc `/health` cùng version/provenance để xác định dữ liệu runtime.
Operator phải rebuild/probe/activate khi thay quyền của nội dung đã vào index; giữ snapshot
không đồng nghĩa tiếp tục được phục vụ toàn văn. Không xóa dữ liệu trong đợt sửa tài liệu.
