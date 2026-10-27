"""Cấu hình chung cho toàn bộ bộ test itlr.

Thêm repo root vào sys.path để `import itlr` luôn thành công bất kể cwd,
và đặt các biến môi trường "nghiêm ngặt" để bắt lỗi sớm.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Import `itlr` trực tiếp từ thư mục repo (không phụ thuộc cwd của pytest).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Console + HuggingFace an toàn khi test (không tải model thật).
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("ITLR_TEST", "1")

import pytest  # noqa: E402


@pytest.fixture()
def repo_root() -> Path:
    return ROOT
