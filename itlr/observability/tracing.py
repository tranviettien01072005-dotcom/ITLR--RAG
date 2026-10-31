"""Optional OpenTelemetry tracing.

Disabled unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set (or an exporter is injected in tests),
so a laptop without the monitoring profile pays nothing. Span attributes must stay
low-cardinality and never contain query text, prompts, user ids or secrets.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

_TRACER = None
_ENABLED = False


def init_tracing(service_name: str = "itlr-api", exporter=None) -> bool:
    """Initialise once; return True when spans are exported."""
    global _TRACER, _ENABLED
    if _ENABLED:
        return True
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if exporter is None and not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        if exporter is None:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            target = endpoint if endpoint.endswith("/v1/traces") else endpoint.rstrip("/") + "/v1/traces"
            exporter = OTLPSpanExporter(endpoint=target)
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _TRACER = trace.get_tracer(service_name)
        _ENABLED = True
        return True
    except Exception:  # noqa: BLE001 — observability must never break serving
        _TRACER = None
        _ENABLED = False
        return False


def reset_tracing() -> None:
    """Test helper: allow a later init_tracing() to configure an exporter."""
    global _TRACER, _ENABLED
    _TRACER = None
    _ENABLED = False


@contextmanager
def span(name: str, **attributes):
    """No-op context manager when tracing is disabled."""
    if not _ENABLED or _TRACER is None:
        yield None
        return
    with _TRACER.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield current
