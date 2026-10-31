"""Source-link audit tests (fake network/policy; no real requests)."""
from scripts import audit_source_links


class FakeRobots:
    def __init__(self, denied=()):
        self.denied = set(denied)

    def allowed(self, url):
        return (url not in self.denied, 0.0)


class FakeLimiter:
    def __init__(self):
        self.calls = []

    def wait(self, host, extra_delay=0.0):
        self.calls.append(host)


def test_detects_404_and_redirect_target():
    responses = {
        'https://a.test/ok': (200, 'https://a.test/ok'),
        'https://a.test/moved': (200, 'https://a.test/new-home'),
        'https://a.test/gone': (404, 'https://a.test/gone'),
    }
    limiter = FakeLimiter()
    rows = audit_source_links.audit_links(
        list(responses) + ['https://a.test/moved'],  # duplicate must be fetched once
        fetch=lambda url: responses[url], robots=FakeRobots(), throttle=limiter,
    )
    by_url = {r['url']: r for r in rows}
    assert len(rows) == 3
    assert by_url['https://a.test/gone']['missing'] is True
    assert by_url['https://a.test/moved']['redirected_to'] == 'https://a.test/new-home'
    assert by_url['https://a.test/ok']['redirected_to'] is None
    assert limiter.calls.count('a.test') == 3


def test_skips_urls_denied_by_robots_without_fetching():
    fetched = []
    rows = audit_source_links.audit_links(
        ['https://b.test/blocked'],
        fetch=lambda url: fetched.append(url) or (200, url),
        robots=FakeRobots(denied={'https://b.test/blocked'}), throttle=FakeLimiter(),
    )
    assert rows[0]['robots_allowed'] is False
    assert fetched == []


def test_reports_transport_errors_without_crashing():
    def boom(_url):
        raise OSError('network down')
    rows = audit_source_links.audit_links(
        ['https://c.test/x'], fetch=boom, robots=FakeRobots(), throttle=FakeLimiter(),
    )
    assert rows[0]['error'] and rows[0]['status'] is None
