"""Build embeddings + ANN V2 — có CHUNKING cho tài liệu dài (khác build_embeddings legacy).

Khác biệt so với bản legacy:
- Text mỗi item được CHIA ĐOẠN (itlr.collect.chunk.chunk_text) rồi encode TỪNG đoạn;
  vector item = mean các vector đoạn → chuẩn hóa L2 (giữ 1:1 hàng ↔ item — hợp đồng
  search hiện có không đổi), tài liệu dài không mất đuôi.
- Ghi thêm `chunk_meta.pkl`: (item_id, chunk_idx, chunk_text) phục vụ trích dẫn chi tiết.
- Ghi MANIFEST đầu-level cho quy trình theo phiên bản: n_items, n_chunks, dim,
  model, hash nguồn, thời gian.

Chạy: ITLR_ARTIFACTS_DIR=<staging> ITLR_ITEMS_CSV=<catalog.csv> \
      python -m itlr.pipelines.build_embeddings_v2
"""

from __future__ import annotations

import os
import pickle
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import hashlib  # noqa: E402

import numpy as np  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402

from itlr import config  # noqa: E402
from itlr.collect.chunk import chunk_text  # noqa: E402
from itlr.core.embeddings import encode_passages, load_model, meta_from_preset, resolve_preset  # noqa: E402
from itlr.core.recommender import strip_accents  # noqa: E402

CHUNK_MAX_CHARS = 900
CHUNK_OVERLAP = 120


def build_text(row) -> str:
    """Câu tự nhiên để encode (lowercase — khớp lưu ý search_by_embedding legacy)."""
    return (
        f"{str(row['title']).strip()}. "
        f"Thể loại: {str(row['category']).strip()}. "
        f"Chủ đề: {str(row['topics']).strip()}. "
        f"{str(row['description']).strip()}"
    ).lower()


def build_char_index(items, out_dir: str):
    """Char n-gram TF-IDF (bỏ dấu) trên title+topics+category — như bản legacy."""
    searchable = [
        strip_accents(f"{r['title']} {r['topics']} {r['category']}")
        for _, r in items.iterrows()
    ]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    matrix = vec.fit_transform(searchable)
    with open(os.path.join(out_dir, "char_vectorizer.pkl"), "wb") as f:
        pickle.dump(vec, f)
    with open(os.path.join(out_dir, "char_matrix.pkl"), "wb") as f:
        pickle.dump(matrix, f)
    print(f"[OK] char_vectorizer.pkl + char_matrix.pkl {matrix.shape}")


def main() -> int:
    out_dir = str(config.current_dir())
    with open(os.path.join(out_dir, "item_list.pkl"), "rb") as f:
        items = pickle.load(f).reset_index(drop=True)
    n = len(items)
    preset = resolve_preset()
    print(f"[i] Items: {n} — model: {preset['model_name']} — dir: {out_dir}")

    from sentence_transformers import SentenceTransformer  # nạp sau khi print cấu hình

    model = load_model(preset["model_name"])

    t0 = time.time()
    # ---- chunking + encode từng đoạn (tài liệu dài không bị cắt đuôi) ----
    texts = [build_text(row) for _, row in items.iterrows()]
    all_passages: list[str] = []
    owner: list[int] = []          # index item mà đoạn thuộc về
    chunk_meta_rows: list[dict] = []
    for i, (_, row) in enumerate(items.iterrows()):
        chunks = chunk_text(texts[i], max_chars=CHUNK_MAX_CHARS,
                            overlap_chars=CHUNK_OVERLAP) or [texts[i]]
        for j, ch in enumerate(chunks):
            all_passages.append(ch)
            owner.append(i)
            chunk_meta_rows.append({"item_id": int(row["item_id"]), "chunk_idx": j,
                                    "chunk_text": ch[:400]})
    print(f"[i] Đoạn (chunks): {len(all_passages)} từ {n} items "
          f"(trung bình {len(all_passages)/max(1, n):.2f}/item)")

    chunk_embs = encode_passages(model, all_passages, preset,
                                 batch_size=32, show_progress_bar=True)
    # ---- gộp mean + chuẩn hóa L2 về đúng n hàng ----
    emb = np.zeros((n, chunk_embs.shape[1]), dtype=np.float32)
    counts = np.zeros(n, dtype=np.int64)
    for pos, o in enumerate(owner):
        emb[o] += chunk_embs[pos]
        counts[o] += 1
    counts[counts == 0] = 1
    emb /= counts.reshape(-1, 1).astype(np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    emb = (emb / norms).astype(np.float32)
    print(f"[OK] Encode xong {time.time()-t0:.1f}s — dim {emb.shape[1]}")

    with open(os.path.join(out_dir, "embeddings.pkl"), "wb") as f:
        pickle.dump(emb, f)
    with open(os.path.join(out_dir, "search_meta.pkl"), "wb") as f:
        pickle.dump(meta_from_preset(preset), f)
    with open(os.path.join(out_dir, "chunk_meta.pkl"), "wb") as f:
        pickle.dump({"rows": chunk_meta_rows, "n_items": n, "dim": int(emb.shape[1])}, f)

    # ---- ANN ----
    backend = None
    try:
        from itlr.core.ann import build_ann

        backend = build_ann(emb, out_dir)
        if backend:
            print(f"[OK] ANN ({backend}) → ann_index.*")
        else:
            print("[!] Bỏ qua ANN (chưa cài faiss/hnswlib) — runtime sẽ brute-force.")
    except Exception as exc:  # noqa: BLE001
        print(f"[!] Bỏ qua ANN do lỗi: {exc}")

    build_char_index(items, out_dir)

    import json

    catalog_hash = ""
    cat_path = str(config.ITEMS_CSV)
    if os.path.isfile(cat_path):
        h = hashlib.sha256()
        with open(cat_path, "rb") as f:
            for blk in iter(lambda: f.read(1 << 20), b""):
                h.update(blk)
        catalog_hash = h.hexdigest()[:16]
    manifest = {
        "step": "embeddings_v2",
        "model_name": preset["model_name"],
        "n_items": n,
        "n_chunks": len(all_passages),
        "dim": int(emb.shape[1]),
        "ann_backend": backend,
        "items_csv": cat_path,
        "catalog_sha256_16": catalog_hash,
        "ok": True,
    }
    with open(os.path.join(out_dir, "EMBEDDINGS_MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("[OK] Hoàn tất build_embeddings_v2:\n" + json.dumps(
        manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
