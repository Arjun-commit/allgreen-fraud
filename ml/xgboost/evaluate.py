"""Evaluate saved XGBoost model on holdout data."""

from __future__ import annotations

import os
import sys

import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from tests.data_generator import build_xgboost_dataset

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def evaluate(threshold: float = 0.5, seed: int = 999) -> dict:
    model_path = os.path.join(ARTIFACTS_DIR, "model.json")
    clf = xgb.XGBClassifier()
    clf.load_model(model_path)

    X, y = build_xgboost_dataset(n_normal=200, n_fraud=40, seed=seed)
    probs = clf.predict_proba(X)[:, 1]
    auc = roc_auc_score(y, probs)

    binary = (probs >= threshold).astype(int)
    report = classification_report(y, binary, output_dict=True)

    return {
        "auc": auc,
        "threshold": threshold,
        "precision": report["1.0"]["precision"],
        "recall": report["1.0"]["recall"],
        "f1": report["1.0"]["f1-score"],
    }


if __name__ == "__main__":
    m = evaluate()
    for k, v in m.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
