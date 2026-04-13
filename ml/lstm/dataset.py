"""PyTorch Dataset for session-level behavioral sequences."""

from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import Dataset


class SessionSequenceDataset(Dataset):
    """Wraps (X, y) numpy arrays into a torch Dataset.

    X shape: (n_samples, seq_len, n_features)
    y shape: (n_samples,)
    """

    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.from_numpy(X).float()
        self.y = torch.from_numpy(y).float().unsqueeze(1)  # (n, 1) for BCE

    def __len__(self) -> int:
        return self.X.shape[0]

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.X[idx], self.y[idx]
