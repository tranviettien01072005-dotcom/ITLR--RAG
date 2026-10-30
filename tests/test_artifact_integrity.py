import json

import pytest

from itlr import versioning


def test_reject_version_traversal(tmp_path):
    with pytest.raises(versioning.VersionError):
        versioning.create_version_dir(tmp_path, '../escape')


def test_pointer_outside_root_fails_closed(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    root = tmp_path / 'artifacts'
    root.mkdir()
    (root / 'CURRENT.json').write_text(json.dumps({'version': 'v1', 'dir': str(outside)}))
    with pytest.raises(versioning.VersionError):
        versioning.current_dir(root)


def test_changed_artifact_cannot_activate(tmp_path):
    d = versioning.create_version_dir(tmp_path, 'v1')
    (d / 'item_list.pkl').write_bytes(b'original')
    versioning.write_manifest(d, {'probe': 'ok'})
    (d / 'item_list.pkl').write_bytes(b'changed')
    with pytest.raises(versioning.VersionError):
        versioning.activate(tmp_path, 'v1')


def test_added_pickle_cannot_activate(tmp_path):
    d = versioning.create_version_dir(tmp_path, 'v1')
    versioning.write_manifest(d, {'probe': 'ok'})
    (d / 'cf_model.pkl').write_bytes(b'unverified')
    with pytest.raises(versioning.VersionError):
        versioning.activate(tmp_path, 'v1')


def test_corrupt_previous_version_cannot_rollback(tmp_path):
    for name in ['v1', 'v2']:
        d = versioning.create_version_dir(tmp_path, name)
        (d / 'item_list.pkl').write_bytes(b'original')
        versioning.write_manifest(d, {'probe': 'ok'})
        versioning.activate(tmp_path, name)
    (tmp_path / 'versions/v1/item_list.pkl').write_bytes(b'changed')
    with pytest.raises(versioning.VersionError):
        versioning.rollback(tmp_path)
    assert versioning.current_version(tmp_path) == 'v2'


def test_engine_rejects_changed_pickle_before_deserialization(tmp_path, monkeypatch):
    import pickle
    from itlr import config
    from itlr.engine import load_engine

    (tmp_path / 'item_list.pkl').write_bytes(b'original')
    versioning.write_manifest(tmp_path, {'probe': 'ok'})
    (tmp_path / 'item_list.pkl').write_bytes(b'changed')
    monkeypatch.setattr(config, 'current_dir', lambda: tmp_path)
    monkeypatch.setattr(pickle, 'load', lambda _: pytest.fail('untrusted pickle executed'))
    load_engine.cache_clear()
    with pytest.raises(versioning.VersionError, match='integrity'):
        load_engine()


def test_strict_mode_rejects_missing_manifest(tmp_path):
    with pytest.raises(versioning.VersionError):
        versioning.verify_integrity(tmp_path, required=True)


def test_manifest_survives_first_flat_engine_read_lock(tmp_path):
    from itlr.locking import file_lock

    (tmp_path / 'item_list.pkl').write_bytes(b'trusted fixture')
    versioning.write_manifest(tmp_path, {'probe': 'pending'})
    with file_lock(tmp_path / '.activation.lock', shared=True):
        versioning.verify_integrity(tmp_path, required=True)
