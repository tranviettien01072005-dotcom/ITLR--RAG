"""Engine nạp artifacts & expose API thuần Python — ĐỘC LẬP framework (không Streamlit).

Đây là đường nạp artifacts DUY NHẤT cho mọi lớp trình bày (web API FastAPI, CLI, hay
code khác). Toàn bộ giao diện Streamlit cũ đã được gỡ bỏ — hệ thống chạy thuần FastAPI.

Toàn bộ logic lõi (truy hồi ngữ nghĩa, RAG, chatbot có cổng off-topic + khái niệm-trước,
Collaborative Filtering) được giữ nguyên — engine chỉ gói lại cho tiện gọi.
"""

import logging
import os
import pickle
import threading
from pathlib import Path

from itlr import config
from itlr.core.recommender import recommend_for_user, search_by_embedding
from itlr.retrieval.service import DEFAULT_SEARCH_MIN_PCT

LOG = logging.getLogger("itlr.engine")


class CFUnavailable(RuntimeError):
    """Collaborative Filtering chưa được build (cf_model.pkl không có) — CF là TUỲ CHỌN V2."""


class RecommenderEngine:
    """Gói gọn artifacts + 3 năng lực: tìm kiếm ngữ nghĩa · chatbot · gợi ý CF."""

    def __init__(self, items, model, search_index, cf_model, chatbot):
        self.items = items
        self.model = model
        self.search_index = search_index
        self.cf_model = cf_model   # None khi chưa build CF (tính năng tùy chọn)
        self.chatbot = chatbot

    def search(self, query, item_type=None, min_pct=DEFAULT_SEARCH_MIN_PCT):
        """Tìm kiếm ngữ nghĩa — logic hiểu truy vấn của tab Tìm kiếm.

        Mở rộng viết tắt + sửa lỗi chính tả + bổ sung tên/chủ đề khái niệm (nếu truy vấn
        là một khái niệm trong glossary), rồi truy hồi qua `search_by_embedding`.
        Trả dict: {results, display, note, corrected}.
        """
        from itlr.chatbot.knowledge_base import CONCEPTS, safe_concept_match, _key
        from itlr.chatbot.query_understanding import understand_query

        if not query or not query.strip():
            return {"results": [], "display": "", "note": "", "corrected": False}

        understanding = understand_query(query, self.search_index.get("vocab") or frozenset())
        search_query = query
        if understanding["corrections"] or understanding["expansions"]:
            search_query = understanding["corrected"] or query

        matched = None
        mkey = safe_concept_match(query)
        # Expand bare aliases, not a specific question merely mentioning the concept.
        concept = CONCEPTS[mkey] if mkey else None
        if concept and _key(query) in {_key(alias) for alias in
                                      [concept['name'], *concept.get('aliases', [])]}:
            matched = concept
            search_query = f"{search_query} {matched['name']} {' '.join(matched.get('topics', []))}"

        notes = []
        if understanding["expansions"]:
            notes.append("mở rộng: " + ", ".join(understanding["expansions"]))
        if matched:
            notes.append(f"khái niệm: {matched['name']}")

        if self.search_index.get("retrieval") is not None:
            from itlr.core.recommender import row_to_dict
            hits = self.search_index["retrieval"].search(search_query,item_type=item_type,
                                                       min_relevance=min_pct/100., unique_items=True)
            results = [{**row_to_dict(hit["item"], score=hit["dense_score"]),
                        "chunk_id": hit["chunk_id"], "excerpt": hit["excerpt"]}
                       for hit in hits]
        else:
            results = search_by_embedding(
                search_query, self.items, self.model, self.search_index["embeddings"],
                char_vectorizer=self.search_index["char_vectorizer"],
                char_matrix=self.search_index["char_matrix"],
                item_type=item_type, min_relevance=min_pct / 100.0,
                query_prefix=self.search_index.get("query_prefix", ""),
                ann=self.search_index.get("ann"),
                reranker=self.search_index.get("reranker"),
            )
        return {
            "results": results,
            "display": understanding["display"],
            "note": " · ".join(notes),
            "corrected": bool(understanding["corrections"] or notes),
        }

    def chat(self, message, history=None):
        """Trả lời chatbot (off-topic gate + khái niệm-trước đã nằm trong EducationalChatbot)."""
        return self.chatbot.chat(message, history=history or [])

    def chat_stream(self, message, history=None):
        """Bản STREAMING: generator yield (event, data) — xem EducationalChatbot.chat_stream."""
        yield from self.chatbot.chat_stream(message, history=history or [])

    def personas(self):
        """Danh sách hồ sơ người dùng mô phỏng: [{uid, label}]."""
        self._require_cf()
        labels = self.cf_model["labels"]
        return [{"uid": int(u), "label": labels[u]} for u in labels]

    def for_you(self, persona_uid, interested_item_ids=None, top_n=12):
        """Gợi ý CF cho một persona. `interested_item_ids` = các item_id user vừa bấm 'Quan tâm'
        trong phiên (chuyển sang vị trí và nối vào lịch sử để feed học thêm)."""
        self._require_cf()
        histories = self.cf_model["histories"]
        id_to_pos = self.cf_model["id_to_pos"]
        uid = int(persona_uid)
        base = list(histories.get(uid, []))
        extra = [id_to_pos[int(i)] for i in (interested_item_ids or []) if int(i) in id_to_pos]
        recs = recommend_for_user(base + extra, self.cf_model, self.items, top_n=top_n)
        return {"recs": recs}

    def _require_cf(self) -> None:
        """CF là tùy chọn trong V2: chỉ endpoint CF mới yêu cầu model tồn tại."""
        if self.cf_model is None:
            raise CFUnavailable(
                "Chưa có cf_model.pkl — Collaborative Filtering là tính năng tùy chọn. "
                "Build phiên bản staging mới bằng `python scripts/build_all_v2.py --with-cf` "
                "rồi probe/activate (dữ liệu tương tác giả mô phỏng, "
                "không gắn dữ liệu thật).")


