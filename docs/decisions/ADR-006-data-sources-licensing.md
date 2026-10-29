> **Ngữ cảnh đồ án — 2026-10-30:** Quyết định kiến trúc theo thời điểm. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../../README.md).

# ADR-006: Nguồn dữ liệu crawl V2 — licensing, robots, full-text vs snippet-only

## Trạng thái
Accepted

## Ngày
2026-10-29

## Bối cảnh
Catalog legacy (5000 items) là dữ liệu tổng hợp để demo — không thể dùng làm dữ liệu thật cho người
dùng. Cần dữ liệu thật, cập nhật được và hợp pháp. Môi trường build CPU-only, không GPU. Nguyên tắc
dự án: không bao giờ bịa dữ liệu; mỗi item phải truy ngược được về nguồn gốc.

## Quyết định
Bộ nguồn mặc định trong `configs/collect.sources.json` (đã kiểm robots.txt + feed bằng curl trước
khi thêm vào cấu hình):

| Nguồn | Kiểu | Nội dung | License | Chính sách lưu |
|-------|------|----------|---------|----------------|
| dev.to (tag `python`) | JSON API | full-text + tags | Nội dung thuộc tác giả, công khai qua official API | full-text |
| freeCodeCamp News | RSS + HTML | full-text | CC BY-SA 4.0 | full-text (+ credit, link nguồn) |
| MDN Web Docs Blog | RSS + HTML | full-text | CC BY-SA 2.5 | full-text (+ credit, link nguồn) |
| VnExpress – Công nghệ | HTML listing | title + mô tả ngắn | Chưa có giấy phép mở | **snippet-only** |

Các cơ chế đi kèm:

- **Snippet-only**: `full_text_allowed=0` trong cấu hình nguồn → `docs_for_index()` loại doc ra
  khỏi index văn bản; chỉ lưu title/mô tả ngắn/URL (hyperlink, không đóng khung toàn văn).
- **item_id ổn định**: `item_map` trong SQLite, khóa `content_key` = hash của URL chuẩn hóa.
  ID mới bắt đầu tại floor = max(item_id legacy) + 1 → ID cũ không bao giờ bị chiếm đoạt
  (trích dẫn `[item_id:...]` không hỏng giữa các phiên bản index).
- **Lọc trang listing**: `link_pattern` regex theo nguồn (ví dụ VNE:
  `^\/[-a-zA-Z0-9~-]+-[0-9]{4,}\.html$` — bài thật luôn có id trong đường dẫn) → chặn trang mục
  lục/tag-page đi vào docs.
- **Chất lượng**: lọc `too_short`, loại trùng theo content-hash và tiêu đề-tương tự ≥ 0.8 với
  catalog legacy; trạng thái quyết định lưu ở `quality_status` (không xóa âm thầm).
- **Provenance**: cột `origin` (vd `crawl:devto-python` / `legacy:synthetic`), `crawl_license`,
  `crawl_lang`, `crawl_hash` đi vào CSV catalog — minh bạch nguồn gốc từng hàng.

## Crawler hợp quy
- HTTPX một client/lần fetch; retry exponential-backoff cho 429/5xx/timeout; timeout connect và
  timeout request tách riêng.
- Kiểm tra robots.txt trước khi fetch mỗi host lần đầu; cache kết quả + `Crawl-delay`.
- Rate limiter per-host; chuẩn hóa URL (bỏ UTM/traffic params, trailing slash) chống re-fetch.
- Số lượng mỗi lượt: giới hạn bởi `max_items_per_run` từng nguồn.

## Phương án đã cân nhắc
- **Scrapy/Playwright**: nhẹ hều hơn cho nhu cầu 4 nguồn; bs4 + httpx đủ, ít dependency mới, dễ test.
  Playwright (cần browser JS) bị loại — các nguồn hiện tại không đòi render JS.
- **Nguồn khác** (GitHub, Coursera…): yêu cầu API key / điều khoản riêng — để tương lai khi có cấp phép.
- **Crawl toàn văn VnExpress**: không có giấy phép mở → chỉ snippet.

## Hệ quả
- Lượt đầu cho ~85 docs thật (devto 25 · fCC 10 · MDN 25 · VNE 25; một số bài fCC bị lọc
  `too_short` do trích xuất không đủ — đúng thiết kế, không nuốt lỗi âm thầm).
- Không so sánh tốc độ giữa các nguồn vì số liệu chưa đủ dài hạn (cảnh báo trung thực).
- Quy trách nhiệm khi thêm nguồn mới: người thêm tự verify license + robots trước khi cấu hình;
  license ghi tường trong config, không ghi chung chung.
- Credit luôn đi kèm mỗi item: `link` = URL gốc, `platform`, `instructor` (tác giả) — mọi trích dẫn
  trong RAG dẫn về đúng nguồn, không nhận nhầm tác quyền.
