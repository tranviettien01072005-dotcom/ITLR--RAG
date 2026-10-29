"""Build index V2 MỘT LỆNH — theo phiên bản, API sống không bị gián đoạn.

Chuỗi:
    1. catalog V2 = legacy CSV (synthetic, giữ nguyên item_id) + crawl SQLite (item_id
       ổn định bắt đầu sau floor legacy)  ->  var/data/itlr_v2_items.csv
    2. build vào THƯ MỤC STAGING (var/artifacts/versions/<id>/, KHÔNG đụng bản đang chạy):
       itlr.pipelines.build_model (dùng lại pipeline legacy, đầu vào là catalog CSV)
       + itlr.pipelines.build_embeddings_v2 (encode TỪNG CHUNK, mean + L2).
       Tùy chọn: --with-cf chạy generate_interactions + build_cf (dữ liệu tương tác GIẢ
       mô phỏng — chỉ để demo CF, không dùng làm dữ liệu thật).
    3. PROBE (itlr.indexv2.probe): validate > self-retrieval TF-IDF > engine subprocess.
       Probe fail ⇒ KHÔNG activate, rc=1, bản đang chạy giữ nguyên (an toàn).
    4. ACTIVATE (ghi var/artifacts/CURRENT.json nguyên tử) + garbage_collect giữ ~3 phiên.

Idempotent: chạy lại sinh phiên bản mới (timestamp), bản cũ có thể GC; không phá dữ liệu.

    python scripts/build_all_v2.py                    # build + probe + activate
    python scripts/build_all_v2.py --dry-run          # chỉ in plan
    python scripts/build_all_v2.py --no-activate      # build + probe, quyết định sau
    python scripts/build_all_v2.py --with-cf          # kèm bước CF (tương tác giả)
    python scripts/build_all_v2.py --online           # lần đầu: cho phép HF tải model
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _log(msg: str) -> None:
    """Log an toàn console (không để lỗi encoding làm chết build)."""
    try:
        print(msg)
    except Exception:
        sys.stdout.write(msg.encode("ascii", "replace").decode() + "\n")


def build_catalog(max_items=None) -> Path:
    """Bước 1: ghép catalog legacy + crawl → CSV V2. Trả về đường dẫn CSV."""
    from itlr.collect.normalize import build_catalog_v2
    from itlr import config

    out = config.DATA_DIR / "itlr_v2_items.csv"
    df = build_catalog_v2(out_path=out, max_items=max_items)
    if df.empty:
        raise RuntimeError("Catalog V2 rỗng — không có legacy CSV lẫn docs crawl hợp lệ. "
                           "Chạy `python scripts/collect_data.py` trước.")
    n_crawl = int((df["origin"].astype(str).str.startswith("crawl:")).sum())
    _log(f"[OK] Catalog V2: {len(df)} items (crawl thật: {n_crawl}) → {out}")
    return out


def run_step(module: str, env: dict, timeout: float) -> dict:
    """Chạy 1 pipeline subprocess (đầu ra stream live, KHÔNG capture để dễ debug)."""
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-m", module], cwd=str(ROOT),
                          env=env, timeout=timeout)
    return {"module": module, "rc": proc.returncode, "seconds": round(time.time() - t0, 1)}


def check_outputs(version_dir: Path, required: list[str]) -> list[str]:
    missing = [f for f in required if not (version_dir / f).is_file()]
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--real-only", action="store_true", help="Index only real collected sources; preserve synthetic legacy CSV")
    ap.add_argument("--dry-run", action="store_true", help="Chỉ in plan, không chạy")
    ap.add_argument("--no-activate", action="store_true",
                    help="Build + probe nhưng KHÔNG ghi CURRENT.json (quyết định activate sau)")
    ap.add_argument("--no-probe", action="store_true",
                    help="Bỏ probe (KHÔNG khuyến khích — activate yêu cầu probe ok)")
    ap.add_argument("--with-cf", action="store_true",
                    help="Kèm CF: generate_interactions (giả lập, seed 7) + build_cf")
    ap.add_argument("--online", action="store_true",
                    help="HF_HUB_OFFLINE=0 cho subprocess (lần đầu máy mới chưa có cache model)")
    ap.add_argument("--keep", type=int, default=3,
                    help="Số phiên bản cũ tối đa giữ lại sau GC (mặc định 3)")
    ap.add_argument("--max-items", type=int, default=None,
                    help="Giới hạn số item crawl đưa vào catalog (debug nhanh)")
    args = ap.parse_args()

    from itlr import config
    from itlr import versioning

    steps = [
        ("retrieval_model", "itlr.pipelines.build_model",
         ["item_list.pkl", "retrieval_model.pkl", "tfidf_vectorizer.pkl", "tfidf_matrix.pkl"]),
        ("embeddings_v2", "itlr.pipelines.build_embeddings_v2",
         ["embeddings.pkl", "search_meta.pkl", "chunk_meta.pkl",
          "char_vectorizer.pkl", "char_matrix.pkl"]),
    ]
    if args.with_cf:
        # Mọi step là bộ 3 (name, module, outputs). outputs=None nghĩa là bước phụ
        # (interactions CSV nằm ngoài staging) — chỉ kiểm tra ở nhánh bên dưới.
        steps.append(("interactions_fake", "itlr.pipelines.generate_interactions", None))
        steps.append(("cf_model", "itlr.pipelines.build_cf", ["cf_model.pkl"]))

    if args.dry_run:
        _log("Plan build V2 (dry-run):")
        for name, module, _outs in steps:
            _log(f"  - {name}: python -m {module}  (staging=var/artifacts/versions/<id>)")
        _log("  - probe (itlr.indexv2.probe) → activate (CURRENT.json) → garbage_collect(keep=%d)"
             % args.keep)
        _log(f"  CF: {'kèm theo (--with-cf — tương tác giả, KHÔNG dữ liệu thật)' if args.with_cf else 'bỏ qua (tùy chọn V2)'}")
        return 0

    if args.real_only:
        os.environ["ITLR_REAL_ONLY"] = "1"

    # ---- Bước 1: catalog ----
    t_build = time.time()
    try:
        catalog = build_catalog(args.max_items)
    except Exception as exc:  # noqa: BLE001 — lỗi build phải lộ rõ, không nuốt
        traceback.print_exc()
        _log(f"[LỖI] build catalog: {type(exc).__name__}: {exc}")
        return 1

    # ---- Bước 2: staging + subprocess pipelines ----
    staging = versioning.create_version_dir()
    version = staging.name
    env = os.environ.copy()
    env["ITLR_ARTIFACTS_DIR"] = str(staging)
    env["ITLR_ITEMS_CSV"] = str(catalog)
    if args.online:
        env["HF_HUB_OFFLINE"] = "0"
        env["TRANSFORMERS_OFFLINE"] = "0"
        env.setdefault("HF_HOME", str(ROOT / "var" / "hf"))
    env.setdefault("TOKENIZERS_PARALLELISM", "false")

    _log(f"[1/4] Catalog: {catalog}")
    _log(f"[2/4] Staging: {staging}")
    results = []
    for name, module, outs in steps:
        _log(f"--- [{name}] python -m {module}")
        try:
            r = run_step(module, env, timeout=7200.0)
        except subprocess.TimeoutExpired:
            _log(f"[LỖI] {name} quá 2h — abort")
            return 1
        results.append({"step": name, **r})
        if r["rc"] != 0:
            _log(f"[LỖI] {name} rc={r['rc']} — staging KHÔNG được activate.")
            (staging / "MANIFEST.json").write_text(json.dumps(
                {"probe": "fail", "reason": f"build step {name} rc={r['rc']}",
                 "steps": results}, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1
        _log(f"[OK] {name} ({r['seconds']}s)")
        if outs:  # None = bước phụ (interactions CSV ngoài staging) — chỉ kiểm tồn tại
            miss = check_outputs(staging, outs)
            if miss:
                _log(f"[LỖI] {name} không sinh đủ outputs: {miss}")
                return 1
    if args.with_cf and not config.INTERACTIONS_CSV.is_file():
        _log("[LỖI] --with-cf nhưng không tìm thấy file tương tác sau generate_interactions.")
        return 1

    # ---- Bước 3: probe ----
    _log("[3/4] Probe staging (validate + self-retrieval + engine subprocess)...")
    from itlr.indexv2 import probe

    ok, report = probe(staging, with_engine=not args.no_probe)
    if not ok:
        fails = [c for c in report.get("checks", []) if not c.get("ok")]
        _log(f"[LỖI] Probe FAIL — phiên bản {version} KHÔNG được activate. "
             f"Điểm hỏng: {json.dumps(fails, ensure_ascii=False)}")
        _log("Bản đang chạy giữ nguyên. Fix xong chạy lại build (mk version mới).")
        return 1
    _log(f"[OK] Probe ok: {json.dumps({k: report.get(k) for k in ('self_retrieval',)}, ensure_ascii=False)}")

    # ---- Bước 4: activate + GC ----
    summary = {"version": version, "dir": str(staging), "steps": results,
               "probe": "ok" if ok else "skipped",
               "activated": False, "catalog": str(catalog),
               "seconds": round(time.time() - t_build, 1)}
    if args.no_activate:
        summary["note"] = "KHÔNG activate (--no-activate). Kích hoạt by hand: " \
                          "python -c 'import json;from itlr import versioning as v;" \
                          f'print(v.activate(version="{version}"))'
        _log("[--no-activate] Probe ok nhưng không ghi CURRENT.json.")
    else:
        ver = versioning.activate(config.ARTIFACTS_DIR, version)
        versioning.garbage_collect(config.ARTIFACTS_DIR, keep=args.keep)
        summary["activated"] = True
        summary["activated_version"] = ver
        keeps = versioning.list_versions(config.ARTIFACTS_DIR)
        summary["kept_versions"] = keeps
        _log(f"[4/4] ACTIVATE phiên bản '{ver}' (giữ lại: {keeps})")
    out_path = config.DATA_DIR / "last_build.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _log("Build xong:\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    _log("Server nạp bản mới: POST /admin/reload (header X-Admin-Token) hoặc restart uvicorn.")
    return 0


if __name__ == "__main__":
    from itlr import config
    from itlr.locking import file_lock
    with file_lock(config.DATA_DIR / ".pipeline.lock"):
        sys.exit(main())
