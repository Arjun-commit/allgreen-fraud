"""XGBoost transaction-context fraud classifier.

The model itself is vanilla — the magic is in the features, not the
algorithm. We lean heavily on scale_pos_weight to handle the 1:50-ish
class imbalance, and eval_metric='aucpr' because precision-recall AUC
is what matters when you're catching 1% fraud at high precision.
"""

from __future__ import annotations

import xgboost as xgb


def build_classifier(
    n_estimators: int = 300,
    max_depth: int = 6,
    learning_rate: float = 0.05,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
    scale_pos_weight: float = 10.0,
    seed: int = 42,
) -> xgb.XGBClassifier:
    """Build the XGBClassifier with default hyperparams.

    scale_pos_weight is set to 10 for synthetic data (10:1 ratio).
    Real training would use ~50 based on actual class distribution.
    """
    return xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        use_label_encoder=False,
        random_state=seed,
        verbosity=0,
    )
