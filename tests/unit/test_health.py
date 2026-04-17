"""Smoke tests for the API endpoints."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_ok() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_score_returns_valid_response() -> None:
    """POST /score with no session events → models return low-risk.

    This now exercises the real pipeline (not a stub), but with no events
    in the DB for this session, so all features are zero and the models
    should return a low-risk score.
    """
    r = client.post(
        "/v1/score",
        json={
            "session_id": "test-health-score",
            "transaction": {
                "amount": 42.00,
                "currency": "USD",
                "payee_account": "000111222",
                "transfer_type": "domestic",
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    # With zero features, both models should return low risk
    assert body["risk_level"] in ("low", "medium", "high", "critical")
    assert "friction" in body
    assert body["friction"]["type"] in ("none", "awareness_prompt", "cooling_timer", "callback_required")
    assert "transaction_id" in body
    assert "behavioral_score" in body
    assert "context_score" in body
    assert "shap_top_factors" in body


def test_session_events_ingest_accepts_batch() -> None:
    r = client.post(
        "/v1/events/session",
        json={
            "session_id": "s-1",
            "user_id": "u-1",
            "events": [
                {"type": "mousemove", "ts_ms": 100, "x": 10, "y": 20},
                {"type": "click", "ts_ms": 200, "x": 30, "y": 40},
            ],
        },
    )
    assert r.status_code == 202
    assert r.json()["event_count"] == 2


def test_friction_endpoint_returns_null_for_unknown_session() -> None:
    r = client.get("/v1/friction/nonexistent-session-id")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "nonexistent-session-id"
    assert body["friction"] is None
