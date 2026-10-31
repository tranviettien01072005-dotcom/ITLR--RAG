"""Readiness identifies the verified loaded snapshot, never the current pointer alone."""
import hashlib
import shutil
from types import SimpleNamespace

from test_api_integration import client as client  # Re-export the isolated artifact fixture.


def fingerprint(path):
    return {'version': path.name, 'manifest_sha256': hashlib.sha256((path / 'MANIFEST.json').read_bytes()).hexdigest()}


def test_health_snapshot_changes_only_after_successful_reload(client, monkeypatch):
    from itlr import config, versioning
    root = config.ARTIFACTS_DIR
    original = root / 'versions' / 'fixture'
    assert client.get('/health').json()['artifacts'] == fingerprint(original)
    candidate = root / 'versions' / 'candidate'
    shutil.copytree(original, candidate)
    versioning.activate(root, 'candidate')
    assert client.get('/health').json()['artifacts'] == fingerprint(original)
    monkeypatch.setenv('ITLR_ADMIN_TOKEN', 'fixture-only-fingerprint-token')
    response = client.post('/admin/reload', headers={'X-Admin-Token': 'fixture-only-fingerprint-token'})
    assert response.status_code == 200
    assert response.json()['artifacts'] == fingerprint(candidate)
    assert client.get('/health').json()['artifacts'] == fingerprint(candidate)


def test_failed_reload_retains_loaded_fingerprint(client, monkeypatch):
    from itlr import config, versioning
    root = config.ARTIFACTS_DIR
    original = root / 'versions' / 'fixture'
    candidate = root / 'versions' / 'candidate'
    shutil.copytree(original, candidate)
    versioning.activate(root, 'candidate')
    with (candidate / 'item_list.pkl').open('ab') as handle:
        handle.write(b'isolated tamper fixture')
    monkeypatch.setenv('ITLR_ADMIN_TOKEN', 'fixture-only-fingerprint-token')
    response = client.post('/admin/reload', headers={'X-Admin-Token': 'fixture-only-fingerprint-token'})
    assert response.status_code == 503
    assert client.get('/health').json()['artifacts'] == fingerprint(original)


def test_legacy_engine_without_fingerprint_remains_supported(monkeypatch):
    from itlr.api import server
    monkeypatch.setattr(server, 'load_engine', lambda: SimpleNamespace(items=[], cf_model=None))
    assert server.health()['artifacts'] is None
