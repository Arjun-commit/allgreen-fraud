"""Dead-simple smoke tests for the phase-1 skeleton."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_ok() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_score_stub_returns_low_risk() -> None:
    r = client.post(
        "/v1/score",
        json={
            "session_id": "abc-123",
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
    assert body["risk_level"] == "low"
    assert body["friction"]["type"] == "none"


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
