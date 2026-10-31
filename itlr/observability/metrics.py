"""Prometheus metrics for the RAG API (low cardinality, no prompt/PII labels).

Only route templates, status classes, provider/mode names, citation status and artifact
version (releases) are labels. Query text, user ids, item ids and prompts are never labels.
"""
from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

_BUCKETS_FAST = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
_BUCKETS_LLM = (0.5, 1, 2, 5, 10, 20, 30, 45, 60, 120, 240)

HTTP_REQUESTS = Counter(
    "itlr_http_requests", "API requests by route template, method and status class",
    ["route", "method", "status_class"])
HTTP_DURATION = Histogram(
    "itlr_http_request_duration_seconds", "API request duration",
    ["route", "method"], buckets=_BUCKETS_FAST)
RETRIEVAL_DURATION = Histogram(
    "itlr_retrieval_duration_seconds", "Search/retrieval duration (includes embedding)",
    ["kind"], buckets=_BUCKETS_FAST)
LLM_DURATION = Histogram(
    "itlr_llm_request_duration_seconds", "Generation duration (provider wall clock)",
    ["provider", "mode"], buckets=_BUCKETS_LLM)
LLM_TTFT = Histogram(
    "itlr_llm_ttft_seconds", "Time to first SSE text/token event", ["provider"],
    buckets=_BUCKETS_LLM)
LLM_TOKENS = Counter(
    "itlr_llm_tokens", "Provider-reported tokens (never content)", ["provider", "kind"])
GENERATION_MODES = Counter(
    "itlr_generation_modes", "Final generation mode", ["mode"])
CITATION_STATUS = Counter(
    "itlr_citation_status", "citation_validation status of final answers", ["status"])
SSE_STREAMS = Counter(
    "itlr_sse_streams", "SSE stream outcomes", ["result"])
SSE_DURATION = Histogram(
    "itlr_sse_stream_duration_seconds", "SSE stream duration", buckets=_BUCKETS_LLM)
ARTIFACT_INFO = Gauge(
    "itlr_artifact_info", "Loaded artifact snapshot (value is always 1)",
    ["version", "manifest_sha256"])
ARTIFACT_ITEMS = Gauge(
    "itlr_artifact_items", "Number of items in the loaded engine")


def observe_http(route: str, method: str, status: int, seconds: float) -> None:
    klass = f"{status // 100}xx"
    HTTP_REQUESTS.labels(route=route, method=method, status_class=klass).inc()
    HTTP_DURATION.labels(route=route, method=method).observe(seconds)


def observe_retrieval(kind: str, seconds: float) -> None:
    RETRIEVAL_DURATION.labels(kind=kind).observe(seconds)


def observe_llm(provider: str, mode: str, seconds: float) -> None:
    LLM_DURATION.labels(provider=provider, mode=mode).observe(seconds)


def observe_ttft(provider: str, seconds: float) -> None:
    LLM_TTFT.labels(provider=provider).observe(seconds)


def add_tokens(provider: str, prompt: int, completion: int) -> None:
    if prompt:
        LLM_TOKENS.labels(provider=provider, kind="prompt").inc(int(prompt))
    if completion:
        LLM_TOKENS.labels(provider=provider, kind="completion").inc(int(completion))


def observe_generation(mode: str, citation_status: str | None) -> None:
    GENERATION_MODES.labels(mode=mode or "unknown").inc()
    if citation_status:
        CITATION_STATUS.labels(status=citation_status).inc()


def observe_sse(result: str, seconds: float | None = None) -> None:
    SSE_STREAMS.labels(result=result).inc()
    if seconds is not None:
        SSE_DURATION.observe(seconds)


def set_artifact_info(version: str | None, manifest: str | None, items: int | None) -> None:
    """Keep only the currently loaded snapshot in the label set."""
    ARTIFACT_INFO.clear()
    if version or manifest:
        ARTIFACT_INFO.labels(version=version or "unknown",
                             manifest_sha256=(manifest or "")[:16]).set(1)
    if items is not None:
        ARTIFACT_ITEMS.set(int(items))


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
