"""Tests for the maker-checker threshold settings API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_thresholds_returns_defaults() -> None:
    r = client.get("/v1/settings/thresholds")
    assert r.status_code == 200
    body = r.json()
    assert "thresholds" in body
    assert body["thresholds"]["medium"] == 45.0
    assert body["thresholds"]["high"] == 65.0
    assert body["thresholds"]["critical"] == 80.0


def test_propose_and_approve_threshold_change() -> None:
    """Full maker-checker flow: propose → approve by different user."""
    # Step 1: propose
    r = client.post(
        "/v1/settings/thresholds",
        json={
            "medium": 50,
            "high": 70,
            "critical": 85,
            "requested_by": "analyst_alice",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    change_id = body["change_id"]

    # Step 2: approve by a different analyst
    r2 = client.post(
        f"/v1/settings/thresholds/{change_id}/approve",
        json={"approved_by": "analyst_bob"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["status"] == "approved"
    assert body2["active_thresholds"]["medium"] == 50
    assert body2["active_thresholds"]["high"] == 70
    assert body2["active_thresholds"]["critical"] == 85


def test_cannot_approve_own_change() -> None:
    """Maker-checker: same person can't approve their own change."""
    r = client.post(
        "/v1/settings/thresholds",
        json={
            "medium": 40,
            "high": 60,
            "critical": 75,
            "requested_by": "analyst_alice",
        },
    )
    change_id = r.json()["change_id"]

    r2 = client.post(
        f"/v1/settings/thresholds/{change_id}/approve",
        json={"approved_by": "analyst_alice"},  # same person!
    )
    assert r2.status_code == 403
    assert "maker-checker" in r2.json()["detail"].lower()


def test_reject_threshold_change() -> None:
    r = client.post(
        "/v1/settings/thresholds",
        json={
            "medium": 55,
            "high": 72,
            "critical": 88,
            "requested_by": "analyst_carol",
        },
    )
    change_id = r.json()["change_id"]

    r2 = client.post(
        f"/v1/settings/thresholds/{change_id}/reject",
        json={"rejected_by": "analyst_dave", "reason": "Too aggressive"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"


def test_invalid_threshold_ordering() -> None:
    """medium must be < high < critical."""
    r = client.post(
        "/v1/settings/thresholds",
        json={
            "medium": 70,
            "high": 60,  # wrong order!
            "critical": 80,
            "requested_by": "analyst_eve",
        },
    )
    assert r.status_code == 422


def test_approve_nonexistent_change() -> None:
    r = client.post(
        "/v1/settings/thresholds/nonexistent-id/approve",
        json={"approved_by": "analyst_bob"},
    )
    assert r.status_code == 404
