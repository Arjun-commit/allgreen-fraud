"""XGBoost inference wrapper.

Same pattern as the LSTM wrapper: load once, serve forever.

Usage:
    from backend.models.xgboost_inference import score_transaction
    prob, shap_factors = score_transaction(feature_vector)

Note: we use XGBoost's native `pred_contribs=True` for feature contributions
instead of the shap library, because shap.TreeExplainer has a known
compatibility bug with recent XGBoost versions (base_score format issue).
The native contribs are mathematically equivalent and faster anyway.
"""

from __future__ import annotations

import os

import numpy as np
import xgboost as xgb

from backend.config import get_settings

_model: xgb.XGBClassifier | None = None
_booster: xgb.Booster | None = None


def _load_model() -> xgb.XGBClassifier:
    settings = get_settings()
    path = settings.xgboost_model_path

    if not os.path.exists(path):
        repo_path = os.path.join(
            os.path.dirname(__file__), "../../ml/xgboost/artifacts/model.json"
        )
        if os.path.exists(repo_path):
            path = repo_path

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"XGBoost model not found at {path}. Run `python -m ml.xgboost.train` first."
        )

    clf = xgb.XGBClassifier()
    clf.load_model(path)
    return clf


def get_model() -> xgb.XGBClassifier:
    global _model, _booster
    if _model is None:
        _model = _load_model()
        _booster = _model.get_booster()
    return _model


def reset_model() -> None:
    """For tests."""
    global _model, _booster
    _model = None
    _booster = None


def score_transaction(
    feature_vector: np.ndarray,
    feature_names: list[str] | None = None,
    top_k_shap: int = 5,
) -> tuple[float, list[dict]]:
    """Score a single transaction.

    Args:
        feature_vector: shape (n_features,).
        feature_names: optional list for labelling SHAP output.
        top_k_shap: how many SHAP factors to return.

    Returns:
        (probability_of_fraud, top_shap_factors)
        where each factor is {"feature": str, "direction": str, "magnitude": float}.
    """
    clf = get_model()
    x = feature_vector.reshape(1, -1)
    prob = float(clf.predict_proba(x)[0, 1])

    # Feature contributions via XGBoost's native pred_contribs.
    # Returns (1, n_features+1) — last column is the bias term.
    shap_factors: list[dict] = []
    try:
        dmat = xgb.DMatrix(x)
        contribs = _booster.predict(dmat, pred_contribs=True)[0]  # type: ignore[union-attr]
        # Drop the bias (last element)
        feature_contribs = contribs[:-1]
        names = feature_names or [f"f{i}" for i in range(len(feature_contribs))]

        indices = np.argsort(np.abs(feature_contribs))[::-1][:top_k_shap]
        for idx in indices:
            val = float(feature_contribs[idx])
            if abs(val) < 1e-6:
                continue
            shap_factors.append(
                {
                    "feature": names[idx],
                    "direction": "increases_risk" if val > 0 else "decreases_risk",
                    "magnitude": round(abs(val), 4),
                }
            )
    except Exception:
        # Explainability shouldn't block scoring. If it fails we still
        # have the probability. Log and move on.
        pass

    return prob, shap_factors
