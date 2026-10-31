"""Observability contract: low-cardinality metrics, artifact info, optional tracing."""
import re

from fastapi.testclient import TestClient

from itlr.api.server import app
from itlr.observability import metrics as obs
from itlr.observability import tracing


def test_metrics_render_uses_route_templates_only():
    obs.observe_http("/api/search", "POST", 200, 0.012)
    body, content_type = obs.render_metrics()
    text = body.decode()
    assert content_type.startswith("text/plain")
    assert 'itlr_http_requests_total{method="POST",route="/api/search",status_class="2xx"}' in text
    assert "itlr_http_request_duration_seconds_bucket" in text
    # No query text, user id or message content can appear: labels are route/method/status only.
    assert "min_pct" not in text and "message" not in text


def test_artifact_info_keeps_only_the_loaded_snapshot():
    obs.set_artifact_info("v-old", "a" * 64, 10)
    obs.set_artifact_info("v-new", "b" * 64, 178)
    text = obs.render_metrics()[0].decode()
    assert 'itlr_artifact_info{manifest_sha256="' in text
    assert 'version="v-new"' in text
    assert 'version="v-old"' not in text
    assert re.search(r"itlr_artifact_items [0-9.]+", text)
    assert " 178" in text or "178.0" in text


def test_prometheus_endpoint_requires_token_and_returns_family_names(monkeypatch):
    monkeypatch.setenv("ITLR_ADMIN_TOKEN", "s3cret")
    client = TestClient(app)
    assert client.get("/metrics/prometheus").status_code == 403
    ok = client.get("/metrics/prometheus", headers={"X-Admin-Token": "s3cret"})
    assert ok.status_code == 200
    assert "itlr_http_requests_total" in ok.text


def test_tracing_is_disabled_without_otlp_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    tracing.reset_tracing()
    assert tracing.init_tracing("itlr-test") is False
    with tracing.span("retrieval.search", route="/api/search"):
        pass


def test_tracing_exports_spans_when_configured():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    tracing.reset_tracing()
    assert tracing.init_tracing("itlr-test", exporter=exporter) is True
    with tracing.span("generation.chat", provider="ollama", route="/api/chat"):
        pass
    from opentelemetry import trace
    trace.get_tracer_provider().force_flush()
    spans = exporter.get_finished_spans()
    assert [s.name for s in spans] == ["generation.chat"]
    assert spans[0].attributes["provider"] == "ollama"
