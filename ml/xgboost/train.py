"""Train XGBoost fraud classifier on synthetic data.

Usage:
    python -m ml.xgboost.train

Saves:
    ml/xgboost/artifacts/model.json
    ml/xgboost/artifacts/metrics.json
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ml.xgboost.model import build_classifier
from tests.data_generator import build_xgboost_dataset

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def train(
    n_normal: int = 1000,
    n_fraud: int = 100,
    seed: int = 42,
) -> dict:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    np.random.seed(seed)

    print(f"generating synthetic data: {n_normal} normal, {n_fraud} fraud")
    X, y = build_xgboost_dataset(n_normal, n_fraud, seed=seed)

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )

    clf = build_classifier(
        scale_pos_weight=float(np.sum(y_train == 0)) / max(np.sum(y_train == 1), 1),
        seed=seed,
    )

    print(f"training XGBoost (n_estimators={clf.n_estimators})...")
    clf.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # Evaluate
    val_probs = clf.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, val_probs)
    print(f"val AUC: {auc:.4f}")

    # Feature importance (gain)
    importances = clf.feature_importances_
    from backend.features.transaction_extractor import TRANSACTION_FEATURE_NAMES

    feat_imp = sorted(
        zip(TRANSACTION_FEATURE_NAMES, importances, strict=False),
        key=lambda x: x[1],
        reverse=True,
    )
    print("top features:")
    for name, imp in feat_imp[:5]:
        print(f"  {name}: {imp:.4f}")

    # Save model
    model_path = os.path.join(ARTIFACTS_DIR, "model.json")
    clf.save_model(model_path)
    print(f"saved model → {model_path}")

    metrics = {
        "val_auc": auc,
        "n_train": len(y_train),
        "n_val": len(y_val),
        "n_fraud_train": int(np.sum(y_train == 1)),
        "feature_importances": {n: float(v) for n, v in feat_imp},
    }
    metrics_path = os.path.join(ARTIFACTS_DIR, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


def main() -> None:
    t0 = time.time()
    metrics = train()
    elapsed = time.time() - t0
    print(f"\ndone in {elapsed:.1f}s. AUC: {metrics['val_auc']:.4f}")


if __name__ == "__main__":
    main()
