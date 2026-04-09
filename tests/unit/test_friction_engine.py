"""Threshold boundary tests for friction selection."""

import pytest

from backend.friction.engine import decide, risk_level_for_score


@pytest.mark.parametrize(
    "score,level",
    [
        (0, "low"),
        (44.9, "low"),
        (45.0, "medium"),
        (64.9, "medium"),
        (65.0, "high"),
        (79.9, "high"),
        (80.0, "critical"),
        (100.0, "critical"),
    ],
)
def test_thresholds(score: float, level: str) -> None:
    assert risk_level_for_score(score) == level


def test_decide_low_returns_none() -> None:
    d = decide(10.0)
    assert d["friction_type"] == "none"
    assert d["payload"] is None


def test_decide_high_returns_cooling_timer() -> None:
    d = decide(70.0)
    assert d["friction_type"] == "cooling_timer"
    assert d["payload"] is not None
    assert d["payload"]["duration_seconds"] == 600


def test_decide_critical_returns_callback() -> None:
    d = decide(90.0)
    assert d["friction_type"] == "callback_required"
