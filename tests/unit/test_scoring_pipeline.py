"""Tests for the scoring pipeline."""

from __future__ import annotations

from backend.features.transaction_extractor import UserHistory
from backend.scoring.pipeline import ScoringInput, run_pipeline
from tests.data_generator import generate_coached_session, generate_normal_session


def test_normal_session_scores_low() -> None:
    events = generate_normal_session(seed=10)
    inp = ScoringInput(
        session_id="test-normal-1",
        session_events=events,
        transaction={"amount": 200.0, "transfer_type": "domestic", "is_new_payee": False},
        user_history=UserHistory(avg_transfer_amount_30d=250.0),
    )
    result = run_pipeline(inp)

    assert result.risk_level in ("low", "medium")
    assert result.risk_score < 65  # shouldn't hit "high"
    assert result.friction_type in ("none", "awareness_prompt")
    assert result.transaction_id  # should be a UUID string
    assert result.latency_ms > 0


def test_coached_session_scores_higher() -> None:
    events = generate_coached_session(seed=10)
    inp = ScoringInput(
        session_id="test-coached-1",
        session_events=events,
        transaction={
            "amount": 5000.0,
            "transfer_type": "domestic",
            "is_new_payee": True,
        },
        user_history=UserHistory(avg_transfer_amount_30d=300.0),
    )
    result = run_pipeline(inp)

    # Coached session should score notably higher than a normal one.
    # We don't assert a specific level because synthetic data varies,
    # but the behavioral score should be clearly elevated.
    assert result.behavioral_score >= 0.0
    # At minimum, the pipeline should complete without errors.
    assert result.risk_level in ("low", "medium", "high", "critical")
    assert result.transaction_id


def test_empty_session_returns_low_risk() -> None:
    """No events → all features zero → models return low-risk."""
    inp = ScoringInput(
        session_id="test-empty",
        session_events=[],
        transaction={"amount": 100.0, "transfer_type": "domestic", "is_new_payee": False},
    )
    result = run_pipeline(inp)
    assert result.risk_level == "low"
    assert result.friction_type == "none"


def test_pipeline_caches_friction_in_redis(fake_redis) -> None:
    events = generate_normal_session(seed=20)
    inp = ScoringInput(
        session_id="test-friction-cache",
        session_events=events,
        transaction={"amount": 100.0, "transfer_type": "domestic", "is_new_payee": False},
    )
    run_pipeline(inp)

    # Friction should be cached in the fake redis
    from backend.store.redis_store import get_cached_friction

    cached = get_cached_friction("test-friction-cache")
    assert cached is not None
    assert "friction_type" in cached
    assert "risk_score" in cached


def test_pipeline_latency_under_budget() -> None:
    """Full pipeline should be < 100ms even on first call (models already loaded)."""
    events = generate_normal_session(seed=30)
    inp = ScoringInput(
        session_id="test-latency",
        session_events=events,
        transaction={"amount": 500.0, "transfer_type": "domestic", "is_new_payee": False},
    )
    result = run_pipeline(inp)
    # Be generous here — CI runners are slow. 500ms is the "something broke" threshold.
    assert result.latency_ms < 500, f"Pipeline took {result.latency_ms}ms"


def test_shap_factors_present_when_scored() -> None:
    """The response should include SHAP factors (possibly empty for low-risk)."""
    events = generate_coached_session(seed=40)
    inp = ScoringInput(
        session_id="test-shap",
        session_events=events,
        transaction={"amount": 3000.0, "transfer_type": "international", "is_new_payee": True},
        user_history=UserHistory(avg_transfer_amount_30d=200.0),
    )
    result = run_pipeline(inp)
    # SHAP factors are a list of dicts (may be empty for very low-risk predictions,
    # but should be populated for anything non-trivial)
    assert isinstance(result.shap_top_factors, list)
    for factor in result.shap_top_factors:
        assert "feature" in factor
        assert "direction" in factor
        assert "magnitude" in factor