def _load_engine():
    """Nạp toàn bộ artifacts MỘT LẦN (cache process-level) và dựng RecommenderEngine.

    Ném FileNotFoundError nếu thiếu artifacts -> caller hiển thị hướng dẫn build.
    """
    from itlr.versioning import verify_integrity

    active_dir = config.current_dir()
    verify_integrity(active_dir, required=os.environ.get("ITLR_REQUIRE_ARTIFACT_MANIFEST") == "1")
    def artifact(name):
        return str(active_dir / name)
    with open(artifact("item_list.pkl"), "rb") as f:
        items = pickle.load(f).reset_index(drop=True)
    with open(artifact("search_meta.pkl"), "rb") as f:
        meta = pickle.load(f)
    with open(artifact("retrieval_model.pkl"), "rb") as f:
        retrieval_model = pickle.load(f)
    # CF là TUỲ CHỌN V2: thiếu cf_model.pkl → log WARNING, engine vẫn chạy
    # (search/chatbot giữ nguyên; endpoint CF sẽ trả 503). KHÔNG nuốt lỗi cho artifact khác.
    cf_path = artifact("cf_model.pkl")
    if Path(cf_path).is_file():
        with open(cf_path, "rb") as f:
            cf_model = pickle.load(f)
    else:
        LOG.warning("Thiếu %s — Collaborative Filtering bị tắt (tùy chọn V2); "
                    "/api/personas và /api/for-you sẽ trả 503 cho tới khi build CF.", cf_path)
        cf_model = None
    search_index = {
        "embeddings": None,
        "char_vectorizer": None,
        "char_matrix": None,
        "query_prefix": meta.get("query_prefix", ""),
    }
    with open(artifact("embeddings.pkl"), "rb") as f:
        search_index["embeddings"] = pickle.load(f)
    with open(artifact("char_vectorizer.pkl"), "rb") as f:
        search_index["char_vectorizer"] = pickle.load(f)
    with open(artifact("char_matrix.pkl"), "rb") as f:
        search_index["char_matrix"] = pickle.load(f)

    chunk_path = active_dir / "chunk_meta.pkl"
    has_chunk_meta = chunk_path.is_file()
    if has_chunk_meta:
        with chunk_path.open("rb") as handle:
            chunk_meta = pickle.load(handle)
        search_index["chunk_meta"] = (chunk_meta.get("rows", []) if isinstance(chunk_meta, dict)
                                      else chunk_meta.to_dict("records") if hasattr(chunk_meta, "to_dict") else chunk_meta)

    if (active_dir / "chunk_embeddings.pkl").is_file():
        if not has_chunk_meta:
            # Nửa bộ artifacts (bản chép nửa vời / GC giữa chừng): fail-closed trước
            # nhập ChunkIndex — bản 503 của API, không hề KeyError 500.
            raise FileNotFoundError(
                "chunk_embeddings.pkl có mặt nhưng thiếu cặp chunk_meta.pkl trong "
                f"{active_dir} — phiên bản incomplete, hãy rebuild (scripts/build_all_v2.py).")
        from itlr.core.chunks import ChunkIndex
        with (active_dir / "chunk_embeddings.pkl").open("rb") as handle:
            search_index["chunks"] = ChunkIndex(search_index["chunk_meta"], pickle.load(handle))

    from sentence_transformers import SentenceTransformer

    from itlr.chatbot.chatbot import EducationalChatbot
    from itlr.core.ann import load_ann
    from itlr.core.rerank import get_reranker

    model = SentenceTransformer(meta["model_name"])
    # ANN phải thuộc đúng version đang active và đúng shape với embeddings/items.
    # load_ann tự trả None (fallback brute-force) nếu meta lệch — xem itlr/core/ann.py.
    ann = load_ann(artifacts_dir=active_dir, expected_n=len(items), expected_dim=meta.get("dim"))
    reranker = get_reranker()
    search_index["ann"] = ann
    search_index["reranker"] = reranker

    if search_index.get("chunks") is not None:
        from itlr.retrieval.service import RetrievalService
        search_index["retrieval"] = RetrievalService(search_index["chunks"],items,model,
                                                     search_index["query_prefix"],reranker)

    chatbot = EducationalChatbot(
        items, retrieval_model, search_index=search_index, embed_model=model,
        query_prefix=search_index["query_prefix"], ann=ann, reranker=reranker,
    )
    search_index["vocab"] = chatbot.vocab
    return RecommenderEngine(items, model, search_index, cf_model, chatbot)


_ENGINE = None
_ENGINE_LOCK = threading.RLock()


def load_engine():
    global _ENGINE
    cached = _ENGINE
    if cached is not None:
        return cached
    with _ENGINE_LOCK:
        if _ENGINE is None:
            return _reload_engine()
        return _ENGINE


def _reload_engine():
    global _ENGINE
    from itlr.locking import file_lock
    with _ENGINE_LOCK, file_lock(config.ARTIFACTS_DIR / ".activation.lock", shared=True):
        candidate = _load_engine()
        _ENGINE = candidate
        return candidate


def _clear_engine():
    global _ENGINE
    with _ENGINE_LOCK:
        _ENGINE = None


load_engine.cache_clear = _clear_engine
load_engine.reload = _reload_engine
