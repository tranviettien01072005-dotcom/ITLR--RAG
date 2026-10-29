"""Gói thu thập dữ liệu V2 — crawl CNTT từ nguồn được phép (API/RSS/website).

Thiết kế: ĐƠN GIẢN — Python thuần (httpx + feedparser + BeautifulSoup) + SQLite.
Nothing-chained: mỗi module có 1 trách nhiệm, đáng tin cậy, dễ debug:

    url_util  — chuẩn hóa URL + khóa nội dung (chống trùng)
    robots    — kiểm tra robots.txt (bắt buộc trước mọi fetch)
    rate      — giới hạn tần suất theo host + jitter
    client    — HTTP client fetch với timeout + retry/backoff
    extract   — trích nội dung từ HTML oleh BeautifulSoup
    quality   — lọc nội dung rác/quá ngắn + near-dup
    adapters  — rss / api / web  → RawItem chuẩn
    store     — SQLite: upsert, cập nhật thay đổi, provenance
    chunk     — chia tài liệu dài thành các mảnh (cho embeddings)
    normalize — RawItem/SQLite → schema ITLR (item_id ỔN ĐỊNH)
    crawl     — orchestrator một lượt chạy

Không Kafka, không Spark, không DataLake — gỡ được từng mảnh một.
"""

from itlr.collect.url_util import content_key, normalize_url, same_site  # noqa: F401
