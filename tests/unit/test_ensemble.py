"""Verify the ensemble aggregator buckets scores correctly.

Boundary tests — if you tune the thresholds, update these in lockstep.
"""

import pytest

from backend.models.ensemble import aggregate_risk


@pytest.mark.parametrize(
    "behavioral,context,expected_level",
    [
        (0.0, 0.0, "low"),
        (0.3, 0.3, "low"),
        (0.6, 0.5, "medium"),
        (0.8, 0.7, "high"),
        (1.0, 1.0, "critical"),
    ],
)
def test_aggregate_levels(behavioral: float, context: float, expected_level: str) -> None:
    r = aggregate_risk(behavioral, context)
    assert r["risk_level"] == expected_level
    assert 0 <= r["final_score"] <= 100


def test_weighting_favors_behavioral() -> None:
    # A pure behavioral signal should outscore a pure context signal
    # of equal magnitude, because w_behavioral > w_context.
    a = aggregate_risk(1.0, 0.0)
    b = aggregate_risk(0.0, 1.0)
    assert a["final_score"] > b["final_score"]
