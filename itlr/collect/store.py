"""SQLite store cho dữ liệu thu thập — KHÔNG DataLake, không dịch vụ ngoài.

Bảng:
  sources   — nguồn + chính sách (provenance)
  docs      — tài liệu đã thu ( contenki hash, revision, chất lượng, giấy phép)
  item_map  — item_key (khóa bền vững) → item_id (số ổn định, KHÔNG đổi giữa các lần chạy)
Mọi ghi: transaction từng thao tác (atomic); đọc mở connect ngắn.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    source_id          TEXT PRIMARY KEY,
    kind               TEXT NOT NULL,
    name               TEXT NOT NULL,
    platform           TEXT NOT NULL DEFAULT '',
    homepage           TEXT NOT NULL DEFAULT '',
    full_text_allowed  INTEGER NOT NULL DEFAULT 0,
    license            TEXT NOT NULL DEFAULT '',
    lang               TEXT NOT NULL DEFAULT 'en',
    type_label         TEXT,
    level_label        TEXT,
    extras_json        TEXT,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS docs (
    doc_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    content_key        TEXT NOT NULL UNIQUE,   -- khóa bền vững (URL chuẩn hóa → sha)
    source_id          TEXT NOT NULL,
    external_id        TEXT NOT NULL DEFAULT '',
    url                TEXT NOT NULL,
    norm_url           TEXT NOT NULL,
    title              TEXT NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    text               TEXT NOT NULL DEFAULT '',
    tags               TEXT NOT NULL DEFAULT '',   -- "a,b,c" từ nguồn (rss/api)
    author             TEXT NOT NULL DEFAULT '',
    published_at       TEXT NOT NULL DEFAULT '',
    lang               TEXT NOT NULL DEFAULT 'en',
    license            TEXT NOT NULL DEFAULT '',
    full_text_allowed  INTEGER NOT NULL DEFAULT 0,
    content_hash       TEXT NOT NULL,
    n_chars            INTEGER NOT NULL DEFAULT 0,
    quality_status     TEXT NOT NULL DEFAULT 'ok',
    status             TEXT NOT NULL DEFAULT 'active',   -- active | missing
    revision           INTEGER NOT NULL DEFAULT 1,
    fetched_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_docs_source   ON docs(source_id);
CREATE INDEX IF NOT EXISTS idx_docs_quality  ON docs(quality_status, status);
CREATE INDEX IF NOT EXISTS idx_docs_listing  ON docs(norm_url);

CREATE TABLE IF NOT EXISTS item_map (
    item_key    TEXT PRIMARY KEY,   -- 'u:<sha1(url)>' cho crawl; 'legacy:csv:<item_id>' legacy
    item_id     INTEGER NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS title_seen (
    title_norm  TEXT PRIMARY KEY,   -- chống trùng title (near-dup giữa các nguồn)
    content_key TEXT NOT NULL
);
"""


def utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CollectStore:
    """SQLite wrapper: upsert thân thiện crawler, phát hiện thay đổi, cho xuất dữ liệu."""

    def __init__(self, db_path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.commit()

    def close(self):
        try:
            self._conn.commit()
        finally:
            self._conn.close()

    # ---------- sources ----------
    def upsert_source(self, data: dict) -> None:
        q = ("INSERT INTO sources (source_id, kind, name, platform, homepage, "
             "full_text_allowed, license, lang, type_label, level_label, extras_json, updated_at) "
             "VALUES (:source_id,:kind,:name,:platform,:homepage,:full_text_allowed,"
             ":license,:lang,:type_label,:level_label,:extras_json,:updated_at) "
             "ON CONFLICT(source_id) DO UPDATE SET kind=excluded.kind, name=excluded.name, "
             "platform=excluded.platform, homepage=excluded.homepage, "
             "full_text_allowed=excluded.full_text_allowed, license=excluded.license, "
             "lang=excluded.lang, type_label=excluded.type_label, "
             "level_label=excluded.level_label, extras_json=excluded.extras_json, "
             "updated_at=excluded.updated_at")
        if not data.get("updated_at"):
            data = {**data, "updated_at": utcnow()}
        with self._conn:
            self._conn.execute(q, data)
            if not data["full_text_allowed"]:
                # Revoke reuse immediately, including archived URLs and failed listings.
                self._conn.execute(
                    "UPDATE docs SET full_text_allowed=0, updated_at=? "
                    "WHERE source_id=? AND full_text_allowed<>0",
                    (data["updated_at"], data["source_id"]))

    def source_row(self, source_id: str) -> dict | None:
        cur = self._conn.execute("SELECT * FROM sources WHERE source_id=?", (source_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    # ---------- docs ----------
    def get_doc_by_key(self, content_key: str) -> dict | None:
        cur = self._conn.execute("SELECT * FROM docs WHERE content_key=?", (content_key,))
        row = cur.fetchone()
        return dict(row) if row else None

    def find_title_dup(self, title_norm: str, exclude_key: str = "") -> dict | None:
        cur = self._conn.execute(
            "SELECT * FROM title_seen WHERE title_norm=? AND content_key<>?",
            (title_norm, exclude_key))
        row = cur.fetchone()
        if row:
            d = self.get_doc_by_key(row["content_key"])
            if d:
                return d
        return None

    def find_near_dup_title(self, title: str, threshold: float = 0.80) -> dict | None:
        """Tìm doc đang active có tiêu đề gần trùng (Jaccard token >= threshold).

        Khác `find_title_dup` (chỉ khớp CHÍNH XÁC sau chuẩn hóa), hàm này bắt được biến thể
        tiêu đề giữa các nguồn ("Hướng dẫn Docker (2026)" vs "Hướng dẫn Docker"). So sánh
        trên toàn bộ title_seen — quy mô crawl hiện tại (vài nghìn) chấp nhận được; nếu lớn
        hơn nên chuyển sang FTS5.
        """
        from itlr.collect.quality import is_near_dup_title, title_similarity

        # Quét TẤT CẢ candidate đạt is_near_dup_title (khác số thứ tự là series, không trùng) —
        # candidate điểm cao nhất có thể là series, trong khi biến thể chữ có điểm thấp hơn.
        for row in self._conn.execute(
                "SELECT d.* FROM title_seen t JOIN docs d ON d.content_key=t.content_key "
                "WHERE d.status='active' ORDER BY d.doc_id DESC"):
            score = title_similarity(row["title"], title)
            if score < threshold:
                continue
            if is_near_dup_title(row["title"], title, threshold):
                return dict(row)
        return None

    def upsert_doc(self, doc: dict) -> dict:
        """Upsert theo content_key; nhận biết NEW / CHANGED / UNCHANGED bằng content_hash.

        Trả {"event": "new|updated|unchanged", "row_id": doc_id, "revision": n}
        """
        now = utcnow()
        existing = self.get_doc_by_key(doc["content_key"])
        if existing is None:
            q = ("INSERT INTO docs (content_key, source_id, external_id, url, norm_url, "
                 "title, description, text, tags, author, published_at, lang, license, "
                 "full_text_allowed, content_hash, n_chars, quality_status, status, "
                 "revision, fetched_at, updated_at) "
                 "VALUES (:content_key,:source_id,:external_id,:url,:norm_url,"
                 ":title,:description,:text,:tags,:author,:published_at,:lang,:license,"
                 ":full_text_allowed,:content_hash,:n_chars,:quality_status,"
                 "COALESCE(:status,'active'),1,:fetched_at,:updated_at)")
            self._conn.execute(q, {**doc, "updated_at": doc["fetched_at"]})
            self._conn.commit()
            row = self._conn.execute(
                "SELECT doc_id, revision FROM docs WHERE content_key=?",
                (doc["content_key"],)).fetchone()
            self._remember_title(doc)
            # Khóa thống nhất với event còn lại: "row_id" + "revision"; trước đây event
            # "new" trả "row" (shape lệch) khiến consumer đọc res["row_id"] va KeyError.
            return {"event": "new", "row_id": row["doc_id"],
                    "row": dict(row), "revision": int(row["revision"])}

        provenance = ("source_id", "external_id", "url", "norm_url", "lang",
                      "license", "full_text_allowed")
        if existing["content_hash"] == doc["content_hash"] and all(
                existing[field] == doc[field] for field in provenance):
            self._touch(existing["doc_id"], now)
            return {"event": "unchanged", "row_id": existing["doc_id"],
                    "revision": existing["revision"]}

        # Nội dung ĐỔI → cập nhật, thúc revision
        q = ("UPDATE docs SET title=:title, description=:description, text=:text, "
             "tags=:tags, author=:author, published_at=:published_at, "
             "source_id=:source_id, external_id=:external_id, url=:url, norm_url=:norm_url, "
             "lang=:lang, license=:license, full_text_allowed=:full_text_allowed, "
             "content_hash=:content_hash, n_chars=:n_chars, "
             "quality_status=:quality_status, revision=revision+1, "
             "fetched_at=:fetched_at, updated_at=:updated_at, status='active' "
             "WHERE doc_id=:doc_id")
        self._conn.execute(q, {
            **doc, "doc_id": existing["doc_id"], "updated_at": now})
        self._conn.commit()
        self._remember_title(doc)
        if existing["quality_status"] == "ok" or doc["quality_status"] == "ok":
            ev = "updated"
        else:
            ev = "updated_quality"
        return {"event": ev, "row_id": existing["doc_id"],
                "revision": existing["revision"] + 1}

    def _remember_title(self, doc: dict) -> None:
        from itlr.collect.quality import normalize_title

        norm = normalize_title(doc.get("title"))
        if len(norm) < 8:
            return
        self._conn.execute(
            "INSERT OR IGNORE INTO title_seen (title_norm, content_key) VALUES (?,?)",
            (norm, doc["content_key"]))
        self._conn.commit()

    def _touch(self, doc_id: int, now: str) -> None:
        self._conn.execute("UPDATE docs SET fetched_at=? WHERE doc_id=?", (now, doc_id))
        self._conn.commit()

    def mark_missing(self, source_id: str) -> int:
        """Đánh dấu doc của nguồn không còn thấy trong lượt chạy -> missing.

        Trả số bản ghi vừa chuyển từ active sang missing. Dùng `reconcile_source` để
        mark + restore trong CÙNG transaction.
        """
        cur = self._conn.execute(
            "UPDATE docs SET status='missing', updated_at=? WHERE source_id=? AND status='active'",
            (utcnow(), source_id))
        self._conn.commit()
        return int(cur.rowcount)

    def reactivated_count(self, source_id: str) -> int:
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM docs WHERE source_id=? AND status='active'", (source_id,))
        return int(cur.fetchone()[0])

    def link_seen(self, source_id: str, keys: set[str]) -> int:
        """Đặt active lại cho các doc thấy trong lượt này; trả số doc 'missing' được phục hồi."""
        if not keys:
            return 0
        cur = self._conn.executemany(
            "UPDATE docs SET status='active', updated_at=? "
            "WHERE content_key=? AND source_id=? AND status='missing'",
            [(utcnow(), k, source_id) for k in keys])
        self._conn.commit()
        return int(cur.rowcount)

    def reconcile_source(self, source_id: str, seen_keys: set[str]) -> dict:
        """Đồng bộ trạng thái active/missing của MỘT nguồn trong một transaction.

        - Doc active nhưng URL không còn trong listing đầy đủ -> missing.
        - Doc missing nhưng xuất hiện lại -> active (restored).
        Chỉ gọi khi listing LẤY ĐỦ; listing lỗi một phần mà gọi sẽ đánh missing nhầm.
        """
        now = utcnow()
        active_keys = {row[0] for row in self._conn.execute(
            "SELECT content_key FROM docs WHERE source_id=? AND status='active'", (source_id,))}
        missing_keys = {row[0] for row in self._conn.execute(
            "SELECT content_key FROM docs WHERE source_id=? AND status='missing'", (source_id,))}
        newly_missing = len(active_keys - set(seen_keys))
        restored = len(missing_keys & set(seen_keys))
        self._conn.execute(
            "UPDATE docs SET status='missing', updated_at=? "
            "WHERE source_id=? AND status='active'", (now, source_id))
        if seen_keys:
            self._conn.executemany(
                "UPDATE docs SET status='active', updated_at=? "
                "WHERE content_key=? AND source_id=? AND status='missing'",
                [(now, k, source_id) for k in seen_keys])
        self._conn.commit()
        return {"marked_missing": newly_missing, "restored": restored}

    def stats(self) -> dict[str, Any]:
        out = {
            "sources": self._conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
            "docs_active": self._conn.execute(
                "SELECT COUNT(*) FROM docs WHERE status='active' AND quality_status='ok'"
            ).fetchone()[0],
            "docs_total": self._conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0],
            "item_ids": self._conn.execute("SELECT COUNT(*) FROM item_map").fetchone()[0],
        }
        by_source = {}
        for row in self._conn.execute(
                "SELECT source_id, COUNT(*) AS n FROM docs WHERE quality_status='ok' "
                "AND status='active' GROUP BY source_id"):
            by_source[row["source_id"]] = row["n"]
        out["by_source"] = by_source
        return out

    # ---------- item_map ----------
    def assign_item_id(self, item_key: str) -> tuple[int, bool]:
        """item_id ỔN ĐỊNH: đã có → trả lại; chưa → gán max+1. Trả (item_id, is_new)."""
        cur = self._conn.execute("SELECT item_id FROM item_map WHERE item_key=?", (item_key,))
        row = cur.fetchone()
        if row:
            return int(row["item_id"]), False
        nxt = self._next_item_id()
        row = self._conn.execute("INSERT INTO item_map (item_key, item_id, created_at) "
                                 "VALUES (?,?,?) RETURNING item_id",
                                 (item_key, nxt, utcnow())).fetchone()
        self._conn.commit()
        return int(row[0]), True

    def _next_item_id(self) -> int:
        row = self._conn.execute("SELECT MAX(item_id) FROM item_map").fetchone()
        base = int(row[0] or 0)
        return base + 1

    def set_item_floor(self, floor_id: int) -> None:
        """Giữ item_id legacy (catalog CSV) để item_id crawl bắt đầu SAU số đó."""
        self._conn.execute(
            "INSERT OR REPLACE INTO item_map (item_key, item_id, created_at) VALUES (?,?,?)",
            ("legacy:floor", int(floor_id), utcnow()))
        self._conn.commit()

    def item_id_lookup(self, item_key: str) -> int | None:
        cur = self._conn.execute("SELECT item_id FROM item_map WHERE item_key=?", (item_key,))
        row = cur.fetchone()
        return int(row["item_id"]) if row else None

    # ---------- xuất cho dựng catalog ----------
    def docs_for_index(self, source_ids=None, limit=None) -> list[dict]:
        q = ("SELECT * FROM docs WHERE status='active' AND quality_status='ok' "
             "AND full_text_allowed=1")
        args: list = []
        if source_ids:
            q += " AND source_id IN ({})".format(",".join("?" * len(source_ids)))
            args += list(source_ids)
        q += " ORDER BY doc_id DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        return [dict(r) for r in self._conn.execute(q, args)]
