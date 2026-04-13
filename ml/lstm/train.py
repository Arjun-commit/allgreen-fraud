"""Train the global BehaviorLSTM on synthetic data.

Usage:
    python -m ml.lstm.train [--epochs 30] [--lr 0.001]

Saves:
    ml/lstm/artifacts/model.pt
    ml/lstm/artifacts/metrics.json

In a real deployment this would use MLflow for experiment tracking +
model registry. We'll wire that up when the MLflow container is live.
For now we just dump metrics to JSON so the ML validation tests can
pick them up.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader

# So we can run this from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ml.lstm.dataset import SessionSequenceDataset
from ml.lstm.model import BehaviorLSTM
from tests.data_generator import build_training_dataset

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def train(
    epochs: int = 30,
    lr: float = 0.001,
    batch_size: int = 64,
    n_normal: int = 1000,
    n_fraud: int = 100,
    seed: int = 42,
) -> dict:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    torch.manual_seed(seed)
    np.random.seed(seed)

    print(f"generating synthetic data: {n_normal} normal, {n_fraud} fraud")
    X, y = build_training_dataset(n_normal, n_fraud, seed=seed)

    # 80/20 split, stratified-ish (just take last 20%)
    split = int(len(y) * 0.8)
    train_ds = SessionSequenceDataset(X[:split], y[:split])
    val_ds = SessionSequenceDataset(X[split:], y[split:])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)

    model = BehaviorLSTM(input_size=X.shape[2])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.BCELoss()

    best_auc = 0.0
    best_state = None
    history: list[dict] = []

    print(f"training for {epochs} epochs...")
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * xb.size(0)
        train_loss /= len(train_ds)

        # Validation
        model.eval()
        val_preds, val_labels = [], []
        with torch.no_grad():
            for xb, yb in val_loader:
                pred = model(xb)
                val_preds.append(pred.numpy())
                val_labels.append(yb.numpy())
        val_preds_np = np.concatenate(val_preds).flatten()
        val_labels_np = np.concatenate(val_labels).flatten()

        # AUC needs both classes present
        if len(np.unique(val_labels_np)) > 1:
            auc = roc_auc_score(val_labels_np, val_preds_np)
        else:
            auc = 0.0

        history.append({"epoch": epoch, "train_loss": train_loss, "val_auc": auc})

        if epoch % 5 == 0 or epoch == 1:
            print(f"  epoch {epoch:3d} | loss {train_loss:.4f} | val AUC {auc:.4f}")

        if auc > best_auc:
            best_auc = auc
            best_state = model.state_dict().copy()

    # Save best model
    if best_state is None:
        best_state = model.state_dict()
    model_path = os.path.join(ARTIFACTS_DIR, "model.pt")
    torch.save(best_state, model_path)
    print(f"saved model → {model_path} (best val AUC: {best_auc:.4f})")

    metrics = {
        "best_val_auc": best_auc,
        "epochs": epochs,
        "n_normal": n_normal,
        "n_fraud": n_fraud,
        "history": history,
    }
    metrics_path = os.path.join(ARTIFACTS_DIR, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--n-normal", type=int, default=1000)
    parser.add_argument("--n-fraud", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    t0 = time.time()
    metrics = train(
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        n_normal=args.n_normal,
        n_fraud=args.n_fraud,
        seed=args.seed,
    )
    elapsed = time.time() - t0
    print(f"\ndone in {elapsed:.1f}s. best AUC: {metrics['best_val_auc']:.4f}")


if __name__ == "__main__":
    main()
