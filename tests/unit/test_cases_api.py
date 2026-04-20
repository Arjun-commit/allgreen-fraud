"""Tests for the analyst case management API endpoints.

These hit the demo-data fallback since we don't spin up Postgres in unit tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


# ---------- GET /cases ----------

def test_list_cases_returns_items() -> None:
    r = client.get("/v1/cases")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert body["total"] > 0, "Demo seed should produce cases"


def test_list_cases_pagination() -> None:
    r = client.get("/v1/cases", params={"page": 1, "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 5
    assert body["limit"] == 5


def test_list_cases_filter_by_status() -> None:
    r = client.get("/v1/cases", params={"status": "open"})
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["status"] == "open"


def test_list_cases_filter_by_min_score() -> None:
    r = client.get("/v1/cases", params={"min_score": 70})
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["risk_score"] >= 70


def test_list_cases_item_shape() -> None:
    """Each case should have the required fields for the alert feed."""
    r = client.get("/v1/cases", params={"limit": 1})
    body = r.json()
    assert len(body["items"]) >= 1
    item = body["items"][0]
    required = [
        "case_id", "transaction_id", "session_id", "user_id_masked",
        "amount", "risk_score", "risk_level", "status", "created_at",
    ]
    for field in required:
        assert field in item, f"Missing field: {field}"


# ---------- GET /cases/{case_id} ----------

def test_get_case_detail() -> None:
    # First get a case_id from the list
    r = client.get("/v1/cases", params={"limit": 1})
    case_id = r.json()["items"][0]["case_id"]

    r2 = client.get(f"/v1/cases/{case_id}")
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["case_id"] == case_id
    # Detail should have extra fields beyond the summary
    assert "behavioral_score" in detail
    assert "context_score" in detail
    assert "shap_factors" in detail
    assert isinstance(detail["shap_factors"], list)


def test_get_case_not_found() -> None:
    r = client.get("/v1/cases/nonexistent-case-id")
    assert r.status_code == 404


# ---------- POST /cases/{case_id}/resolve ----------

def test_resolve_case_confirmed_fraud() -> None:
    r = client.get("/v1/cases", params={"limit": 1})
    case_id = r.json()["items"][0]["case_id"]

    r2 = client.post(
        f"/v1/cases/{case_id}/resolve",
        json={"outcome": "confirmed_fraud", "notes": "Verified via callback."},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["outcome"] == "confirmed_fraud"
    assert body["status"] == "resolved"


def test_resolve_case_legitimate() -> None:
    r = client.get("/v1/cases", params={"limit": 1})
    case_id = r.json()["items"][0]["case_id"]

    r2 = client.post(
        f"/v1/cases/{case_id}/resolve",
        json={"outcome": "legitimate"},
    )
    assert r2.status_code == 200
    assert r2.json()["outcome"] == "legitimate"


def test_resolve_case_invalid_outcome() -> None:
    """Invalid outcome should be rejected by pydantic."""
    r = client.get("/v1/cases", params={"limit": 1})
    case_id = r.json()["items"][0]["case_id"]

    r2 = client.post(
        f"/v1/cases/{case_id}/resolve",
        json={"outcome": "not_a_valid_outcome"},
    )
    assert r2.status_code == 422  # validation error


# ---------- GET /analytics/model-performance ----------

def test_model_performance_endpoint() -> None:
    r = client.get("/v1/analytics/model-performance")
    assert r.status_code == 200
    body = r.json()
    assert "period" in body
    assert "lstm" in body
    assert "xgboost" in body
    assert "ensemble" in body
    assert "friction_effectiveness" in body


def test_model_performance_has_friction_stats() -> None:
    r = client.get("/v1/analytics/model-performance")
    body = r.json()
    fe = body["friction_effectiveness"]
    assert "soft_friction_abandon_rate" in fe
    assert "hard_block_scam_confirmation_rate" in fe


# ---------- GET /analytics/score-distribution ----------

def test_score_distribution_endpoint() -> None:
    r = client.get("/v1/analytics/score-distribution")
    assert r.status_code == 200
    body = r.json()
    assert "buckets" in body
    assert "current_week" in body
    assert "last_week" in body
    assert len(body["buckets"]) == 10  # 0-10, 10-20, ... 90-100
    assert len(body["current_week"]) == 10
