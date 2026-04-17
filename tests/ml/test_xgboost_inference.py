"""ML validation: XGBoost inference on holdout data."""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from backend.features.transaction_extractor import TRANSACTION_FEATURE_NAMES
from backend.models.xgboost_inference import score_transaction
from tests.data_generator import build_xgboost_dataset


@pytest.fixture(scope="module")
def holdout_data():
    X, y = build_xgboost_dataset(n_normal=200, n_fraud=40, seed=999)
    return X, y


@pytest.fixture(scope="module")
def holdout_scores(holdout_data):
    X, y = holdout_data
    names = list(TRANSACTION_FEATURE_NAMES)
    probs = []
    all_shap = []
    for i in range(len(y)):
        prob, shap_factors = score_transaction(X[i], names)
        probs.append(prob)
        all_shap.append(shap_factors)
    return np.array(probs), y, all_shap


def test_xgboost_auc_above_threshold(holdout_scores) -> None:
    probs, y, _ = holdout_scores
    auc = roc_auc_score(y, probs)
    print(f"XGBoost holdout AUC: {auc:.4f}")
    assert auc > 0.85, f"XGBoost AUC {auc:.4f} below 0.85"


def test_xgboost_output_range(holdout_scores) -> None:
    probs, _, _ = holdout_scores
    assert probs.min() >= 0.0
    assert probs.max() <= 1.0


def test_xgboost_shap_present(holdout_scores) -> None:
    """At least some fraud predictions should have SHAP factors."""
    _, y, all_shap = holdout_scores
    fraud_indices = np.where(y == 1)[0]
    shap_present = sum(1 for i in fraud_indices if len(all_shap[i]) > 0)
    # At least half of fraud cases should have explainability data
    ratio = shap_present / len(fraud_indices)
    print(f"SHAP present on {ratio:.0%} of fraud cases")
    assert ratio > 0.5, f"Only {ratio:.0%} fraud cases have SHAP factors"


def test_xgboost_precision_at_threshold(holdout_scores) -> None:
    """At threshold 0.5, precision should be reasonable."""
    probs, y, _ = holdout_scores
    predicted_fraud = probs >= 0.5
    if predicted_fraud.sum() == 0:
        pytest.skip("No predictions above threshold")
    precision = y[predicted_fraud].sum() / predicted_fraud.sum()
    print(f"XGBoost precision at 0.5: {precision:.4f}")
    assert precision > 0.5, f"Precision {precision:.4f} too low"
