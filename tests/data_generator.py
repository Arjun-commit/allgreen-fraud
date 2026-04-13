"""Synthetic event + feature-vector generator.

Two audiences:
  - tests/unit: quick, small fixtures via generate_normal_session/generate_coached_session
  - ml/: training-ready datasets via build_training_dataset

The generation is deterministic per seed so experiments are reproducible.
"""

from __future__ import annotations

import random
from typing import Literal

import numpy as np

from backend.features.session_extractor import (
    BEHAVIORAL_FEATURE_NAMES,
    extract_session_features,
)

# ------------------------------------------------------------------ #
#  Raw event generators (unchanged from phase 2)                      #
# ------------------------------------------------------------------ #

def generate_normal_session(
    session_id: str = "sess-normal",
    user_id: str = "user-1",
    duration_ms: int = 60_000,
    seed: int = 0,
) -> list[dict]:
    rng = random.Random(seed)
    events: list[dict] = []
    t = 0
    x, y = 500, 400

    while t < duration_ms:
        x += rng.randint(-40, 40)
        y += rng.randint(-30, 30)
        events.append({"type": "mousemove", "x": x, "y": y, "ts_ms": t})
        t += rng.randint(80, 160)

        if rng.random() < 0.05:
            events.append({"type": "click", "x": x, "y": y, "ts_ms": t})
            t += rng.randint(50, 200)

        if rng.random() < 0.08:
            for _ in range(rng.randint(3, 10)):
                kc = rng.randint(65, 90)
                if rng.random() < 0.08:
                    kc = 8  # occasional backspace in normal sessions
                events.append(
                    {"type": "keydown", "key_code": kc, "dwell_ms": rng.randint(60, 140), "ts_ms": t}
                )
                t += rng.randint(90, 180)

        if rng.random() < 0.04:
            events.append({"type": "scroll", "depth": min(1.0, t / duration_ms), "ts_ms": t})
            t += rng.randint(100, 300)

    return events


def generate_coached_session(
    session_id: str = "sess-coached",
    user_id: str = "user-1",
    duration_ms: int = 120_000,
    seed: int = 1,
) -> list[dict]:
    rng = random.Random(seed)
    events: list[dict] = []
    t = 0
    x, y = 600, 500

    while t < duration_ms:
        x += rng.randint(-10, 10)
        y += rng.randint(-8, 8)
        events.append({"type": "mousemove", "x": x, "y": y, "ts_ms": t})
        t += rng.randint(200, 280)

        if rng.random() < 0.10:
            t += rng.randint(3000, 8000)

        if rng.random() < 0.05:
            burst_t = t
            for _ in range(rng.randint(5, 12)):
                events.append(
                    {"type": "keydown", "key_code": rng.randint(48, 57), "dwell_ms": rng.randint(10, 30), "ts_ms": burst_t}
                )
                burst_t += rng.randint(1, 5)
            t = burst_t + rng.randint(500, 2000)

    return events


def make_session_batch(
    kind: Literal["normal", "coached"] = "normal",
    session_id: str = "sess-1",
    user_id: str = "user-1",
) -> dict:
    events = (
        generate_normal_session(session_id=session_id, user_id=user_id)
        if kind == "normal"
        else generate_coached_session(session_id=session_id, user_id=user_id)
    )
    return {"session_id": session_id, "user_id": user_id, "events": events}


# ------------------------------------------------------------------ #
#  Feature-vector dataset builder (phase 3)                           #
# ------------------------------------------------------------------ #

def _session_to_windowed_features(
    events: list[dict],
    window_ms: int = 10_000,
    max_windows: int = 30,
) -> list[dict[str, float]]:
    """Chop a session into time windows and compute features per window.

    The LSTM sees a sequence of these. max_windows=30 → 5 minutes of
    session at 10s windows, matching the blueprint spec.
    """
    if not events:
        return [extract_session_features([])] * max_windows

    min_ts = events[0]["ts_ms"]
    windows: list[list[dict]] = []
    for w in range(max_windows):
        start = min_ts + w * window_ms
        end = start + window_ms
        window_events = [e for e in events if start <= e["ts_ms"] < end]
        windows.append(window_events)

    return [extract_session_features(w) for w in windows]


def build_training_dataset(
    n_normal: int = 1000,
    n_fraud: int = 100,
    window_ms: int = 10_000,
    max_windows: int = 30,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Build (X, y) for LSTM training.

    X shape: (n_normal + n_fraud, max_windows, n_features)
    y shape: (n_normal + n_fraud,)  — 0=normal, 1=fraud

    Also usable for XGBoost by flattening/aggregating X across the time axis.
    """
    n_features = len(BEHAVIORAL_FEATURE_NAMES)
    total = n_normal + n_fraud
    X = np.zeros((total, max_windows, n_features), dtype=np.float32)
    y = np.zeros(total, dtype=np.float32)

    for i in range(n_normal):
        events = generate_normal_session(
            duration_ms=random.Random(seed + i).randint(30_000, 120_000),
            seed=seed + i,
        )
        windows = _session_to_windowed_features(events, window_ms, max_windows)
        for w_idx, feats in enumerate(windows):
            for f_idx, fname in enumerate(BEHAVIORAL_FEATURE_NAMES):
                X[i, w_idx, f_idx] = feats[fname]
        y[i] = 0.0

    for j in range(n_fraud):
        i = n_normal + j
        events = generate_coached_session(
            duration_ms=random.Random(seed + 10000 + j).randint(60_000, 180_000),
            seed=seed + 10000 + j,
        )
        windows = _session_to_windowed_features(events, window_ms, max_windows)
        for w_idx, feats in enumerate(windows):
            for f_idx, fname in enumerate(BEHAVIORAL_FEATURE_NAMES):
                X[i, w_idx, f_idx] = feats[fname]
        y[i] = 1.0

    return X, y


def build_xgboost_dataset(
    n_normal: int = 1000,
    n_fraud: int = 100,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Build (X, y) for XGBoost by aggregating session features across time.

    For XGBoost we collapse the time dimension by taking the mean of each
    feature across all windows. This isn't ideal — a real deployment would
    use the full transaction feature set — but it's enough to validate the
    pipeline end to end.
    """
    X_seq, y = build_training_dataset(n_normal, n_fraud, seed=seed)
    # Mean across the time axis (axis=1) → (n_samples, n_features)
    X_flat = X_seq.mean(axis=1)
    return X_flat, y
