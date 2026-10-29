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


def test_generated_staging_ids_do_not_collide(vroot, monkeypatch):
    monkeypatch.setattr(versioning.time, 'time', lambda: 1234567890.)
    a = versioning.create_version_dir(vroot)
    b = versioning.create_version_dir(vroot)
    assert a != b


def test_rollback_tracks_actual_transition(vroot):
    for name in ['v1', 'v2', 'v3']:
        d = versioning.create_version_dir(vroot, name)
        versioning.write_manifest(d, {'probe': 'ok'})
        versioning.activate(vroot, name)
    assert versioning.rollback(vroot)
    assert versioning.current_version(vroot) == 'v2'
    assert versioning.rollback(vroot)
    assert versioning.current_version(vroot) == 'v3'


def test_concurrent_activations_preserve_all_history(vroot):
    from concurrent.futures import ThreadPoolExecutor
    names = [f'v{i}' for i in range(12)]
    for name in names:
        d = versioning.create_version_dir(vroot, name)
        versioning.write_manifest(d, {'probe':'ok'})
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda name: versioning.activate(vroot,name), names))
    assert len(versioning.read_history(vroot)) == len(names)
    assert {h['version'] for h in versioning.read_history(vroot)} == set(names)


def test_gc_preserves_in_progress_staging(vroot):
    staged = versioning.create_version_dir(vroot,'aaa-staging')
    d = versioning.create_version_dir(vroot,'zzz-active')
    versioning.write_manifest(d, {'probe':'ok'})
    versioning.activate(vroot,'zzz-active')
    versioning.garbage_collect(vroot,keep=1)
    assert staged.is_dir()


def test_multiprocess_activation_history_is_consistent(vroot):
    import subprocess
    import sys
    from concurrent.futures import ThreadPoolExecutor
    names = [f'p{i}' for i in range(8)]
    for name in names:
        d = versioning.create_version_dir(vroot,name)
        versioning.write_manifest(d, {'probe':'ok'})
    def activate(name):
        subprocess.run([sys.executable,'-c',
                        'import sys; from itlr.versioning import activate; activate(sys.argv[1],sys.argv[2])',
                        str(vroot),name],check=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(activate,names))
    hist = versioning.read_history(vroot)
    assert len(hist) == 8
    assert {h['version'] for h in hist} == set(names)
    assert versioning.current_version(vroot) == hist[-1]['version']


def test_crash_between_pointer_and_history_preserves_rollback(vroot, monkeypatch):
    for name in ['v1','v2']:
        d=versioning.create_version_dir(vroot,name)
        versioning.write_manifest(d, {'probe':'ok'})
    versioning.activate(vroot,'v1')
    def crash(*args): raise OSError('simulated interruption after pointer commit')
    with monkeypatch.context() as m:
        m.setattr(versioning,'_append_history',crash)
        with pytest.raises(OSError): versioning.activate(vroot,'v2')
    assert versioning.read_history(vroot)[-1]['version']=='v2'
    assert versioning.rollback(vroot)
    assert versioning.current_version(vroot)=='v1'


def test_restart_after_process_exit_between_pointer_and_mirror(vroot):
    import subprocess
    import sys
    for name in ['v1','v2']:
        d=versioning.create_version_dir(vroot,name)
        versioning.write_manifest(d, {'probe':'ok'})
    versioning.activate(vroot,'v1')
    code = ('import os,sys; from itlr import versioning as v; '
            'v._append_history=lambda *a: os._exit(23); v.activate(sys.argv[1],"v2")')
    result=subprocess.run([sys.executable,'-c',code,str(vroot)],check=False)
    assert result.returncode==23
    assert versioning.current_version(vroot)=='v2'
    assert versioning.read_history(vroot)[-1]['version']=='v2'
    assert versioning.rollback(vroot)
    assert versioning.current_version(vroot)=='v1'
