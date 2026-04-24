"""Synthetic event and feature-vector generator for tests."""

from __future__ import annotations

import random
from typing import Literal

import numpy as np

from backend.features.session_extractor import (
    BEHAVIORAL_FEATURE_NAMES,
    extract_session_features,
)


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



def _session_to_windowed_features(
    events: list[dict],
    window_ms: int = 10_000,
    max_windows: int = 30,
) -> list[dict[str, float]]:
    """Chop a session into time windows and compute features per window.

    The LSTM sees a sequence of these. max_windows=30 covers ~5 minutes
    of session at 10s windows.
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
    """Build (X, y) for XGBoost using transaction-context features (16-dim).

    Generates realistic-ish transaction context: normal sessions get
    normal amounts to known payees; fraud sessions get larger amounts
    to new payees with elevated behavioral scores.
    """
    from backend.features.transaction_extractor import (
        TRANSACTION_FEATURE_NAMES,
        SessionContext,
        UserHistory,
        extract_transaction_features,
    )

    rng = random.Random(seed)
    n_features = len(TRANSACTION_FEATURE_NAMES)
    total = n_normal + n_fraud
    X = np.zeros((total, n_features), dtype=np.float32)
    y = np.zeros(total, dtype=np.float32)

    for i in range(n_normal):
        # Normal: reasonable amount, known payee, low behavioral score
        tx = {
            "amount": rng.uniform(50, 2000),
            "transfer_type": rng.choice(["domestic", "domestic", "domestic", "international"]),
            "is_new_payee": rng.random() < 0.1,
        }
        history = UserHistory(
            avg_transfer_amount_90d=rng.uniform(200, 1500),
            avg_transfer_amount_30d=rng.uniform(200, 1500),
            large_transfers_30d_count=rng.randint(0, 3),
            international_transfers_90d=rng.randint(0, 2),
            days_since_last_large_transfer=rng.randint(1, 60),
            payee_age_days=rng.randint(30, 1000),
            payee_fraud_network_score=rng.uniform(0, 0.05),
            payee_is_mule_candidate=False,
            shared_payee_with_flagged_users=0,
        )
        ctx = SessionContext(
            behavioral_risk_score=rng.uniform(0, 0.2),
            session_duration_at_tx_ms=rng.randint(10_000, 120_000),
            confirmation_page_dwell_ms=rng.randint(2000, 15_000),
        )
        feats = extract_transaction_features(tx, history, ctx)
        for f_idx, fname in enumerate(TRANSACTION_FEATURE_NAMES):
            X[i, f_idx] = feats[fname]
        y[i] = 0.0

    for j in range(n_fraud):
        i = n_normal + j
        # Fraud: larger round amounts, new payees, high behavioral score
        tx = {
            "amount": rng.choice([3000, 5000, 8000, 10000, 15000.0]),
            "transfer_type": rng.choice(["domestic", "international", "crypto"]),
            "is_new_payee": True,
        }
        history = UserHistory(
            avg_transfer_amount_90d=rng.uniform(200, 800),
            avg_transfer_amount_30d=rng.uniform(200, 600),
            large_transfers_30d_count=rng.randint(0, 1),
            international_transfers_90d=rng.randint(0, 1),
            days_since_last_large_transfer=rng.randint(30, 200),
            payee_age_days=0,
            payee_fraud_network_score=rng.uniform(0.3, 0.9),
            payee_is_mule_candidate=rng.random() < 0.4,
            shared_payee_with_flagged_users=rng.randint(1, 5),
        )
        ctx = SessionContext(
            behavioral_risk_score=rng.uniform(0.5, 1.0),
            session_duration_at_tx_ms=rng.randint(60_000, 300_000),
            confirmation_page_dwell_ms=rng.randint(500, 3000),
        )
        feats = extract_transaction_features(tx, history, ctx)
        for f_idx, fname in enumerate(TRANSACTION_FEATURE_NAMES):
            X[i, f_idx] = feats[fname]
        y[i] = 1.0

    return X, y
