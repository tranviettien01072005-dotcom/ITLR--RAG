"""Chỉ mục vector ANN (Approximate/Exact Nearest Neighbor) kiểu vector-DB.

Dùng FAISS (IndexFlatIP — inner product trên vector đã chuẩn hóa = cosine, chính xác
và không cần train) làm tầng truy hồi dày (dense) tốc độ cao, mở rộng được lên hàng
triệu mục. Nếu FAISS chưa cài (vd Python quá mới chưa có wheel) -> fallback hnswlib
-> fallback None (caller tự brute-force bằng nhân ma trận như cũ).

Mọi hàm fail-safe: lỗi/không có thư viện -> trả None, hệ thống vẫn chạy.
Đường dẫn artifact mặc định lấy từ itlr.config.ARTIFACTS_DIR (trung tâm, không phụ
thuộc cwd) — KHÔNG hardcode thư mục tương đối "artifacts/".
"""

import pickle

import numpy as np

from itlr import config

ANN_INDEX_FAISS = "ann_index.faiss"
ANN_INDEX_HNSW = "ann_index.hnsw"
ANN_META = "ann_meta.pkl"


def _dir(artifacts_dir) -> str:
    """Quyết định thư mục artifact: caller truyền -> dùng; không -> config.ARTIFACTS_DIR."""
    return str(artifacts_dir) if artifacts_dir is not None else str(config.ARTIFACTS_DIR)


def _try_import_faiss():
    try:
        import faiss  # noqa: F401
        return faiss
    except Exception:
        return None


def _try_import_hnswlib():
    try:
        import hnswlib  # noqa: F401
        return hnswlib
    except Exception:
        return None


def build_ann(embeddings, artifacts_dir=None):
    """Xây chỉ mục từ ma trận embeddings (n x d, đã chuẩn hóa L2). Ưu tiên FAISS -> hnswlib -> None."""
    embeddings = np.ascontiguousarray(embeddings.astype(np.float32))
    n, d = embeddings.shape
    out_dir = _dir(artifacts_dir)

    faiss = _try_import_faiss()
    if faiss is not None:
        index = faiss.IndexFlatIP(d)
        index.add(embeddings)
        faiss.write_index(index, f"{out_dir}/{ANN_INDEX_FAISS}")
        with open(f"{out_dir}/{ANN_META}", "wb") as f:
            pickle.dump({"backend": "faiss", "n": n, "dim": d}, f)
        return "faiss"

    hnswlib = _try_import_hnswlib()
    if hnswlib is not None:
        index = hnswlib.Index(space="cosine", dim=d)
        index.init_index(max_elements=n, ef_construction=200, M=16)
        index.add_items(embeddings, np.arange(n))
        index.set_ef(64)
        index.save_index(f"{out_dir}/{ANN_INDEX_HNSW}")
        with open(f"{out_dir}/{ANN_META}", "wb") as f:
            pickle.dump({"backend": "hnswlib", "n": n, "dim": d}, f)
        return "hnswlib"

    return None


def load_ann(artifacts_dir=None):
    """Nạp chỉ mục đã build. Trả về dict {backend, index} hoặc None nếu không có/không nạp được."""
    out_dir = _dir(artifacts_dir)
    meta_path = f"{out_dir}/{ANN_META}"
    try:
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)
    except Exception:
        return None

    backend = meta.get("backend")
    if backend == "faiss":
        faiss = _try_import_faiss()
        if faiss is None:
            return None
        path = f"{out_dir}/{ANN_INDEX_FAISS}"
        try:
            return {"backend": "faiss", "index": faiss.read_index(path)}
        except Exception:
            return None  # file hỏng/thiếu -> fail-safe (không làm rơi engine)

    if backend == "hnswlib":
        hnswlib = _try_import_hnswlib()
        if hnswlib is None:
            return None
        path = f"{out_dir}/{ANN_INDEX_HNSW}"
        try:
            index = hnswlib.Index(space="cosine", dim=meta["dim"])
            index.load_index(path, max_elements=meta["n"])
            index.set_ef(64)
            return {"backend": "hnswlib", "index": index}
        except Exception:
            return None

    return None


def ann_search(ann, query_vec, top_n=200):
    """Tìm top_n láng giềng. Trả về (indices: np.int64[], scores: cosine float[]) hoặc None."""
    if ann is None:
        return None
    q = np.ascontiguousarray(np.asarray(query_vec, dtype=np.float32).reshape(1, -1))
    try:
        if ann["backend"] == "faiss":
            scores, idx = ann["index"].search(q, top_n)
            return idx[0], scores[0]
        if ann["backend"] == "hnswlib":
            labels, distances = ann["index"].knn_query(q, k=top_n)
            return labels[0].astype(np.int64), (1.0 - distances[0])
    except Exception:
        return None
    return None
