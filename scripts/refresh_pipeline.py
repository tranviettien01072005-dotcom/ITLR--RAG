"""Pipeline refresh cho cron: thu thập → build index V2 → tổng kết JSON.

Mục đích: một lệnh duy nhất dành cho cron/systemd timer. An toàn khi lỗi:
- Nếu TẤT CẢ nguồn crawl lỗi (rc crawl=1) ⇒ KHÔNG build, giữ nguyên index đang chạy.
- Build V2 tự probe trước khi activate: probe fail ⇒ index đang chạy giữ nguyên.

    python scripts/refresh_pipeline.py                  # crawl tất cả nguồn; build nếu có docs mới
    python scripts/refresh_pipeline.py --force-build    # build dù không có docs mới
    python scripts/refresh_pipeline.py --sources devto-python,mdn-blog
    python scripts/refresh_pipeline.py --no-build       # chỉ crawl
Kết quả: var/data/collect/last_refresh.json (phục vụ giám sát / cảnh báo).
"""

from __future__ import annotations

import argparse
import os
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
    print(f"[i] $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=str(ROOT), timeout=timeout)


def _write_summary(summary: dict) -> None:
    try:
        out = ROOT / "var" / "data" / "collect" / "last_refresh.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 — file tổng kết lỗi không được giết refresh
        print(f"[!] Ghi last_refresh.json lỗi: {exc}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", default=None,
                    help="Phân tách phẩy: chỉ crawl các nguồn này (VD: devto-python,mdn-blog)")
    ap.add_argument("--force-build", action="store_true", help="Build dù không có docs mới")
    ap.add_argument("--no-build", action="store_true", help="Chỉ crawl, không build")
    ap.add_argument("--online", action="store_true",
                    help="Chuyển --online sang build_all_v2 (lần đầu, model chưa có cache)")
    ap.add_argument("--with-cf", action="store_true", help="Chuyển --with-cf sang build_all_v2")
    ap.add_argument("--keep", type=int, default=3, help="Số phiên bản artifacts giữ lại")
    ap.add_argument("--sync-web", action="store_true",
                    help="Sau export, chạy `npm run sync` để nạp catalog vào PostgreSQL "
                         "(cần DATABASE_URL; mặc định chỉ export + verify)")
    args = ap.parse_args()

    py = sys.executable
    summary: dict = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "crawl_rc": None,
                     "build_rc": None, "activated_version": None, "fresh_docs": None}

    # ---- 1. Thu thập (luôn chạy; kiểm state DB bên trong) ----
    collect_cmd = [py, "scripts/collect_data.py"]
    if args.sources:
        collect_cmd += ["--sources", args.sources]
    try:
        c = _run(collect_cmd, timeout=6 * 3600.0)
    except subprocess.TimeoutExpired:
        summary["crawl_rc"] = "timeout(6h)"
        print("[!] Crawl quá 6h — abort refresh.", flush=True)
        _write_summary(summary)
        return 1
    summary["crawl_rc"] = c.returncode
    if c.returncode != 0:
        print("[!] Crawl rc≠0 (mọi nguồn lỗi) ⇒ KHÔNG build — tránh phá index bằng rác.",
              flush=True)
        summary["build_rc"] = "skipped:collect_failed"
        _write_summary(summary)
        return 1

    if args.no_build:
        print("[--no-build] Dừng sau thu thập.", flush=True)
        _write_summary(summary)
        return 0

    # ---- 2. Quyết build: chỉ khi có docs mới/hay thay đổi ----
    build_trigger = args.force_build
    try:
        last = json.loads((ROOT / "var" / "data" / "collect" / "last_run.json")
                          .read_text(encoding="utf-8"))
        tot = last.get("totals", {})
        fresh = int(tot.get("new", 0) or 0) + int(tot.get("updated", 0) or 0)
        summary["fresh_docs"] = fresh
        if fresh > 0:
            build_trigger = True
            print(f"[i] Có {fresh} docs mới/cập nhật — build index.", flush=True)
        elif not args.force_build:
            print("[i] Không có docs mới/cập nhật — bỏ build (dùng --force-build để ép).",
                  flush=True)
    except FileNotFoundError:
        print("[i] last_run.json chưa tồn tại — coi như lần đầu chạy, ép build.", flush=True)
        build_trigger = True
    except Exception as exc:  # noqa: BLE001 — file hỏng không nên chặn refresh
        print(f"[!] Đọc last_run.json lỗi ({exc}) — ép build đề phòng.", flush=True)
        build_trigger = True

    if not build_trigger:
        _write_summary(summary)
        return 0

    # ---- 3. Build + probe + activate ----
    build_cmd = [py, "scripts/build_all_v2.py", "--keep", str(args.keep)]
    if args.online:
        build_cmd.append("--online")
    if args.with_cf:
        build_cmd.append("--with-cf")
    try:
        b = _run(build_cmd, timeout=24 * 3600.0)
    except subprocess.TimeoutExpired:
        summary["build_rc"] = "timeout(24h)"
        print("[!] Build quá 24h — abort.", flush=True)
        _write_summary(summary)
        return 1
    summary["build_rc"] = b.returncode
    try:
        lb = json.loads((ROOT / "var" / "data" / "last_build.json").read_text(encoding="utf-8"))
        summary["activated_version"] = lb.get("activated_version") or lb.get("version")
    except Exception as exc:  # noqa: BLE001 — metadata phụ trợ, đọc không được thì ghi lại
        summary["build_meta_error"] = str(exc)

    rc = b.returncode
    if b.returncode == 0:
        # The RAG index changed: refresh the Web catalog and verify it covers every item,
        # otherwise clicking a new course in search/chat returns 404 (DB has no row).
        for step, cmd in (("export", [py, "scripts/export_web_catalog.py", "--refresh"]),
                          ("verify", [py, "scripts/verify_web_catalog.py"])):
            try:
                r = _run(cmd, timeout=900)
                summary[f"{step}_rc"] = r.returncode
                if r.returncode != 0:
                    print(f"[!] {step} rc≠0 — Web catalog chưa đồng bộ; người dùng có thể gặp 404.",
                          flush=True)
                    rc = 1
            except subprocess.TimeoutExpired:
                summary[f"{step}_rc"] = "timeout"
                rc = 1
        if args.sync_web:
            if not os.environ.get("DATABASE_URL"):
                print("[!] --sync-web cần DATABASE_URL — bỏ qua bước PostgreSQL.", flush=True)
                rc = 1
            else:
                npm = "npm.cmd" if os.name == "nt" else "npm"
                r = subprocess.run([npm, "run", "sync"], cwd=str(ROOT / "web"),
                                   timeout=900)
                summary["sync_web_rc"] = r.returncode
                if r.returncode != 0:
                    print("[!] npm run sync rc≠0 — PostgreSQL chưa có catalog mới.", flush=True)
                    rc = 1

    _write_summary(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    from itlr.locking import file_lock
    with file_lock(ROOT / "var" / "data" / ".refresh.lock"):
        sys.exit(main())
