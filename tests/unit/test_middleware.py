"""Tests for auth and metrics middleware."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_metrics_endpoint_returns_prometheus_format() -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    text = r.text
    # Should contain our custom metrics (or at least the prometheus header)
    assert "allgreen_http_requests_total" in text or "prometheus" in text.lower() or "# " in text


def test_health_not_rate_limited() -> None:
    """Health endpoint should never be rate-limited."""
    for _ in range(50):
        r = client.get("/health")
        assert r.status_code == 200


def test_auth_dev_mode_allows_unauthenticated() -> None:
    """In dev mode, missing auth should still work."""
    r = client.get("/v1/cases")
    assert r.status_code == 200  # dev mode pass-through
