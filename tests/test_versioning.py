"""Tests cho index theo phiên bản: staging → probe → activate → rollback.

Hợp đồng quan trọng: API đang chạy không được phá vỡ khi một phiên bản build mới
không đạt kiểm thử (không kích hoạt) và rollback cuối phải trả về đúng phiên bản cũ.
"""

import json

import pytest

from itlr import versioning


@pytest.fixture()
def vroot(tmp_path, monkeypatch):
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setattr(versioning.config, "ARTIFACTS_DIR", root)
    return root


class TestVersions:
    def test_no_pointer_returns_base_dir(self, vroot):
        assert versioning.current_dir() == vroot

    def test_activate_writes_pointer_and_current_dir(self, vroot):
        d = versioning.create_version_dir(vroot, "v1")
        versioning.write_manifest(d, {"probe": "ok"})
        versioning.activate(vroot, "v1")
        cur = versioning.current_dir()
        assert cur == d
        meta = json.loads((vroot / "CURRENT.json").read_text())
        assert meta["version"] == "v1"
        assert meta["dir"].endswith("v1")

    def test_activate_missing_version_fails(self, vroot):
        with pytest.raises(versioning.VersionError):
            versioning.activate(vroot, "nope")

    def test_activation_requires_marker_file(self, vroot):
        """Phiên bản không có MANIFEST 'activated ok' → CHƯA được phép kích hoạt."""
        d = versioning.create_version_dir(vroot, "v_bad")
        with pytest.raises(versioning.VersionError):
            versioning.activate(vroot, "v_bad")

    def test_rollback_to_previous(self, vroot):
        versioning.create_version_dir(vroot, "v1")
        versioning.write_manifest(vroot / "versions" / "v1", {"probe": "ok"})
        versioning.activate(vroot, "v1")
        versioning.create_version_dir(vroot, "v2")
        versioning.write_manifest(vroot / "versions" / "v2", {"probe": "ok"})
        versioning.activate(vroot, "v2")
        assert versioning.current_version(vroot) == "v2"
        ok = versioning.rollback(vroot)
        assert ok is True
        assert versioning.current_version(vroot) == "v1"

    def test_rollback_without_history(self, vroot):
        assert versioning.rollback(vroot) is False

    def test_history_note(self, vroot):
        versioning.create_version_dir(vroot, "v1")
        versioning.write_manifest(vroot / "versions" / "v1", {"probe": "ok"})
        versioning.activate(vroot, "v1")
        versioning.create_version_dir(vroot, "v2")
        versioning.write_manifest(vroot / "versions" / "v2", {"probe": "ok"})
        versioning.activate(vroot, "v2")
        h = versioning.read_history(vroot)
        assert [x["version"] for x in h if x["event"] == "activate"][-2:] == \
            ["v1", "v2"]

    def test_garbage_collect_keeps_recent(self, vroot):
        for v in ["v1", "v2", "v3", "v4"]:
            d = versioning.create_version_dir(vroot, v)
            (d / f"{v}.txt").write_text("x")
            versioning.write_manifest(d, {"probe": "ok"})
            versioning.activate(vroot, v)
        versioning.garbage_collect(vroot, keep=3)
        assert versioning.list_versions(vroot) == ["v4", "v3", "v2"]
