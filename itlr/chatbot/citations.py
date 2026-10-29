"""Evidence identity checks, deliberately separate from semantic entailment."""
import math
import re
from urllib.parse import urlsplit

INSUFFICIENT_EVIDENCE = (
    "Mình chưa có đủ bằng chứng từ nguồn truy xuất để trả lời đáng tin cậy. "
    "Bạn có thể xem đoạn trích và liên kết nguồn bên dưới hoặc làm rõ câu hỏi."
)


def source_contract(source):
    item = {k: None if isinstance(v, float) and not math.isfinite(v) else v
            for k, v in source.get("item", source).items() if k != "full_text"}
    origin = item.get("origin")
    origin = origin if isinstance(origin, str) else "unknown"
    excerpt = source.get("excerpt", item.get("description", ""))
    excerpt = excerpt if isinstance(excerpt, str) else ""
    url = item.get("link", "")
    url = url if isinstance(url, str) else ""
    try:
        parsed = urlsplit(url)
        url = url if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username else ""
    except ValueError:
        url = ""
    real = (origin.startswith("crawl:") and bool(url and excerpt.strip())
            and source.get("evidence_kind") == "source_text")
    return {**item, "citation_id": f"item_id:{item['item_id']}",
            "chunk_id": source.get("chunk_id", f"{item['item_id']}:description"),
            "excerpt": excerpt, "url": url, "provenance": origin,
            "evidence_kind": "source_text" if real else "synthetic" if "synthetic" in origin else "unknown"}


def validate_citations(text, sources):
    raw_ids = re.findall(r"\[item_id:([^\]]*)\]", text or "")
    cited = sorted({int(x) for x in raw_ids if x.isascii() and x.isdigit()})
    allowed = {int(s["item_id"]) for s in sources if s["evidence_kind"] == "source_text"}
    invalid = sorted(set(cited) - allowed)
    malformed = any(not (x.isascii() and x.isdigit()) for x in raw_ids)
    status = "invalid" if invalid or malformed else "valid" if cited else "missing"
    return {"status": status, "cited_ids": cited, "invalid_ids": invalid,
            "malformed": malformed, "semantic_grounding": "not_verified"}
