"""Đánh giá CHẤT LƯỢNG GENERATION của chatbot (RAG) — hoàn toàn offline, reproducible.

Các số liệu ĐO TRỰC TIẾP (không phụ thuộc LLM judge):
  - CITATION ACCURACY  : phần trăm mã [item_id:ID] trong câu trả lời (1) tồn tại trong
                         catalog, (2) nằm trong context mà mô hình được cấp. Bất kỳ ID sai
                         nào = HALLUCINATION REFERENCE (tuyệt đối, không xấp xỉ).
  - HALLUCINATION RATE : tỷ lệ câu trả lời chứa ÍT NHẤT một citation sai/context-lạc.
  - GROUNDEDNESS proxy : tỷ lệ n-gram (n=3) của câu trả lời xuất hiện trong nguồn đã cấp.
                         (XẤP XỈ — n-gram-based; LLM-judge cần API key riêng, ghi rõ.)
  - RELEVANCY proxy    : độ phủ token giữa câu hỏi và câu trả lời. (XẤP XỈ.)
  - REFUSAL RATE       : với bộ câu NGOÀI chủ đề, tỷ lệ câu trả lời có tín hiệu từ chối
                         phù hợp (không bày bạch khi không có bằng chứng).

Bộ câu hỏi mặc định: var/data/eval/generation_testset.csv (cột query,is_offtopic).
Chạy:
    python eval/eval_generation.py                 # chế độ template (không cần key)
    python eval/eval_generation.py --llm           # ép dùng LLM (cần DEEPSEEK/OPENAI key)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Không tải model báo tiếng - tắt log progress bar HF.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import pandas as pd  # noqa: E402

from itlr import config  # noqa: E402

CITE_RE = re.compile(r"\[item_id:(\d+)\]")

_REFUSAL_MARKERS = [
    "ngoài lĩnh vực", "ngoài phạm vi", "không thể tư vấn", "không thuộc",
    "chưa có dữ liệu", "không có dữ liệu tin cậy", "không có bằng chứng",
    "không tìm thấy", "chưa có trong", "mình chưa", "không chắc chắn",
]


def extract_citations(text: str) -> list[int]:
    """Trích mọi mã [item_id:ID] trong câu trả lời (danh sách int theo thứ tự xuất hiện)."""
    return [int(m) for m in CITE_RE.findall(str(text))]


def citation_stats(citations: list[int], context: set, valid: set) -> dict:
    """Thống kê citation của MỘT câu trả lời.

    valid_ratio    = phần ID có thật trong catalog   (bịa = 0)
    in_context_ratio = phần ID nằm trong context cấp cho model (context-lạc cũng là lỗi)
    """
    cs = list(citations)
    if not cs:
        return {"citations": 0, "valid_ratio": None, "in_context_ratio": None}
    n = len(cs)
    valid_hits = sum(1 for c in cs if c in valid)
    ctx_hits = sum(1 for c in cs if c in context)
    return {"citations": n,
            "valid_ratio": valid_hits / n,
            "in_context_ratio": ctx_hits / n}
def ngram_grounded_ratio(response_text: str, source_texts: list, n: int = 3) -> float:
    """Tỷ lệ n-gram của câu trả lời có mặt trong nguồn đã cấp (xấp xỉ groundedness)."""
    def tokenize(t):
        return re.findall(r"[a-z0-9à-ỹđ]+", str(t).lower())

    resp_tokens = tokenize(response_text)
    if len(resp_tokens) < n:
        return float("nan")
    src_ngrams = set()
    for src in source_texts:
        toks = tokenize(src)
        if len(toks) >= n:
            for i in range(len(toks) - n + 1):
                src_ngrams.add(tuple(toks[i:i + n]))
    if not src_ngrams:
        return float("nan")
    resp_ngrams = [tuple(resp_tokens[i:i + n]) for i in range(len(resp_tokens) - n + 1)]
    hits = sum(1 for g in resp_ngrams if g in src_ngrams)
    return hits / len(resp_ngrams)


def relevancy_proxy(query: str, response_text: str) -> float:
    """Xấp xỉ relevancy: |tokens(query) ∩ tokens(answer)| / |tokens(query)|."""
    def keywords(t):
        toks = re.findall(r"[a-z0-9à-ỹđ]+", str(t).lower())
        return {w for w in toks if len(w) > 2}

    q = keywords(query)
    if not q:
        return float("nan")
    a = keywords(response_text)
    return len(q & a) / len(q)


def is_refusal(response_text: str) -> bool:
    """Câu trả lời có tín hiệu TỪ CHỐI/THIẾU BẰNG CHỨNG phù hợp không."""
    low = str(response_text).lower()
    return any(m in low for m in _REFUSAL_MARKERS)


# --------------------------- integration runner --------------------------- #


def _default_testset_path() -> str:
    return str(config.data_file("eval/generation_testset.csv"))


DEFAULT_TESTSET_ROWS = [
    # (query, is_offtopic) — bộ câu hỏi mẫu cho generation eval (IT + ngoài chủ đề)
    ("Docker là gì và dùng để làm gì?", 0),
    ("Khoa học dữ liệu nên học gì trước cho người mới?", 0),
    ("Linux cron job hoạt động thế nào?", 0),
    ("SQL JOIN có mấy loại và khác nhau thế nào?", 0),
    ("An ninh mạng học lộ trình thế nào cho người mới?", 0),
    ("Python với Java khác nhau ra sao khi chọn học?", 0),
    ("React state hook hoạt động thế nào?", 0),
    ("Git merge với rebase khác gì nhau?", 0),
    ("Kubernetes triển khai microservices cần biết gì?", 0),
    ("Thread và process trong hệ điều hành khác nhau thế nào?", 0),
    ("Machine Learning loss function là gì?", 0),
    ("Học HTML CSS tuần đầu nên làm gì?", 0),
    ("TCP và UDP trong mạng máy tính khác gì nhau?", 0),
    ("Pentest (kiểm thử xâm nhập) bắt đầu chuẩn như thế nào?", 0),
    ("NLP pipeline cơ bản gồm những bước nào?", 0),
    ("Phân tích dữ liệu bằng Excel nên học từ đâu?", 0),
    ("Làm sao học AWS cho quản trị hệ thống hiệu quả?", 0),
    ("Khi nào nên dùng NoSQL và cần lưu ý gì?", 0),
    ("Học computer vision cho người mới nên bắt đầu thế nào?", 0),
    ("Soft skill nào quan trọng cho software engineer?", 0),
    ("Sự khác biệt giữa TensorFlow và PyTorch?", 0),
    ("Cách thiết kế API REST an toàn và rõ ràng?", 0),
    ("Học lập trình mobile nên chọn Android hay iOS trước?", 0),
    ("Vì sao DevOps giúp triển khai phần mềm nhanh hơn?", 0),
    ("Hướng dẫn tự học Python từ con số không?", 0),
    ("Cách viết CV xin việc IT cho fresher?", 0),
    ("Cloud computing có mấy loại dịch vụ chính?", 0),
    ("MongoDB và PostgreSQL nên chọn loại nào?", 0),
    ("Kiểm thử phần mềm unit test nên làm thế nào?", 0),
    ("Nấu cháo gà sao cho đậm đà và không bị cháy?", 1),
    ("Đội tuyển bóng đá Việt Nam giao hữu gần đây đấu ra sao?", 1),
    ("Cách chọn táo nhập khẩu sạch và an toàn cho gia đình?", 1),
    ("Du lịch Đà Nẵng nên đi mùa nào là lý tưởng nhất?", 1),
    ("Cảm cúm nên uống thuốc gì và ăn gì cho nhanh khỏi?", 1),
    ("Chính trị đảng Mỹ vận hành thế nào cho người mới tìm hiểu?", 1),
    ("Hướng dẫn nuôi cá vàng sinh sống được vài năm?", 1),
    ("Chứng khoán Việt Nam nên đầu tư thời điểm nào?", 1),
    ("Lời bài hát về tình yêu đã xa cảm động?", 1),
    ("Cách vượt khỏi khủng hoảng tình cảm sau chia tay?", 1),
    ("Dinh dưỡng áp dụng cho con 7 tháng cần bổ sung gì?", 1),
    ("Quy định giao thông đường bộ mới nhất về đi xe máy?", 1),
    ("Cách học toán hình học lớp 10 thích thú thật?", 1),
    ("Nên trồng cây gì trong phòng giúp không khí trong lành?", 1),
    ("Xu hướng thời trang thu đông cho nam giới?", 1),
    ("Cách pha cà phê muối ngon đúng chuẩn?", 1),
    ("Đạo nhảy hiện đại của Kpop học ở đâu?", 1),
    ("Cách làm mì Ý sốt bò bằm chuẩn vị?", 1),
    ("Mở tiệm trà sữa nên vốn bao nhiêu cho khởi đầu?", 1),
    ("Chăm sóc chó con 2 tháng tuổi cần biết gì?", 1),
    ("Yoga buổi sáng cho người cao tuổi nên tập thế nào?", 1),
]


def _build_testset(out_path: str) -> str:
    """Tạo generation_testset.csv nếu chưa có (deterministic bộ default)."""
    import csv

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query", "is_offtopic"])
        w.writerows(DEFAULT_TESTSET_ROWS)
    print(f"-> tạo bộ test mặc định: {out_path}")
    return out_path


def run_case(eng, query: str, is_offtopic: bool, mode: str) -> dict:
    """Chạy 1 case qua engine, trả về metric row.

    mode chỉ đánh dấu NHẪN report: eng.chat() tự quyết định LLM/template theo cấu hình
    (không có cơ chế "ép LLM" bên ngoài) — vì vậy main() fail-fast khi --llm mà thiếu key.
    """
    valid_ids = set(int(i) for i in eng.items["item_id"].astype(int))
    result = eng.chat(query)

    response = str(result.get("response", ""))
    sources = result.get("sources") or []
    context_ids = set()
    for s in sources:
        try:
            context_ids.add(int(s.get("item_id")))
        except (TypeError, ValueError, AttributeError):
            continue

    stats = citation_stats(extract_citations(response),
                           context=context_ids, valid=valid_ids)
    source_texts = []
    for s in sources:
        # chat() trả sources là list ITEM DICT trực tiếp (không bọc {"item": ...})
        it = s.get("item") or s
        source_texts.append(" ".join(str(it.get(k, "")) for k in
                                     ("title", "topics", "category", "description")))
    tried = {
        "query": query, "is_offtopic": int(is_offtopic), "mode": mode,
        "intent": result.get("intent"),
        "citations": stats["citations"],
        "citation_valid_ratio": stats["valid_ratio"],
        "citation_in_context_ratio": stats["in_context_ratio"],
        "hallucination": int(stats["citations"] > 0 and (stats["valid_ratio"] or 1.0) < 1.0),
        "groundedness_ngram": ngram_grounded_ratio(response, source_texts),
        "relevancy": relevancy_proxy(query, response),
        "refusal": int(is_refusal(response)),
        "response_chars": len(response),
    }
    return tried


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--llm", action="store_true",
                    help="Ép dùng LLM (cần key); mặc định template offline")
    ap.add_argument("--testset", default=_default_testset_path())
    ap.add_argument("--out-tag", default="template")
    args = ap.parse_args()

    if not os.path.exists(args.testset):
        _build_testset(args.testset)
    df = pd.read_csv(args.testset)

    from itlr.engine import load_engine
    eng = load_engine()

    mode = "llm" if args.llm else "template"
    if args.llm:
        # KHÔNG fallback âm thầm: --llm phải thực sự dùng LLM; thiếu key là LỖI (rc=2),
        # tránh kết quả "llm" thực chất template (sai lệch số liệu, vi phạm tính trung thực).
        from itlr.chatbot import llm_client
        if not llm_client.llm_available():
            print("[!] --llm yêu cầu LLM nhưng chưa cấu hình (DEEPSEEK_API_KEY / "
                  "OPENAI_API_KEY / Ollama không chạy). Bỏ --llm để chạy template offline.")
            return 2

    rows = []
    for _, r in df.iterrows():
        rows.append(run_case(eng, str(r["query"]), bool(r["is_offtopic"]), mode))
        print(".", end="", flush=True)
    print()

    out_df = pd.DataFrame(rows)
    reports = config.ROOT / "reports"
    os.makedirs(reports, exist_ok=True)
    csv_path = reports / f"generation_eval_{args.out_tag}.csv"
    out_df.to_csv(csv_path, index=False)
    print(f"-> {csv_path}")

    off = out_df[(out_df.is_offtopic == 1) & (out_df.refusal == 0)]
    off_refusal = out_df[(out_df.is_offtopic == 1) & (out_df.refusal == 1)]
    ontopic = out_df[out_df.is_offtopic == 0]
    md = [
        "# Đánh giá chất lượng GENERATION (chatbot RAG)",
        f"*Mode: **{mode}** — {'câu trả lời do LLM sinh (cần key riêng)' if mode == 'llm' else 'bộ tổng hợp template KHÔNG dùng LLM (offline)'}.*",
        "*Các số GROUNDEDNESS / RELEVANCY là XẤP XỈ rule-based (n-gram, token-overlap); "
        "HALLUCINATION + CITATION ACCURACY là đo TRỰC TIẾP trên ID nguồn (không xấp xỉ).*",
        "",
        f"- **Citation**: {int(out_df.citations.sum())} mã cite trong {len(out_df)} câu trả lời;"
        f" valid = {(out_df.citation_valid_ratio.dropna().mean() * 100):.1f}%"
        f" | in-context = {(out_df.citation_in_context_ratio.dropna().mean() * 100):.1f}%"
        f" (tính khi có cite)",
        f"- **Hallucination rate** (câu có >=1 cite không có thật): "
        f"{(out_df.hallucination.mean() * 100):.1f}% ({int(out_df.hallucination.sum())}/{len(out_df)})",
        f"- **Groundedness proxy** (n-gram trúng nguồn): "
        f"{out_df.groundedness_ngram.dropna().mean():.3f}",
        f"- **Relevancy proxy**: {out_df.relevancy.dropna().mean():.3f}",
        f"- **Refusal với câu NGOÀI chủ đề**: {len(off_refusal)}/{len(off) + len(off_refusal)} "
        f"= {(len(off_refusal) / max(len(off) + len(off_refusal), 1) * 100):.1f}%",
        f"- Câu hỏi IT bị từ chối NHẦM (false refusal): "
        f"{int(out_df[(out_df.is_offtopic == 0) & (out_df.refusal == 1)].shape[0])} "
        f"/ {len(ontopic)} (càng thấp càng tốt)",
        "",
        "| query | is_offtopic | intent | cites | valid% | in-ctx% | halluc | grounded | refusal |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in out_df.iterrows():
        md.append(
            f"| {str(r['query'])[:42]} | {int(r.is_offtopic)} | {r.intent} | {int(r.citations)} |"
            f" {'-' if pd.isna(r.citation_valid_ratio) else round(100 * r.citation_valid_ratio)} |"
            f" {'-' if pd.isna(r.citation_in_context_ratio) else round(100 * r.citation_in_context_ratio)} |"
            f" {int(r.hallucination)} |"
            f" {'-' if pd.isna(r.groundedness_ngram) else round(r.groundedness_ngram, 2):.2f} |"
            f" {int(r.refusal)} |")
    md_path = reports / f"generation_eval_{args.out_tag}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"-> {md_path}")

    json_path = reports / f"generation_eval_{args.out_tag}.json"

    def _finite(x) -> "float | None":
        """NaN (khi cột trống) -> null: JSON output luôn là JSON hợp lệ."""
        return None if pd.isna(x) else round(float(x), 6)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"mode": mode, "n": len(out_df),
                   "mean_valid_ratio": _finite(out_df.citation_valid_ratio.dropna().mean()),
                   "mean_in_context_ratio":
                       _finite(out_df.citation_in_context_ratio.dropna().mean()),
                   "hallucination_rate": _finite(out_df.hallucination.mean()),
                   "groundedness": _finite(out_df.groundedness_ngram.dropna().mean()),
                   "relevancy": _finite(out_df.relevancy.dropna().mean())}, f, indent=2)
    print(f"-> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
