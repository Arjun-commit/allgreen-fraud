"""LSTM inference wrapper. Loads the model once and keeps it in memory.

Thread-safe since torch forward passes are read-only on the weights.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import torch

from backend.config import get_settings

_model: Any | None = None  # lazy-loaded BehaviorLSTM


def _load_model() -> Any:
    from ml.lstm.model import BehaviorLSTM

    settings = get_settings()
    path = settings.lstm_model_path

    # Dev fallback: if the container path doesn't exist, try the repo-relative path.
    if not os.path.exists(path):
        repo_path = os.path.join(
            os.path.dirname(__file__), "../../ml/lstm/artifacts/model.pt"
        )
        if os.path.exists(repo_path):
            path = repo_path

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"LSTM model not found at {path}. Run `python -m ml.lstm.train` first."
        )

    model = BehaviorLSTM()
    model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    model.eval()
    return model


def get_model() -> Any:
    global _model
    if _model is None:
        _model = _load_model()
    return _model


def reset_model() -> None:
    """For tests — force a reload on next call."""
    global _model
    _model = None


def score_session(feature_sequence: np.ndarray) -> float:
    """Score a single session.

    Args:
        feature_sequence: shape (seq_len, n_features) — the windowed
            behavioral features for one session.

    Returns:
        Anomaly score in [0, 1]. Higher = more likely coached/fraud.
    """
    model = get_model()
    # Add batch dim: (1, seq_len, features)
    x = torch.from_numpy(feature_sequence).float().unsqueeze(0)
    with torch.no_grad():
        score = model(x).item()
    return float(score)
