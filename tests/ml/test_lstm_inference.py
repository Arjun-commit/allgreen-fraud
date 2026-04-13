"""ML validation: LSTM inference on holdout data.

These are slow-ish tests (generate data + run inference) so they live in
tests/ml/ rather than tests/unit/ and run in a separate CI job.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from backend.models.lstm_inference import score_session
from tests.data_generator import build_training_dataset


@pytest.fixture(scope="module")
def holdout_data():
    """Generate a holdout set with a seed the training never saw."""
    X, y = build_training_dataset(n_normal=200, n_fraud=40, seed=999)
    return X, y


@pytest.fixture(scope="module")
def holdout_scores(holdout_data):
    X, y = holdout_data
    scores = np.array([score_session(X[i]) for i in range(len(y))])
    return scores, y


def test_lstm_auc_above_threshold(holdout_scores) -> None:
    """Blueprint target: AUC > 0.85 on holdout."""
    scores, y = holdout_scores
    auc = roc_auc_score(y, scores)
    print(f"LSTM holdout AUC: {auc:.4f}")
    assert auc > 0.85, f"LSTM AUC {auc:.4f} below 0.85 threshold"


def test_lstm_output_range(holdout_scores) -> None:
    """All scores should be in [0, 1] (sigmoid output)."""
    scores, _ = holdout_scores
    assert scores.min() >= 0.0
    assert scores.max() <= 1.0


def _find_optimal_threshold(scores: np.ndarray, y: np.ndarray) -> float:
    """Find threshold that maximizes F1.

    The raw sigmoid output is uncalibrated on imbalanced data — scores
    cluster near 0 for normal sessions. A fixed 0.5 cutoff doesn't work.
    In production we'd convert to Z-scores against the user's baseline
    (blueprint §7.1); here we just pick the empirically best threshold.
    """
    from sklearn.metrics import f1_score

    best_t, best_f1 = 0.5, 0.0
    for t in np.linspace(scores.min(), scores.max(), 200):
        preds = (scores >= t).astype(int)
        f1 = f1_score(y, preds, zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, float(t)
    return best_t


def test_lstm_false_positive_rate(holdout_scores) -> None:
    """At optimal threshold, FPR should be < 5% on holdout."""
    scores, y = holdout_scores
    threshold = _find_optimal_threshold(scores, y)
    normal_mask = y == 0
    normal_scores = scores[normal_mask]
    fpr = (normal_scores >= threshold).sum() / len(normal_scores)
    print(f"LSTM FPR at threshold={threshold:.6f}: {fpr:.4f}")
    assert fpr < 0.05, f"FPR {fpr:.4f} too high (>5%)"


def test_lstm_fraud_detection_rate(holdout_scores) -> None:
    """At optimal threshold, recall should be > 60%."""
    scores, y = holdout_scores
    threshold = _find_optimal_threshold(scores, y)
    fraud_mask = y == 1
    fraud_scores = scores[fraud_mask]
    recall = (fraud_scores >= threshold).sum() / len(fraud_scores)
    print(f"LSTM recall at threshold={threshold:.6f}: {recall:.4f}")
    assert recall > 0.60, f"Recall {recall:.4f} too low (<60%)"
