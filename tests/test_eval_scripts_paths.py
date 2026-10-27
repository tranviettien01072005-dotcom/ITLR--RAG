"""Kiểm tra ROOT / sys.path của các script trong eval/ (bug: dirname x3 -> trỏ ra ngoài repo).

Hai lớp kiểm chứng:
1. FUNCTIONAL — nạp từng module eval/ trong subprocess với cwd = thư mục TẠM
   (bên ngoài repo). Module phải tự nạp được `itlr`. Nếu sys.path sai,
   `import itlr` sẽ ModuleNotFoundError: itlr.
2. STATIC — các đường dẫn SCRIPT mà eval/run_all.py liệt kê phải tồn tại thật,
   và ROOT phải trỏ đúng repo root.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"

# Thư viện "nặng" được import trong eval/*: nếu chưa cài cho phép skip (không phải lỗi của test).
HEAVY_BENIGN = {"pandas", "numpy", "scipy", "sklearn", "faiss", "hnswlib",
                "sentence_transformers", "torch", "lightgbm", "matplotlib", "shap", "openai"}

# Template chuỗi THƯỜNG (không f-string): @@PY@@ được thay bằng đường dẫn script thật khi chạy.
_IMPORT_PROBE = """import importlib.util, sys

HEAVY = %(heavy)r

spec = importlib.util.spec_from_file_location("ev_probe", r"@@PY@@")
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except ModuleNotFoundError as e:
    missing = e.name or ""
    if missing.split(".")[0] in HEAVY:
        print("SKIP_HEAVY", missing)
        sys.exit(0)
    print("FAIL_MOD", missing)
    sys.exit(3)
""" % {"heavy": sorted(HEAVY_BENIGN)}


def _eval_py_files() -> list[Path]:
    return sorted(p for p in EVAL_DIR.glob("*.py") if p.name != "__init__.py")


@pytest.mark.parametrize("py", _eval_py_files(), ids=lambda p: p.name)
def test_eval_module_imports_itlr_from_outside_repo(py: Path, tmp_path: Path):
    """Nạp module eval từ cwd ngoài repo -> buộc sys.path.insert trong file phải trúng ROOT."""
    script = tmp_path / "_import_probe.py"
    script.write_text(_IMPORT_PROBE.replace("@@PY@@", str(py)), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path, capture_output=True, text=True, timeout=180,
    )
    out = r.stdout or ""
    if "SKIP_HEAVY" in out:
        pytest.skip(f"cần thư viện nặng chưa cài: {out.strip()}")
    assert r.returncode == 0, (
        f"{py.name}: nạp module thất bại từ cwd ngoài repo. Bằng chứng:\n{r.stderr.strip()[:500]}"
    )


def test_run_all_scripts_exist():
    """Mọi file .py mà run_all.py chạy phải tồn tại (đường dẫn tương đối với repo root)."""
    src = (EVAL_DIR / "run_all.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    referenced: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value.endswith(".py"):
            referenced.add(node.value)

    assert referenced, "run_all.py phải tham chiếu các script eval"
    missing = [
        s for s in referenced
        if not (EVAL_DIR.parent / s).exists()
    ]
    assert not missing, (
        f"run_all.py tham chiếu script KHÔNG TỒN TẠI (path cũ scripts/eval?): {sorted(missing)}"
    )


def test_run_all_root_resolves_to_repo_root():
    """ROOT của run_all.py phải trỏ vào thư mục repo (chứa `itlr/`, `eval/`)."""
    src = (EVAL_DIR / "run_all.py").read_text(encoding="utf-8")
    roots = [
        n for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "ROOT" for t in n.targets)
    ]
    assert roots, "run_all.py phải định nghĩa ROOT"
    normalized = ast.unparse(roots[0].value)
    assert normalized.count("dirname") == 2, (
        f"ROOT phải dùng đúng 2 lần dirname (eval/ cách root 1 cấp), hiện dùng: {normalized}"
    )
