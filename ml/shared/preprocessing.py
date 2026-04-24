"""Shared normalization utils used in training + inference.

Z-score normalization per feature using running stats computed during
training. A more robust approach (quantile normalization, log transforms
on heavy-tailed features) comes once we have real data distributions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np


@dataclass
class FeatureNormalizer:
    """Per-feature z-score normalizer.

    Stores mean + std. Clips to [-5, 5] after normalization to avoid
    extreme outliers blowing up LSTM hidden state.
    """

    means: np.ndarray
    stds: np.ndarray
    clip_range: float = 5.0

    @classmethod
    def fit(cls, X: np.ndarray) -> FeatureNormalizer:
        """Fit on data shaped (n_samples, ..., n_features).

        Last dim is always features. Flatten everything else.
        """
        flat = X.reshape(-1, X.shape[-1])
        means = flat.mean(axis=0)
        stds = flat.std(axis=0)
        # Prevent div-by-zero on constant features
        stds[stds < 1e-8] = 1.0
        return cls(means=means, stds=stds)

    def transform(self, X: np.ndarray) -> np.ndarray:
        z = (X - self.means) / self.stds
        return np.clip(z, -self.clip_range, self.clip_range)

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(
                {
                    "means": self.means.tolist(),
                    "stds": self.stds.tolist(),
                    "clip_range": self.clip_range,
                },
                f,
            )

    @classmethod
    def load(cls, path: str) -> FeatureNormalizer:
        with open(path) as f:
            data = json.load(f)
        return cls(
            means=np.array(data["means"], dtype=np.float32),
            stds=np.array(data["stds"], dtype=np.float32),
            clip_range=data.get("clip_range", 5.0),
        )
