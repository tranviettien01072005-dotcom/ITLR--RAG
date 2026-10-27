"""Build TOÀN BỘ artifacts một lệnh — server (uvicorn) chạy được ngay sau đó.

Chuỗi: catalog -> retrieval -> embeddings/ANN -> CF (engine sẽ nạp artifacts lúc
server khởi động; không có bước kiểm-nạp riêng ở đây).

Idempotent: bỏ qua đã build (có flag --force để build lại hết).

    python scripts/build_all.py            # build phần thiếu
    python scripts/build_all.py --force    # build lại TẤT CẢ
    python scripts/build_all.py --dry-run  # chỉ in kế hoạch (không chạy)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# python scripts/build_all.py đặt sys.path[0] = scripts/ — thêm repo root để import itlr.
sys.path.insert(0, str(ROOT))

# (tên bước, module -m, các artifact khóa coi như "đã xong")
STEPS = [
    ("retrieval_model", "itlr.pipelines.build_model",
     ["item_list.pkl", "retrieval_model.pkl", "tfidf_vectorizer.pkl", "tfidf_matrix.pkl"]),
    ("embeddings_ann", "itlr.pipelines.build_embeddings",
     ["embeddings.pkl", "search_meta.pkl", "char_vectorizer.pkl", "char_matrix.pkl"]),
    ("collaborative", "itlr.pipelines.build_cf",
     ["cf_model.pkl"]),
]


def _artifacts_dir() -> Path:
    import itlr.config as config
    return Path(str(config.ARTIFACTS_DIR))


def plan(force: bool) -> list[tuple[str, str]]:
    have = _artifacts_dir()
    todo = []
    for name, module, outputs in STEPS:
        done = all((have / f).exists() for f in outputs)
        if not done or force:
            todo.append((name, module))
    return todo


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="Build lại cả khi artifact đã tồn tại")
    ap.add_argument("--dry-run", action="store_true", help="Chỉ in các bước sẽ chạy")
    ap.add_argument("--step", action="append", default=[],
                    help="Chỉ chạy bước chỉ định (tên trong kế hoạch), có thể lặp")
    args = ap.parse_args()

    todo = plan(args.force)
    if args.step:
        allowed = set(args.step)
        todo = [(n, m) for n, m in todo if n in allowed]
        unknown = allowed - {n for n, _, _ in STEPS}
        if unknown:
            print(f"[!] --step không hợp lệ: {sorted(unknown)}. "
                  f"Các bước hợp lệ: {[n for n, _, _ in STEPS]}")
            return 2

    print(f"Artifacts dir: {_artifacts_dir()}")
    if not todo:
        print("Tất cả artifact đã sẵn sàng — không cần build gì (dùng --force để build lại).")
        return 0

    print("Kế hoạch build:")
    for name, module in todo:
        print(f"  - {name}  ($ python -m {module})")
    if args.dry_run:
        print("--dry-run: KHÔNG chạy thật. Bỏ --dry-run để build.")
        print(f"[dry-run] tổng kết: {len(todo)} bước sẽ chạy (không chạy thật).")
        return 0

    failed = []
    for name, module in todo:
        print(f"\n{'='*66}\n[{name}] python -m {module}\n{'='*66}")
        t0 = time.time()
        r = subprocess.run([sys.executable, "-m", module], cwd=str(ROOT))
        dt = time.time() - t0
        ok = r.returncode == 0
        print(f"[{'OK' if ok else 'LỖI'}] {name} mất {dt:.1f}s")
        if not ok:
            failed.append(f"{name} (python -m {module}, rc={r.returncode})")

    if failed:
        print("\nBƯỚC LỖI:", "; ".join(failed))
        print("Khắc phục xong có thể chạy lại: python scripts/build_all.py")
        return 1
    print("\nBuild xong toàn bộ. Chạy server: uvicorn itlr.api.server:app --port 8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
