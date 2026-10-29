"""Test chuẩn hóa dữ liệu crawl → schema ITLR: item_id ổn định, phân loại category, provenance."""

import pytest

from itlr.collect.normalize import assemble_itlr_items, classify_category
from itlr.collect.quality import content_hash
from itlr.collect.store import CollectStore
from itlr.collect.url_util import content_key


class TestClassifyCategory:
    def test_docker_kubernetes(self):
        assert classify_category("Hướng dẫn Docker compose cơ bản") == "DevOps"
        assert classify_category("", "k8s, devops") == "DevOps"

    def test_ai_and_python(self):
        assert classify_category("Machine Learning tutorial for beginners") == "Trí tuệ nhân tạo"
        assert classify_category("Python decorators explained step by step") == "Lập trình"

    def test_unknown_returns_default(self):
        # chưa phân loại được → None; lớp assemble sẽ dùng nhãn chung "Khoa học máy tính"
        assert classify_category("Hom lai cac mon khac loai") is None

    def test_never_fabricates_category(self):
        c = classify_category("vi-du-khong-giong-Thu750")
        assert c in (None, "Khoa học máy tính")


class TestAssemble:
    def _store_with_docs(self, tmp_path, docs):
        st = CollectStore(tmp_path / "c.db")
        st.set_item_floor(5000)
        for d in docs:
            st.upsert_source({
                "source_id": d["source_id"], "kind": "api", "name": "N",
                "platform": d.get("platform", "P"), "homepage": "h",
                "full_text_allowed": 1, "license": "L", "lang": "en",
                "type_label": "Tài liệu", "level_label": "Trung cấp",
                "extras_json": "{}", "updated_at": "2026-10-28T00:00:00Z"})
            keys = {k: d[k] for k in ("content_key", "source_id", "external_id", "url",
                                      "norm_url", "title", "description", "text", "tags",
                                      "author", "published_at", "lang", "license",
                                      "full_text_allowed", "content_hash", "n_chars",
                                      "quality_status", "status", "fetched_at")}
            st.upsert_doc({**keys, "revision": 1, "updated_at": keys["fetched_at"]})
        st.close()
        return tmp_path / "c.db"

    def _doc(self, key, title, text, source_id="src", platform="P", tags="",
             url=None):
        url = url or f"https://x/{key.split(':')[-1]}"
        return {
            "content_key": key, "source_id": source_id, "external_id": key,
            "url": url, "norm_url": url, "title": title, "description": "",
            "text": text, "tags": tags, "author": "Author X",
            "published_at": "2026-10-28T00:00:00Z", "lang": "en", "license": "CC BY-SA",
            "full_text_allowed": 1, "content_hash": content_hash(text),
            "n_chars": len(text), "quality_status": "ok", "status": "active",
            "fetched_at": "2026-10-28T00:00:00Z"}

    def test_assemble_maps_schema(self, tmp_path, monkeypatch):
        db = self._store_with_docs(tmp_path, [
            self._doc(content_key("https://dev.to/docker-guide"),
                      "Docker guide for beginners initiated",
                      "learn docker and kubernetes with devops " * 30,
                      tags="docker,k8s", url="https://dev.to/docker-guide"),
        ])
        monkeypatch.setattr("itlr.collect.normalize.config", type(
            "C", (), {"COLLECT_DB": db, "ITEMS_CSV": tmp_path / "missing.csv",
                      "DATA_DIR": tmp_path}))
        df = assemble_itlr_items()
        assert len(df) == 1
        row = df.iloc[0]
        assert row["item_id"] == 5001  # floor 5000 → crawl bắt đầu 5001
        assert row["type"] == "Tài liệu" and row["level"] == "Trung cấp"
        assert row["category"] == "DevOps"
        assert "learn docker" in row["description"].lower()     # description = text thật
        assert row["platform"] == "P"
        assert str(row["link"]).startswith("https://dev.to/")
        assert row["origin"] == "crawl:src"
        assert row["crawl_license"] == "CC BY-SA"
        assert "docker" in str(row["topics"])

    def test_item_id_stable_across_reassembles(self, tmp_path, monkeypatch):
        key = content_key("https://dev.to/stable-doc")
        db = self._store_with_docs(tmp_path, [
            self._doc(key, "Stable doc is what we like to read about kubernetes",
                      "kubernetes and docker " * 30)])
        monkeypatch.setattr("itlr.collect.normalize.config", type(
            "C", (), {"COLLECT_DB": db, "ITEMS_CSV": tmp_path / "missing.csv",
                      "DATA_DIR": tmp_path}))
        df1 = assemble_itlr_items()
        df2 = assemble_itlr_items()  # lần 2 — cùng mapping
        assert df2.iloc[0]["item_id"] == df1.iloc[0]["item_id"]

    def test_empty_store_returns_empty_df(self, tmp_path, monkeypatch):
        monkeypatch.setattr("itlr.collect.normalize.config", type(
            "C", (), {"COLLECT_DB": tmp_path / "none.db",
                      "ITEMS_CSV": tmp_path / "missing.csv", "DATA_DIR": tmp_path}))
        df = assemble_itlr_items()
        assert df.empty
