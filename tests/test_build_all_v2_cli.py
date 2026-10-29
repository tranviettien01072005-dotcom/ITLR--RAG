"""Regression: CLI `build_all_v2.py --with-cf` không được crash vì tuple sai shape.

Bug gốc: steps.append(("interactions_fake", module, None, False)) — 4 phần tử trong
khi cả hai vòng lặp unpack 3. Test này chạy dry-run (không cần model/artifacts) nên
bắt được lỗi ngay trong CI nhẹ.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/build_all_v2.py", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_dry_run_with_cf_lists_cf_steps():
    proc = _run("--dry-run", "--with-cf")
    assert proc.returncode == 0, proc.stderr
    assert "interactions_fake" in proc.stdout
    assert "cf_model" in proc.stdout


def test_dry_run_without_cf_stays_clean():
    proc = _run("--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "interactions_fake" not in proc.stdout
    assert "cf_model" not in proc.stdout
