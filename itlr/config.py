"""Cấu hình đường dẫn TẬP TRUNG — độc lập với thư mục làm việc hiện tại (CWD).

Mọi nơi cần tới var/artifacts/ hoặc var/data/ nên dùng các hằng/hàm ở đây thay vì hardcode
đường dẫn tương đối, để chạy được dù gọi từ thư mục nào (`python -m itlr.pipelines...`).
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_OVERRIDE_ARTIFACTS = os.environ.get("ITLR_ARTIFACTS_DIR")
ARTIFACTS_DIR = (Path(_OVERRIDE_ARTIFACTS) if _OVERRIDE_ARTIFACTS
                 else ROOT / "var" / "artifacts")
DATA_DIR = ROOT / "var" / "data"

ITEMS_CSV = Path(os.environ.get("ITLR_ITEMS_CSV", DATA_DIR / "it_learning_items.csv"))
INTERACTIONS_CSV = Path(os.environ.get("ITLR_INTERACTIONS_CSV", DATA_DIR / "interactions.csv"))

# --- V2: thu thập dữ liệu (crawler) ---
# Dữ liệu thu thập được lưu SQLite + file nguồn; KHÔNG tự bịa dữ liệu.
COLLECT_DIR = DATA_DIR / "collect"
COLLECT_DB = COLLECT_DIR / "crawl.db"
COLLECT_SOURCES = Path(os.environ.get(
    "ITLR_COLLECT_SOURCES", ROOT / "configs" / "collect.sources.json"))
VERSIONS_DIR = ARTIFACTS_DIR / "versions"

LAST_RUN_JSON = COLLECT_DIR / "last_run.json"


def _resolve_active_dir() -> Path:
    """Thư mục artifacts tự động đang dùng: env override > con trỏ CURRENT.json > mặc định.

    Con trỏ CURRENT.json ghi {"version": "<id>", "dir": "<relative>"} để hệ thống index
    theo phiên bản (kiểm thử trước khi kích hoạt, rollback). Không có con trỏ → hành vi
    cũ (build trực tiếp vào ARTIFACTS_DIR) được giữ nguyên.
    """
    override = os.environ.get("ITLR_ARTIFACTS_DIR")
    if override:
        return Path(override)
    from itlr.versioning import current_dir as resolve_version
    return resolve_version(ARTIFACTS_DIR)


def current_dir() -> Path:
    """Thư mục artifacts đang hoạt động (đọc LẠI mỗi lần gọi, không cache)."""
    return _resolve_active_dir()


def artifact(name: str) -> str:
    return str(_resolve_active_dir() / name)


def data_file(name: str) -> str:
    return str(DATA_DIR / name)
