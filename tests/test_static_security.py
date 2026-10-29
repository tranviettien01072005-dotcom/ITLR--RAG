from pathlib import Path
from fastapi.testclient import TestClient
from itlr.api.server import app

STATIC = Path('itlr/api/static')

def test_static_scripts_are_local_and_no_inline_handlers():
    html = (STATIC / 'index.html').read_text()
    assert 'cdn.jsdelivr' not in html
    assert 'onclick=' not in html and 'onkeydown=' not in html
    assert '<script>' not in html

def test_security_headers_on_static_and_errors():
    client = TestClient(app)
    for path in ['/', '/static/ui.js', '/unknown']:
        response = client.get(path)
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert "script-src 'self'" in response.headers['content-security-policy']
        assert response.headers['x-frame-options'] == 'DENY'


def test_metrics_do_not_store_unmatched_user_paths():
    from itlr.api.server import _METRICS
    client = TestClient(app)
    for n in range(10):
        client.get(f'/missing-{n}')
    assert not any(path.startswith('/missing-') for path in _METRICS['by_route'])


def test_multiworker_configuration_rejected(monkeypatch):
    import pytest
    from itlr.api.ratelimit import validate_workers
    monkeypatch.setenv('WEB_CONCURRENCY', '2')
    with pytest.raises(RuntimeError, match='must be 1'):
        validate_workers()
