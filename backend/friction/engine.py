"""Risk score → intervention mapping.

Phase 1: thresholds + lookup only. Phase 4 wires this into the /score path
and publishes `friction.decisions` events.
"""

from typing import Literal, TypedDict

from backend.friction.interventions import FRICTION_TYPES

RiskLevel = Literal["low", "medium", "high", "critical"]


class FrictionDecision(TypedDict):
    friction_type: str  # "none" | one of FRICTION_TYPES keys
    payload: dict | None


# Thresholds live here so tests and docs have one place to look.
# The exact boundaries come from blueprint §9 and will be tunable from the
# Settings page (maker-checker flow, phase 6).
THRESHOLDS = {
    "medium": 45.0,
    "high": 65.0,
    "critical": 80.0,
}


def risk_level_for_score(score: float) -> RiskLevel:
    if score < THRESHOLDS["medium"]:
        return "low"
    if score < THRESHOLDS["high"]:
        return "medium"
    if score < THRESHOLDS["critical"]:
        return "high"
    return "critical"


def decide(score: float) -> FrictionDecision:
    level = risk_level_for_score(score)
    mapping: dict[RiskLevel, str] = {
        "low": "none",
        "medium": "awareness_prompt",
        "high": "cooling_timer",
        "critical": "callback_required",
    }
    ftype = mapping[level]
    return {
        "friction_type": ftype,
        "payload": FRICTION_TYPES.get(ftype),
    }
