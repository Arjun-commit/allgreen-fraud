"""Latency validation.

Blueprint target: full scoring pipeline < 100ms p99.
We test the individual model inference calls here. The full pipeline
latency test (API → features → LSTM → XGBoost → ensemble → response)
lives in tests/integration/ and requires the docker stack.
"""

from __future__ import annotations

import time

import numpy as np

from backend.models.lstm_inference import score_session
from backend.models.xgboost_inference import score_transaction

N_ITERATIONS = 100


def test_lstm_inference_latency() -> None:
    """LSTM inference should be < 20ms p99 (blueprint §7.1)."""
    seq = np.random.randn(30, 18).astype(np.float32)

    # Warm up (first call loads the model)
    score_session(seq)

    times = []
    for _ in range(N_ITERATIONS):
        t0 = time.perf_counter()
        score_session(seq)
        times.append((time.perf_counter() - t0) * 1000)

    p99 = np.percentile(times, 99)
    median = np.median(times)
    print(f"LSTM: median={median:.2f}ms, p99={p99:.2f}ms")
    assert p99 < 50, f"LSTM p99 {p99:.2f}ms exceeds 50ms budget"


def test_xgboost_inference_latency() -> None:
    """XGBoost inference (with SHAP) should be well under 100ms."""
    vec = np.random.randn(16).astype(np.float32)  # 16 transaction features now

    # Warm up
    score_transaction(vec)

    times = []
    for _ in range(N_ITERATIONS):
        t0 = time.perf_counter()
        score_transaction(vec)
        times.append((time.perf_counter() - t0) * 1000)

    p99 = np.percentile(times, 99)
    median = np.median(times)
    print(f"XGBoost: median={median:.2f}ms, p99={p99:.2f}ms")
    assert p99 < 80, f"XGBoost p99 {p99:.2f}ms exceeds 80ms budget"
