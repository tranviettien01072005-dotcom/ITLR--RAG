"""Đánh giá INDEX V2 bằng số đo THẬT (không mô phỏng số trước).

Đo trên engine đang ACTIVE (nạp qua con trỏ CURRENT.json):
  1) Chất lượng retrieval giải quyết rule-based qrels (eval/relevance_judgments.csv —
     sinh bằng `make_judgments.py` với ITLR_ITEMS_CSV=var/data/itlr_v2_items.csv):
     Recall@5/10, MRR@10, NDCG@10 (grade 2/1).
     Ghi chú trung thực: qrels là nhãn metadata rule-based (ADR-004) — KHÔNG phải nhãn người.
  2) Latency đo thật: warm-up rồi time.perf_counter quanh engine.search — p50/p95 (ms).
     Reranker bật/tắt theo môi trường chạy; báo cáo ghi đúng trạng thái đó.
  3) Citation: gọi chatbot (template mode nếu không có LLM key — provider ghi rõ trong
     report); đếm `[item_id:X]` hợp lệ (X có và thuộc kết quả truy hồi của câu hỏi).

Chạy:
    python eval/eval_v2_real.py                      # dùng qrels V2 mặc định
    python eval/eval_v2_real.py --queries 30 --out reports/eval_v2_real.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from itlr import config  # noqa: E402

CITATION_RE = re.compile(r"\[item_id:([\dA-Fa-fx\-]+)\]*[\]\)]?", re.IGNORECASE)


def _ndcg_at_k(ranked_ids, rels, k):
    from itlr.eval.metrics import ndcg_at_k

    return ndcg_at_k([rels.get(int(iid), 0) for iid in ranked_ids[:k]],
                     k, ideal_rels=list(rels.values()))


def _mrr_at_k(ranked_ids, rels, k):
    for pos, iid in enumerate(ranked_ids[:k], 1):
        if rels.get(int(iid), 0) >= 1:
            return 1.0 / pos
    return 0.0


def _recall_at_k(ranked_ids, rels, k):
    good = [i for i, g in rels.items() if g >= 1]
    if not good:
        return None  # query không có nhãn tốt — loại khỏi trung bình
    hits = sum(1 for iid in ranked_ids[:k] if int(iid) in set(good))
    return hits / len(good)


def load_engine():
    from itlr.engine import load_engine

    eng = load_engine()
    return eng


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judgments", default="eval/relevance_judgments.csv")
    ap.add_argument("--queries", type=int, default=20, help="Số lần truy vấn latency (thực đo)")
    ap.add_argument("--chat-questions", type=int, default=5)
    ap.add_argument("--out", default="reports/eval_v2_real.md")
    args = ap.parse_args()

    eng = load_engine()
    items = eng.items
    n_items = len(items)
    cf_available = eng.cf_model is not None

    report: dict = {"n_items": int(n_items), "cf_available": bool(cf_available)}

    # ---- 1) retrieval quality trên qrels rule-based ----
    qrels_path = config.data_file(args.judgments)
    rels_by_q = {}
    if Path(qrels_path).is_file():
        df = pd.read_csv(qrels_path)
        for qid, grp in df.groupby("query_id"):
            rels_by_q[int(qid)] = {"query": str(grp["query"].iloc[0]),
                                   "rel": {int(r.item_id): int(r.grade)
                                           for r in grp.itertuples()}}
    else:
        print(f"[!] Không tìm thấy qrels {qrels_path} — sinh trước bằng make_judgments.py "
              "(với ITLR_ITEMS_CSV = catalog V2). Bỏ phần retrieval quality.")

    r5, r10, mrr, ndcg, n_eval = [], [], [], [], 0
    for q in rels_by_q.values():
        try:
            res = eng.search(q["query"], min_pct=10)["results"]
        except Exception as exc:  # noqa: BLE001 — lỗi một query không giết cả eval
            print(f"[!] search lỗi cho '{q['query'][:40]}': {exc}")
            continue
        ids = [int(x["item_id"]) for x in res]
        rec5 = _recall_at_k(ids, q["rel"], 5)
        rec10 = _recall_at_k(ids, q["rel"], 10)
        if rec5 is None:
            continue
        n_eval += 1
        r5.append(rec5)
        r10.append(rec10)
        mrr.append(_mrr_at_k(ids, q["rel"], 10))
        ndcg.append(_ndcg_at_k(ids, q["rel"], 10))
    if n_eval:
        report["retrieval"] = {
            "n_queries": n_eval,
            "recall@5": round(statistics.mean(r5), 4),
            "recall@10": round(statistics.mean(r10), 4),
            "MRR@10": round(statistics.mean(mrr), 4),
            "NDCG@10": round(statistics.mean(ndcg), 4),
            "note": "qrels rule-based trên metadata (không phải nhãn người người thật)",
        }

    # ---- 2) latency thực (warm-up rồi đo) ----
    qs = ["docker là gì", "học machine learning từ đầu", "python基础 pandas dataframe",
          "bảo mật web", "kubernetes deployment", "react hooks", "sql join",
          "linux command line", "ai chatbot", "git rebase"] * 3
    qs = [q for q in qs if q][:args.queries]
    lat = []
    for i, q in enumerate(qs):
        if i == 1:
            eng.search("warm-up", min_pct=10)  # nạp model/lazies trước khi đo
        t0 = time.perf_counter()
        eng.search(q, min_pct=10)
        lat.append((time.perf_counter() - t0) * 1000.0)
    lat.sort()
    if lat:
        report["latency_ms"] = {
            "p50": round(statistics.median(lat), 1),
            "p95": round(lat[int(0.95 * (len(lat) - 1))], 1),
            "mean": round(statistics.mean(lat), 1),
            "max": round(lat[-1], 1),
            "n_measured": len(lat),
        }

    # ---- 3) citation chatbot ----
    chat_note = "template mode (không LLM key)" if not (
        os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    ) else os.environ.get("DEEPSEEK_MODEL", "deepseek/cloud")
    from itlr.chatbot.chatbot import EducationalChatbot  # noqa: F401 (đảm bảo lớp nạp được)

    valid_items = set(int(x) for x in items["item_id"])
    cit_total = cit_valid = cit_in_ctx = 0
    chat_qs = ["Docker dùng để làm gì?", "Machine learning là gì?",
               "Nginx là gì và khi nào cần?", "Git rebase khác merge thế nào?",
               "SQL join có mấy loại?"][:args.chat_questions]
    for cq in chat_qs:
        out = eng.chat(cq, history=[])
        text = out.get("response", "") or ""
        recs = out.get("recommendations", []) or []
        ctx_ids = {int(r["item_id"]) for r in recs if str(r.get("item_id", "")).lstrip("-").isdigit()}
        for m in CITATION_RE.finditer(text):
            cit_total += 1
            s = m.group(1).strip("x")
            try:
                iid = int(s)
            except ValueError:
                continue
            cit_valid += int(iid in valid_items)
            cit_in_ctx += int(iid in ctx_ids)
    if cit_total:
        report["citations"] = {
            "total": cit_total,
            "valid_item_id": cit_valid,
            "in_context_of_reply": cit_in_ctx,
            "provider": chat_note,
        }

    out_md = Path(config.ROOT) / args.out
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# Đánh giá chỉ số V2 (thực đo)\n\n")
        f.write(f"- Ngày: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- Catalog: **{n_items} items** (legacy synthetic + crawl thật)\n")
        f.write(f"- CF available: **{cf_available}**\n")
        f.write(f"- Reranker: {'BẬT' if os.environ.get('DISABLE_RERANKER', '0') in ('0', '', 'false') else 'TẮT'}"
                f" — provider chatbot: {report['citations']['provider'] if cit_total else '—'}\n\n")
        for k, v in report.items():
            f.write(f"## {k}\n\n`{json.dumps(v, ensure_ascii=False, indent=2)}`\n\n")
        f.write("*Số trên là THỰC ĐO từ index đang chạy; không có mô phỏng.*\n")
    json_path = out_md.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[OK] Ghi {out_md} và {json_path}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
