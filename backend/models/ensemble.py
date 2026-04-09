"""Aggregate LSTM + XGBoost scores into a single risk level.

The ensemble weighting comes from blueprint §7.3. Behavioral gets more
weight because it's our unique signal — the XGBoost context model is
largely overlap with what the existing tools already flag.
"""

from typing import Literal, TypedDict

W_BEHAVIORAL = 0.60
W_CONTEXT = 0.40


class RiskResult(TypedDict):
    final_score: float  # 0-100
    risk_level: Literal["low", "medium", "high", "critical"]


def aggregate_risk(behavioral_z: float, context_prob: float) -> RiskResult:
    """behavioral_z and context_prob are both in [0, 1]."""
    raw = (behavioral_z * W_BEHAVIORAL) + (context_prob * W_CONTEXT)
    final_score = round(raw * 100.0, 1)

    # Bucketing mirrors friction.engine.risk_level_for_score.
    # Duplicated intentionally — the friction module shouldn't depend on models
    # and vice versa. We keep them in sync via tests.
    if final_score < 45:
        level: Literal["low", "medium", "high", "critical"] = "low"
    elif final_score < 65:
        level = "medium"
    elif final_score < 80:
        level = "high"
    else:
        level = "critical"

    return {"final_score": final_score, "risk_level": level}
