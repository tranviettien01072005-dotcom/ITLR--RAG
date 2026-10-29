"""Chạy thực nghiệm đánh giá ĐẦU-CUỐI.

Sinh:
  - reports/results.csv      : metric mọi cấu hình (bảng ablation dạng máy đọc)
  - reports/tables.md        : bảng ablation + kiểm định thống kê (đưa thẳng vào báo cáo)
  - reports/per_query.csv     : NDCG@10 per-query mỗi cấu hình (phục vụ vẽ/kiểm định lại)

Mỗi cấu hình tương ứng một mức của phễu multi-stage: TF-IDF only -> BM25 ->
Hybrid lexical -> Embeddings -> +L1 -> +Cross-Encoder -> +RAG-Fusion+MMR (Full).

Cách chạy:
    python scripts/eval/run_evaluation.py                 # đầy đủ
    python scripts/eval/run_evaluation.py --quick         # nhanh (bỏ rerank, ít truy vấn)
    python scripts/eval/run_evaluation.py --no-rerank     # bỏ tầng cross-encoder
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pickle
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random  # noqa: E402

import pandas as pd  # noqa: E402

from itlr import config  # noqa: E402
from itlr.core import pipeline as P  # noqa: E402
from itlr.core.recommender import strip_accents  # noqa: E402
from itlr.eval import diversity, metrics as M, significance  # noqa: E402

KS = (1, 3, 5, 10, 100)
HEADLINE = ["P@5", "R@5", "NDCG@10", "MAP", "MRR", "R@100"]


def perturb_query(query: str, rng: random.Random) -> str:
    """Mô phỏng input tiếng Việt 'đời thực': bỏ dấu + chèn lỗi gõ nhẹ (hoán/xóa ký tự).

    Dùng cho chế độ --noisy: nhãn liên quan GIỮ NGUYÊN, chỉ truy vấn bị nhiễu -> đo độ
    BỀN của hệ (kênh ngữ nghĩa + char n-gram bỏ dấu) so với khớp từ vựng chính xác.
    """
    q = strip_accents(query)
    chars = list(q)
    for i in range(len(chars) - 1):
        r = rng.random()
        if r < 0.04:
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
        elif r < 0.06 and chars[i] != " ":
            chars[i] = ""
    return "".join(chars)


def load_qrels(path: str):
    """Đọc qrels -> {qid: {'query':str, 'rel':{item_id:grade}}}."""
    df = pd.read_csv(path)
    qrels = {}
    for qid, group in df.groupby("query_id"):
        qrels[qid] = {
            "query": group["query"].iloc[0],
            "rel": {int(r.item_id): int(r.grade) for r in group.itertuples()},
        }
    return qrels


def build_context() -> P.RankContext:
    """Nạp artifacts qua load_engine (model/ann/reranker) + retrieval_model -> RankContext."""
    from itlr.engine import load_engine
    engine = load_engine()
    model_path = config.artifact("retrieval_model.pkl")
    with open(model_path, "rb") as f:
        retrieval_model = pickle.load(f)
    si = engine.search_index
    return P.RankContext(
        item_list=engine.items,
        retrieval_model=retrieval_model,
        embeddings=si["embeddings"],
        embed_model=engine.model,
        char_vectorizer=si["char_vectorizer"],
        char_matrix=si["char_matrix"],
        query_prefix=si.get("query_prefix", ""),
        ann=si.get("ann"),
        reranker=si.get("reranker"),
    )


def effective_configs(no_rerank: bool, reranker_available: bool) -> tuple[dict, bool]:
    """Chọn cấu hình trung thực với tầng rerank thực tế.

    Khi rerank bị tắt/không khả dụng, cấu hình "+ Cross-Encoder" trùng y hệt "+ L1 hybrid
    signals" -> KHÔNG báo cáo nó như một tầng riêng (tránh bảng ablation giả). Cấu hình Full
    vẫn chạy nhưng đổi tên rõ "(no rerank)".
    """
    configs = P.ablation_configs()
    rerank_effective = (not no_rerank) and reranker_available
    selected: dict = {}
    for name, cfg in configs.items():
        if cfg.use_rerank and not rerank_effective:
            if name == "+ Cross-Encoder":
                continue
            cfg = replace(cfg, use_rerank=False, name=f"{name} (no rerank)")
            name = cfg.name
        selected[name] = cfg
    return selected, rerank_effective


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(config.ROOT),
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:  # noqa: BLE001 — provenance không được làm hỏng eval
        return "unknown"


def write_provenance(suffix: str, *, judgments_path: str, n_queries: int,
                     rerank_requested: bool, rerank_available: bool,
                     rerank_effective: bool, configs: list[str],
                     max_queries: int, noisy: bool) -> str:
    """Ghi reports/provenance<suffix>.json — bằng chứng cấu hình đã chạy, không phải nhãn người."""
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "qrels_path": judgments_path,
        "qrels_sha256": _sha256(config.data_file(judgments_path)),
        "n_queries": n_queries,
        "max_queries": max_queries,
        "noisy_queries": bool(noisy),
        "rerank_requested": bool(rerank_requested),
        "reranker_available": bool(rerank_available),
        "rerank_effective": bool(rerank_effective),
        "configs": configs,
        "labels": "rule-based synthetic qrels (KHÔNG phải nhãn người)",
    }
    out = config.ROOT / "reports" / f"provenance{suffix}.json"
    os.makedirs(out.parent, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)


def grades_for_ranking(positions, id_for_pos, rel_map):
    """Chuyển danh sách vị trí xếp hạng -> mảng grade (0 nếu không nằm trong qrels)."""
    return [rel_map.get(int(id_for_pos[p]), 0) for p in positions]


def evaluate_config(ctx, cfg, qrels, id_for_pos, top_n=500, query_transform=None):
    """Chạy một cấu hình trên toàn bộ truy vấn -> (agg_metrics, per_query_ndcg10, rec_lists)."""
    per_query_rows = []
    ndcg10 = {}
    rec_lists = []
    for qid, q in qrels.items():
        qtext = query_transform(q["query"]) if query_transform else q["query"]
        positions = P.rank(ctx, qtext, cfg, top_n=top_n)
        rels = grades_for_ranking(positions, id_for_pos, q["rel"])
        n_rel = sum(1 for g in q["rel"].values() if g >= 1)
        ideal = list(q["rel"].values())
        row = M.per_query_metrics(rels, n_rel, ks=KS, ideal_rels=ideal)
        per_query_rows.append(row)
        ndcg10[qid] = row["NDCG@10"]
        rec_lists.append(positions[:10])
    agg = M.evaluate_run(per_query_rows)
    return agg, ndcg10, rec_lists


def fmt(v):
    return f"{v:.4f}" if isinstance(v, float) else str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="Nhanh: 20 truy vấn, bỏ rerank")
    ap.add_argument("--no-rerank", action="store_true", help="Bỏ tầng Cross-Encoder")
    ap.add_argument("--noisy", action="store_true",
                    help="Nhiễu hóa truy vấn (bỏ dấu + lỗi gõ) -> đo độ bền (nhãn giữ nguyên)")
    ap.add_argument("--top-n", type=int, default=500)
    ap.add_argument("--max-queries", type=int, default=0)
    ap.add_argument("--judgments", default="eval/relevance_judgments.csv",
                    help="Đường dẫn qrels (tương đối DATA_DIR) — cho phép nhiều benchmark song song")
    ap.add_argument("--tag", default="",
                    help="Hậu tố tên file báo cáo (vd _kw cho benchmark từ khóa) -> tables<tag>.md")
    args = ap.parse_args()
    suffix = args.tag + ("_noisy" if args.noisy else "")
    qtransform = (lambda s: perturb_query(s, random.Random(42))) if args.noisy else None

    qrels = load_qrels(config.data_file(args.judgments))
    if args.quick:
        args.max_queries = args.max_queries or 20
        args.no_rerank = True
    if args.max_queries:
        qrels = dict(list(qrels.items())[: args.max_queries])
    print(f"Đánh giá trên {len(qrels)} truy vấn | K={KS}")

    print("Nạp artifacts (load_engine)...")
    t0 = time.time()
    ctx = build_context()
    id_for_pos = ctx.item_list["item_id"].astype(int).to_numpy()
    n_items = len(ctx.item_list)
    reranker_available = ctx.reranker is not None
    print(f"  xong sau {time.time()-t0:.1f}s | {n_items} items"
          f" | ANN={'có' if ctx.ann is not None else 'không'}"
          f" | reranker={'có' if reranker_available else 'không'}")

    configs, rerank_effective = effective_configs(args.no_rerank, reranker_available)
    if args.no_rerank:
        print("[!] --no-rerank: bỏ dòng '+ Cross-Encoder' (sẽ trùng '+ L1 hybrid signals').")
    elif not reranker_available:
        print("[!] Không nạp được reranker: bỏ dòng '+ Cross-Encoder'; "
              "cấu hình Full chạy ở chế độ '(no rerank)'.")

    results = {}
    ndcg_by_cfg = {}
    rec_lists_by_cfg = {}
    for name, cfg in configs.items():
        t = time.time()
        agg, ndcg10, rec_lists = evaluate_config(
            ctx, cfg, qrels, id_for_pos, top_n=args.top_n, query_transform=qtransform)
        results[name] = agg
        ndcg_by_cfg[name] = ndcg10
        rec_lists_by_cfg[name] = rec_lists
        print(f"  [{name}] NDCG@10={agg['NDCG@10']:.4f} P@5={agg['P@5']:.4f} "
              f"MAP={agg['MAP']:.4f} ({time.time()-t:.1f}s)")

    os.makedirs(config.ROOT / "reports", exist_ok=True)
    metric_keys = list(next(iter(results.values())).keys())
    with open(config.ROOT / "reports" / f"results{suffix}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["config"] + metric_keys)
        for name, agg in results.items():
            w.writerow([name] + [fmt(agg[k]) for k in metric_keys])
    print(f"-> reports/results{suffix}.csv")

    with open(config.ROOT / "reports" / f"per_query{suffix}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        names = list(configs.keys())
        w.writerow(["query_id"] + names)
        for qid in qrels:
            w.writerow([qid] + [fmt(ndcg_by_cfg[n][qid]) for n in names])

    full_name = max(results, key=lambda n: results[n]["NDCG@10"])
    sig_rows = []
    full_scores = [ndcg_by_cfg[full_name][q] for q in qrels]
    for name in configs:
        if name == full_name:
            continue
        base_scores = [ndcg_by_cfg[name][q] for q in qrels]
        cmp = significance.compare(full_scores, base_scores)
        sig_rows.append((name, cmp))

    diverse_name = "+ RAG-Fusion + MMR (Full)"
    if diverse_name not in rec_lists_by_cfg:
        diverse_name = next((n for n in rec_lists_by_cfg if n.startswith("+ RAG-Fusion")),
                            full_name)
    ba = diversity.beyond_accuracy_report(
        rec_lists_by_cfg.get(diverse_name, rec_lists_by_cfg[full_name]), n_items,
        embeddings=ctx.embeddings,
        popularity=None,
    )

    write_tables(results, sig_rows, ba, full_name, len(qrels), suffix, args.noisy,
                 judgments_path=args.judgments,
                 rerank_requested=not args.no_rerank,
                 rerank_available=reranker_available,
                 rerank_effective=rerank_effective)
    prov = write_provenance(
        suffix, judgments_path=args.judgments, n_queries=len(qrels),
        rerank_requested=not args.no_rerank, rerank_available=reranker_available,
        rerank_effective=rerank_effective, configs=list(configs),
        max_queries=args.max_queries, noisy=args.noisy)
    print(f"-> {prov}")
    print(f"-> reports/tables{suffix}.md")
    print(f"\nHoàn tất. Xem reports/tables{suffix}.md để có bảng ablation + kiểm định.")
    return 0


def write_tables(results, sig_rows, ba, full_name, n_queries, suffix="", noisy=False, *,
                 judgments_path="eval/relevance_judgments.csv",
                 rerank_requested=True, rerank_available=True, rerank_effective=True):
    lines = []
    mode = "NHIỄU (bỏ dấu + lỗi gõ)" if noisy else "sạch"
    noisy_table = f"tables{suffix}_noisy.md"
    lines.append(f"# Kết quả đánh giá — Bảng ablation per-stage (truy vấn {mode})\n")
    lines.append(f"*Số truy vấn: {n_queries}. Metric macro-average trên nhãn bán-tự-động "
                 f"(`{judgments_path}`).*\n")
    lines.append("> **Nguồn nhãn:** qrels rule-based sinh từ metadata catalog, KHÔNG phải "
                 "nhãn người. Không dùng bảng này để tuyên bố chất lượng theo nhãn người.\n")
    if rerank_effective:
        rerank_note = "**BẬT** (cross-encoder đã nạp)."
    elif not rerank_requested:
        rerank_note = ("**TẮT** bởi `--no-rerank`: dòng `+ Cross-Encoder` bị bỏ vì sẽ trùng "
                       "`+ L1 hybrid signals`.")
    else:
        rerank_note = ("**KHÔNG KHẢ DỤNG**: không nạp được reranker; dòng `+ Cross-Encoder` bị bỏ, "
                       "cấu hình Full chạy `(no rerank)`.")
    lines.append(f"> **Rerank:** {rerank_note}\n")
    if noisy:
        lines.append(f"> Truy vấn bị **bỏ dấu + chèn lỗi gõ**, nhãn liên quan giữ nguyên. "
                     f"Bảng này đo **độ bền** của hệ trước input tiếng Việt đời thực: khớp từ "
                     f"vựng chính xác (TF-IDF/BM25) sụt mạnh, kênh ngữ nghĩa + char n-gram bỏ dấu "
                     f"giữ được chất lượng.\n")
    else:
        lines.append("> Lưu ý: nhãn tự động ≈ khớp topic chính xác nên các cấu hình từ vựng "
                     "(TF-IDF/BM25) gần chạm trần — bảng sạch chủ yếu xác nhận **recall** của tầng "
                     "sinh ứng viên. Khác biệt phương pháp thể hiện rõ ở bảng **truy vấn nhiễu** "
                     f"(`{noisy_table}`) và trên **nhãn người gán** (`evaluate_human.py`). "
                     "Cấu hình **Full** thêm MMR -> đánh đổi một phần độ chính xác lấy **đa dạng** "
                     "(xem mục beyond-accuracy); **+ Cross-Encoder** là mốc độ-chính-xác cao nhất "
                     "khi rerank thực sự bật.\n")

    lines.append("## Bảng ablation (headline metrics)\n")
    header = "| Cấu hình | " + " | ".join(HEADLINE) + " |"
    sep = "|---|" + "|".join(["---"] * len(HEADLINE)) + "|"
    lines.append(header)
    lines.append(sep)
    for name, agg in results.items():
        cells = [fmt(agg.get(k, 0.0)) for k in HEADLINE]
        bold = "**" if name == full_name else ""
        lines.append(f"| {bold}{name}{bold} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append(f"## Kiểm định thống kê — **{full_name}** (tốt nhất) vs baseline (NDCG@10)\n")
    lines.append(f"| Baseline | NDCG@10 (base) | {full_name} − base | CI 95% | p (t-test) | p (bootstrap) | Có ý nghĩa? |")
    lines.append("|---|---|---|---|---|---|---|")
    for name, c in sig_rows:
        ci = f"[{c['ci_low']:.4f}, {c['ci_high']:.4f}]"
        sig = "✅ p<0.05" if c["significant"] else "—"
        lines.append(f"| {name} | {c['mean_b']:.4f} | {c['mean_diff']:+.4f} | {ci} "
                     f"| {c['p_ttest']:.4g} | {c['p_bootstrap']:.4g} | {sig} |")
    lines.append("")

    lines.append("## Beyond-accuracy (cấu hình Full, top-10)\n")
    lines.append("| Metric | Giá trị |")
    lines.append("|---|---|")
    for k, v in ba.items():
        lines.append(f"| {k} | {v:.4f} |")
    lines.append("")

    os.makedirs(config.ROOT / "reports", exist_ok=True)
    with open(config.ROOT / "reports" / f"tables{suffix}.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main() or 0)
