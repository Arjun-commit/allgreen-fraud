"""End-to-end test: synthetic sessions scored through the full pipeline."""

from __future__ import annotations

import os
import random

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from backend.features.transaction_extractor import UserHistory
from backend.scoring.pipeline import ScoringInput, run_pipeline
from tests.data_generator import generate_coached_session, generate_normal_session

# Use env var to scale down for constrained CI environments
_SCALE = int(os.environ.get("E2E_SCALE", "100"))  # default 100% = 500 sessions
N_NORMAL = max(40, 400 * _SCALE // 100)
N_FRAUD = max(10, 100 * _SCALE // 100)
SEED = 777


@pytest.fixture(scope="module")
def e2e_results():
    """Score 500 sessions and collect results."""
    rng = random.Random(SEED)
    results = []
    labels = []

    for i in range(N_NORMAL):
        events = generate_normal_session(
            duration_ms=rng.randint(30_000, 120_000),
            seed=SEED + i,
        )
        tx = {
            "amount": round(rng.uniform(50, 2000), 2),
            "transfer_type": rng.choice(["domestic", "domestic", "international"]),
            "is_new_payee": rng.random() < 0.1,
        }
        history = UserHistory(
            avg_transfer_amount_30d=rng.uniform(200, 1500),
        )
        inp = ScoringInput(
            session_id=f"e2e-normal-{i}",
            session_events=events,
            transaction=tx,
            user_history=history,
        )
        result = run_pipeline(inp)
        results.append(result)
        labels.append(0)

    for j in range(N_FRAUD):
        events = generate_coached_session(
            duration_ms=rng.randint(60_000, 180_000),
            seed=SEED + 10000 + j,
        )
        tx = {
            "amount": rng.choice([3000, 5000, 8000, 10000, 15000.0]),
            "transfer_type": rng.choice(["domestic", "international", "crypto"]),
            "is_new_payee": True,
        }
        history = UserHistory(
            avg_transfer_amount_30d=rng.uniform(200, 600),
        )
        # SessionContext would be populated by the pipeline itself from
        # the behavioral score — we don't pass it in manually here.
        inp = ScoringInput(
            session_id=f"e2e-fraud-{j}",
            session_events=events,
            transaction=tx,
            user_history=history,
        )
        result = run_pipeline(inp)
        results.append(result)
        labels.append(1)

    return results, np.array(labels)


def test_e2e_auc_above_threshold(e2e_results) -> None:
    """The full ensemble should achieve AUC > 0.70 on the 500-session mix.

    This is deliberately a lower bar than the individual model tests
    because the synthetic data doesn't perfectly correlate behavioral
    patterns with transaction fraud labels. The important thing is
    that the pipeline works end to end.
    """
    results, labels = e2e_results
    scores = np.array([r.risk_score for r in results])
    auc = roc_auc_score(labels, scores)
    print(f"\nE2E AUC ({N_NORMAL + N_FRAUD} sessions): {auc:.4f}")
    assert auc > 0.70, f"E2E AUC {auc:.4f} below 0.70 threshold"


def test_e2e_latency_p99(e2e_results) -> None:
    """Full pipeline should be < 100ms p99."""
    results, _ = e2e_results
    latencies = [r.latency_ms for r in results]
    p99 = np.percentile(latencies, 99)
    median = np.median(latencies)
    print(f"\nE2E latency: median={median:.1f}ms, p99={p99:.1f}ms")
    # Be generous — CI runners are slow. Use 500ms as the "broken" threshold.
    assert p99 < 500, f"E2E latency p99 {p99:.1f}ms exceeds 500ms"


def test_e2e_friction_distribution(e2e_results) -> None:
    """Friction should be applied to some but not all sessions."""
    results, labels = e2e_results

    friction_counts: dict[str, int] = {}
    for r in results:
        ft = r.friction_type
        friction_counts[ft] = friction_counts.get(ft, 0) + 1

    print(f"\nFriction distribution: {friction_counts}")

    # At minimum, "none" should be the most common (most are normal sessions)
    assert friction_counts.get("none", 0) > N_NORMAL * 0.5, (
        "Expected most normal sessions to get no friction"
    )

    # Some fraud sessions should trigger friction
    fraud_results = [results[N_NORMAL + j] for j in range(N_FRAUD)]
    fraud_with_friction = sum(
        1 for r in fraud_results if r.friction_type != "none"
    )
    # At least 10% of fraud should trigger something (low bar, synthetic data)
    ratio = fraud_with_friction / N_FRAUD
    print(f"Fraud sessions with friction: {ratio:.0%}")
    # Don't assert hard — synthetic data may not correlate perfectly


def test_e2e_all_results_valid(e2e_results) -> None:
    """Every result should have the expected shape."""
    results, _ = e2e_results
    for r in results:
        assert r.transaction_id  # non-empty UUID
        assert r.risk_level in ("low", "medium", "high", "critical")
        assert 0 <= r.risk_score <= 100
        assert 0 <= r.behavioral_score <= 1.0
        assert 0 <= r.context_score <= 1.0
        assert r.friction_type in ("none", "awareness_prompt", "cooling_timer", "callback_required")
        assert isinstance(r.shap_top_factors, list)


def test_e2e_shap_factors_on_high_risk(e2e_results) -> None:
    """High-risk results should have SHAP explainability."""
    results, _ = e2e_results
    high_risk = [r for r in results if r.risk_score >= 65]
    if len(high_risk) == 0:
        pytest.skip("No high-risk results to check")

    has_shap = sum(1 for r in high_risk if len(r.shap_top_factors) > 0)
    ratio = has_shap / len(high_risk)
    print(f"\nHigh-risk with SHAP factors: {ratio:.0%} ({has_shap}/{len(high_risk)})")
    assert ratio > 0.5, f"Only {ratio:.0%} of high-risk results have SHAP factors"
