"""Unit-test fixtures — patches ML inference so no model artifacts are needed."""

from __future__ import annotations

from unittest.mock import patch

import pytest


def _fake_lstm_score(feature_sequence):
    """Return a low anomaly score. Good enough for pipeline plumbing tests."""
    return 0.05


def _fake_xgb_score(feature_vector, feature_names=None, top_k_shap=5):
    """Return a low fraud prob with one fake SHAP factor."""
    return 0.08, [
        {"feature": "amount_usd", "direction": "increases_risk", "magnitude": 0.12},
    ]


@pytest.fixture(autouse=True)
def fake_models():
    """Patch LSTM and XGBoost inference so unit tests skip model loading."""
    with (
        patch(
            "backend.scoring.pipeline.lstm_score",
            side_effect=_fake_lstm_score,
        ),
        patch(
            "backend.scoring.pipeline.xgb_score",
            side_effect=_fake_xgb_score,
        ),
        patch(
            "backend.models.lstm_inference.score_session",
            side_effect=_fake_lstm_score,
        ),
        patch(
            "backend.models.xgboost_inference.score_transaction",
            side_effect=_fake_xgb_score,
        ),
    ):
        yield
