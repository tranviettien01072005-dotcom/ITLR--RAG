"""Kiểm thử INDEX trước khi kích hoạt (probe) — dùng dữ liệu thật của thư mục staging.

Hai mức:
- validate_artifacts(): nhẹ (numpy + sklearn, KHÔNG nạp torch) — đủ để BẮT như hỏng
  dimension, hàng lệch, NaN, thiếu artifact → TRƯỚC KHI đụng API.
- self_retrieval_sanity(): tự-truy hồi bằng TF-IDF (không model nặng) — các tiêu đề
  mẫu phải tự tìm thấy chính nó ở top-k; đo tỉ lệ đạt, ngưỡng cấu hình.
- engine_probe(): NẶNG (nạp engine thật + torch) — chạy trong subprocess riêng
  với env ITLR_ARTIFACTS_DIR=staging; rc=0 nghĩa là engine sống được và /health tăng.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np

from itlr import config
from itlr.versioning import write_manifest

LOG = logging.getLogger("itlr.indexv2")

REQUIRED_FILES = ("item_list.pkl", "retrieval_model.pkl", "tfidf_vectorizer.pkl",
                  "tfidf_matrix.pkl", "embeddings.pkl", "search_meta.pkl",
                  "char_vectorizer.pkl", "char_matrix.pkl")


def validate_artifacts(artifacts: str | Path) -> tuple[bool, dict]:
    """Kiểm tra mọi artifact cần cho engine nạp được; trả (ok, report)."""
    artifacts = Path(artifacts)
    report: dict = {"dir": str(artifacts), "checks": []}

    def check(name, ok, detail=""):
        report["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)})

    missing = [f for f in REQUIRED_FILES if not (artifacts / f).is_file()]
    check("required_files", not missing, f"thiếu: {missing}")

    if missing:
        return False, report

    with open(artifacts / "item_list.pkl", "rb") as f:
        items = pickle.load(f)
    with open(artifacts / "embeddings.pkl", "rb") as f:
        emb = pickle.load(f)
    with open(artifacts / "search_meta.pkl", "rb") as f:
        meta = pickle.load(f)
    with open(artifacts / "retrieval_model.pkl", "rb") as f:
        retrieval_model = pickle.load(f)
    with open(artifacts / "char_matrix.pkl", "rb") as f:
        char_matrix = pickle.load(f)

    n = len(items)
    check("rows_align", emb.shape[0] == n == char_matrix.shape[0],
          f"items={n} emb={emb.shape[0]} char={char_matrix.shape[0]}")
    check("dim_match", emb.shape[1] == (meta.get("dim") or emb.shape[1]),
          f"emb={emb.shape[1]} meta={meta.get('dim')}")
    emb_arr = np.asarray(emb, dtype=np.float32)
    check("no_nan", bool(np.isfinite(emb_arr).all()), "NaN/Inf trong embeddings!")
    norms = np.linalg.norm(emb_arr, axis=1)
    ok_norm = bool(np.all(norms > 0.99) and np.all(norms < 1.01))
    check("norm_l2", ok_norm, f"norm range [{norms.min():.4f}, {norms.max():.4f}]")
    for key in ("vectorizers", "matrices", "bm25", "categories"):
        check(f"retrieval_model.{key}", key in retrieval_model,
              "thiếu khóa trong retrieval_model")
    ids = items["item_id"].to_numpy()
    check("item_ids_unique", len(set(ids.tolist())) == n, "item_id trùng lặp!")

    ok = all(c["ok"] for c in report["checks"])
    return ok, report


def self_retrieval_sanity(artifacts: str | Path, n_samples=30, top_k=5,
                          threshold=0.80, seed=20240623) -> tuple[float, dict]:
    """Tỉ lệ tự-truy hồi thành công (TF-IDF full — nhẹ, không model nặng)."""
    artifacts = Path(artifacts)
    with open(artifacts / "item_list.pkl", "rb") as f:
        items = pickle.load(f).reset_index(drop=True)
    with open(artifacts / "retrieval_model.pkl", "rb") as f:
        model = pickle.load(f)

    from sklearn.metrics.pairwise import cosine_similarity

    vec = model["vectorizers"]["full"]
    matrix = model["matrices"]["full"]
    rng = np.random.RandomState(seed)
    idxs = rng.choice(len(items), size=min(n_samples, len(items)), replace=False)
    hits = 0
    misses = []
    titles_db = items["title"].astype(str).tolist()
    for i in idxs:
        title = titles_db[int(i)]
        q = vec.transform([title])
        scores = cosine_similarity(q, matrix).ravel()
        top = np.argpartition(scores, -top_k)[-top_k:]
        found = int(i) in set(int(t) for t in top)
        hits += found
        if not found:
            misses.append(title[:60])
    ratio = hits / len(idxs)
    return ratio, {"n_samples": int(len(idxs)), "hits": hits,
                   "threshold": threshold, "misses": misses[:5]}


def probe(artifacts: str | Path, *, min_self_recall=0.8, with_engine=True) -> tuple[bool, dict]:
    """Chạy TOÀN BỘ probe và GHI MANIFEST (probe=ok/fail) trong thư mục artifacts."""
    artifacts = Path(artifacts)
    ok, report = validate_artifacts(artifacts)
    if ok:
        ratio, sr = self_retrieval_sanity(artifacts)
        report["self_retrieval"] = sr
        ok = ratio >= min_self_recall
        report["checks"].append({"check": "self_retrieval", "ok": ok,
                                 "detail": f"recall={ratio:.3f} min={min_self_recall}"})
        if ok and with_engine:
            ev = engine_probe(artifacts)
            report["engine_probe"] = ev
            ok = ev.get("ok", False)
            report["checks"].append({"check": "engine_probe", "ok": bool(ok),
                                     "detail": ev.get("msg", "")})
    write_manifest(artifacts, {"probe": "ok" if ok else "fail", "report": report})
    return ok, report


def engine_probe(artifacts: str | Path, timeout=600) -> dict:
    """Nạp engine THẬT (torch + faiss) trong subprocess: rc=0 ↔ artifacts dùng được."""
    import subprocess
    import sys

    script = (
        "import sys, os; os.environ['ITLR_ARTIFACTS_DIR']=r'%s'\n"
        "sys.path.insert(0, r'%s')\n"
        "from itlr.engine import load_engine\n"
        "eng = load_engine()\n"
        "res = eng.search('kubernetes', min_pct=10)\n"
        "assert res['results'], 'không có kết quả search'\n"
        "print('ENGINE_PROBE_OK', len(res['results']))\n"
    ) % (artifacts, str(config.ROOT))
    try:
        r = subprocess.run([sys.executable, "-c", script], capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "msg": "engine_probe timeout"}
    ok = ("ENGINE_PROBE_OK" in r.stdout)
    return {"ok": ok, "msg": (r.stdout.strip().splitlines()[-1] if r.stdout.strip()
                              else (r.stderr.strip().splitlines()[-1]
                                    if r.stderr.strip() else "no output")),
            "rc": r.returncode}
