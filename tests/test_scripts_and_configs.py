"""Yêu cầu hạ tầng dự án: pyproject.toml hợp lệ + .env.example đầy đủ + scripts/build_all.py.

Bugs được hồi quy:
  - server.py lifespan hướng dẫn `python scripts/build_all.py` nhưng script KHÔNG TỒN TẠI.
  - Không có pyproject.toml -> người dùng checkout phải cài dependency bằng tay.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_exists_and_valid_toml():
    p = ROOT / "pyproject.toml"
    assert p.exists(), "phải có pyproject.toml (metadata + dependencies)"
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    assert data.get("project", {}).get("name"), "project.name bắt buộc"


def test_pyproject_declares_core_deps():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for dep in ("fastapi", "uvicorn", "pandas", "scikit-learn", "openai",
                "sentence-transformers", "faiss-cpu"):
        assert dep in text, f"pyproject.toml thiếu dependency {dep}"


@pytest.mark.parametrize(
    "var",
    ["DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
     "OPENAI_API_KEY", "USE_OLLAMA", "OLLAMA_BASE_URL"],
)
def test_env_example_documents_llm_vars(var: str):
    """.env.example phải ghi chép mọi biến cấu hình LLM mà code đọc."""
    p = ROOT / ".env.example"
    assert p.exists(), "thiếu .env.example (hướng dẫn cấu hình)"
    assert var in p.read_text(encoding="utf-8"), f".env.example thiếu biến {var}"


def test_scripts_build_all_dry_run_missing_artifacts(tmp_path):
    """--dry-run với artifacts TRỐNG (tmp) -> phải mô tả đủ 3 bước build (rc=0)."""
    script = ROOT / "scripts" / "build_all.py"
    assert script.exists(), (
        "scripts/build_all.py KHÔNG TỒN TẠI nhưng server.py lifespan hướng dẫn chạy script này"
    )
    env = {**os.environ, "ITLR_ARTIFACTS_DIR": str(tmp_path / "empty_artifacts")}
    r = subprocess.run(
        [sys.executable, str(script), "--dry-run"],
        capture_output=True, text=True, timeout=120, cwd=str(ROOT), env=env,
    )
    assert r.returncode == 0, f"--dry-run phải rc=0. stderr: {r.stderr[:400]}"
    out = r.stdout
    assert len(out.strip().splitlines()) >= 3, "--dry-run phải mô tả các bước build"
    for step in ("retrieval_model", "embeddings_ann", "collaborative"):
        assert step in out, f"--dry-run thiếu bước {step}"


def test_scripts_build_all_dry_run_all_present(tmp_path):
    """--dry-run khi artifacts ĐẦY ĐỦ (tmp chứa sentinel) -> báo không cần build (rc=0)."""
    have = tmp_path / "full_artifacts"
    have.mkdir()
    for name in ("item_list.pkl", "retrieval_model.pkl", "tfidf_vectorizer.pkl",
                 "tfidf_matrix.pkl", "embeddings.pkl", "search_meta.pkl",
                 "char_vectorizer.pkl", "char_matrix.pkl", "cf_model.pkl"):
        (have / name).write_bytes(b"")
    env = {**os.environ, "ITLR_ARTIFACTS_DIR": str(have)}
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_all.py"), "--dry-run"],
        capture_output=True, text=True, timeout=120, cwd=str(ROOT), env=env,
    )
    assert r.returncode == 0
    assert "Tất cả artifact đã sẵn sàng" in r.stdout


def test_scripts_build_all_help():
    script = ROOT / "scripts" / "build_all.py"
    r = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT),
    )
    assert r.returncode == 0, f"--help phải rc=0. stderr: {r.stderr[:400]}"
