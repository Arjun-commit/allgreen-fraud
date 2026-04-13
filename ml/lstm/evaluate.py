"""Evaluate a saved LSTM model against a holdout set.

Usage:
    python -m ml.lstm.evaluate

Loads model.pt from artifacts, generates a fresh holdout set (different seed
from training), prints metrics.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import torch
from sklearn.metrics import classification_report, roc_auc_score

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ml.lstm.dataset import SessionSequenceDataset
from ml.lstm.model import BehaviorLSTM
from tests.data_generator import build_training_dataset

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def evaluate(threshold: float = 0.5, seed: int = 999) -> dict:
    model_path = os.path.join(ARTIFACTS_DIR, "model.pt")
    model = BehaviorLSTM()
    model.load_state_dict(torch.load(model_path, weights_only=True))
    model.eval()

    # Generate holdout with a different seed than training
    X, y = build_training_dataset(n_normal=200, n_fraud=40, seed=seed)
    ds = SessionSequenceDataset(X, y)

    preds_list = []
    with torch.no_grad():
        for i in range(len(ds)):
            xb, _ = ds[i]
            pred = model(xb.unsqueeze(0))
            preds_list.append(pred.item())

    preds = np.array(preds_list)
    labels = y

    auc = roc_auc_score(labels, preds)
    binary_preds = (preds >= threshold).astype(int)
    report = classification_report(labels, binary_preds, output_dict=True)

    return {
        "auc": auc,
        "threshold": threshold,
        "precision": report["1.0"]["precision"],
        "recall": report["1.0"]["recall"],
        "f1": report["1.0"]["f1-score"],
    }


if __name__ == "__main__":
    metrics = evaluate()
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
