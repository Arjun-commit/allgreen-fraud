"""Prometheus metrics middleware.

Instruments every request with latency, count, and status code. Also
exposes custom metrics for model inference and business logic.
"""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger()

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    PROM_AVAILABLE = True
except ImportError:
    PROM_AVAILABLE = False


if PROM_AVAILABLE:
    REQUEST_COUNT = Counter(
        "allgreen_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )

    REQUEST_LATENCY = Histogram(
        "allgreen_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0, 2.5),
    )

    SCORING_LATENCY = Histogram(
        "allgreen_scoring_pipeline_duration_seconds",
        "Full scoring pipeline latency",
        buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25),
    )

    LSTM_LATENCY = Histogram(
        "allgreen_lstm_inference_duration_seconds",
        "LSTM model inference latency",
        buckets=(0.001, 0.005, 0.01, 0.02, 0.05),
    )

    XGBOOST_LATENCY = Histogram(
        "allgreen_xgboost_inference_duration_seconds",
        "XGBoost model inference latency",
        buckets=(0.001, 0.005, 0.01, 0.02, 0.05),
    )

    ACTIVE_SESSIONS = Gauge(
        "allgreen_active_sessions",
        "Number of active scoring sessions",
    )

    RISK_SCORE_DISTRIBUTION = Histogram(
        "allgreen_risk_score",
        "Distribution of final risk scores",
        buckets=(10, 20, 30, 40, 45, 55, 65, 75, 80, 90, 100),
    )

    FRICTION_APPLIED = Counter(
        "allgreen_friction_applied_total",
        "Friction decisions by type",
        ["friction_type"],
    )

    CASES_RESOLVED = Counter(
        "allgreen_cases_resolved_total",
        "Analyst case resolutions",
        ["outcome"],
    )

    MODEL_DRIFT_AUC = Gauge(
        "allgreen_model_auc",
        "Latest model AUC (updated after each training run)",
        ["model"],
    )



def record_scoring_latency(duration_seconds: float) -> None:
    if PROM_AVAILABLE:
        SCORING_LATENCY.observe(duration_seconds)


def record_lstm_latency(duration_seconds: float) -> None:
    if PROM_AVAILABLE:
        LSTM_LATENCY.observe(duration_seconds)


def record_xgboost_latency(duration_seconds: float) -> None:
    if PROM_AVAILABLE:
        XGBOOST_LATENCY.observe(duration_seconds)


def record_risk_score(score: float) -> None:
    if PROM_AVAILABLE:
        RISK_SCORE_DISTRIBUTION.observe(score)


def record_friction(friction_type: str) -> None:
    if PROM_AVAILABLE:
        FRICTION_APPLIED.labels(friction_type=friction_type).inc()


def record_case_resolved(outcome: str) -> None:
    if PROM_AVAILABLE:
        CASES_RESOLVED.labels(outcome=outcome).inc()


def set_model_auc(model_name: str, auc: float) -> None:
    if PROM_AVAILABLE:
        MODEL_DRIFT_AUC.labels(model=model_name).set(auc)



class PrometheusMiddleware(BaseHTTPMiddleware):
    """Records request count + latency for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not PROM_AVAILABLE:
            return await call_next(request)

        path = request.url.path
        method = request.method

        # Normalize path to avoid high-cardinality labels
        # e.g., /v1/cases/abc-123 → /v1/cases/{id}
        normalized = _normalize_path(path)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        REQUEST_COUNT.labels(
            method=method,
            path=normalized,
            status=response.status_code,
        ).inc()

        REQUEST_LATENCY.labels(
            method=method,
            path=normalized,
        ).observe(duration)

        return response


def _normalize_path(path: str) -> str:
    """Reduce cardinality by replacing UUIDs and IDs with placeholders."""
    parts = path.strip("/").split("/")
    normalized = []
    for i, part in enumerate(parts):
        # UUID-ish or numeric ID after a resource name
        if i > 0 and (len(part) > 8 and "-" in part or part.isdigit()):
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized)



async def metrics_endpoint(request: Request) -> Response:
    """Expose Prometheus metrics in text format."""
    if not PROM_AVAILABLE:
        return Response(
            content="# prometheus_client not installed\n",
            media_type="text/plain",
        )
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
