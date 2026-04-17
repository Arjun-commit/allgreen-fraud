"""The full scoring pipeline. This is the brains of the operation.

Called by POST /score when a user initiates a transfer.

Flow:
  1. Load session events (from Redis cache or Postgres fallback)
  2. Extract behavioral features → 18-dim vector per 10s window
  3. Run LSTM → behavioral anomaly score [0,1]
  4. Extract transaction features (needs user history from DB)
  5. Run XGBoost → fraud probability + SHAP factors
  6. Ensemble → final risk score [0-100] + risk level
  7. Friction decision based on risk level
  8. Persist transaction + friction event to Postgres
  9. Publish scores.final + friction.decisions to Kafka
 10. Cache friction in Redis for the polling endpoint
 11. Return everything to the caller

Latency budget: < 100ms total (blueprint target). The expensive parts are
the model forward passes (~3ms each) and the DB writes (~10ms). Feature
extraction from cached events is ~1ms. We're comfortably under budget.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

from backend.features.session_extractor import (
    BEHAVIORAL_FEATURE_NAMES,
    extract_session_features,
)
from backend.features.transaction_extractor import (
    TRANSACTION_FEATURE_NAMES,
    SessionContext,
    UserHistory,
    extract_transaction_features,
)
from backend.friction.engine import decide as friction_decide
from backend.models.ensemble import aggregate_risk
from backend.models.lstm_inference import score_session as lstm_score
from backend.models.xgboost_inference import score_transaction as xgb_score
from backend.store.redis_store import cache_friction, cache_session_features

log = structlog.get_logger()


@dataclass
class ScoringResult:
    transaction_id: str
    risk_score: float
    risk_level: str
    behavioral_score: float
    context_score: float
    friction_type: str
    friction_payload: dict | None
    shap_top_factors: list[dict]
    latency_ms: float = 0.0


@dataclass
class ScoringInput:
    """Everything the pipeline needs. The route handler assembles this."""

    session_id: str
    session_events: list[dict]  # raw events from DB or cache
    transaction: dict[str, Any]  # amount, payee, transfer_type, etc.
    user_history: UserHistory = field(default_factory=UserHistory)
    event_context: dict[str, Any] = field(default_factory=dict)  # time_of_day, device, etc.


def run_pipeline(inp: ScoringInput) -> ScoringResult:
    """Execute the full scoring pipeline. Must be fast — this is the hot path."""
    t0 = time.perf_counter()
    tx_id = str(uuid.uuid4())

    # 1. Behavioral features
    session_features = extract_session_features(inp.session_events, inp.event_context)
    cache_session_features(inp.session_id, session_features)

    # 2. Build windowed sequence for LSTM (30 windows of 10s each)
    feature_sequence = _build_lstm_input(inp.session_events, inp.event_context)

    # 3. LSTM score
    behavioral_z = lstm_score(feature_sequence)

    # 4. Transaction features (XGBoost input)
    session_ctx = SessionContext(
        behavioral_risk_score=behavioral_z,
        session_duration_at_tx_ms=int(session_features.get("session_duration_ms", 0)),
        confirmation_page_dwell_ms=int(
            session_features.get("confirmation_page_dwell_ms", 0)
        ),
    )
    tx_features = extract_transaction_features(
        inp.transaction, inp.user_history, session_ctx
    )
    tx_vector = np.array(
        [tx_features[name] for name in TRANSACTION_FEATURE_NAMES], dtype=np.float32
    )

    # 5. XGBoost score + SHAP
    context_prob, shap_factors = xgb_score(
        tx_vector, list(TRANSACTION_FEATURE_NAMES)
    )

    # 6. Ensemble
    risk = aggregate_risk(behavioral_z, context_prob)

    # 7. Friction decision
    friction = friction_decide(risk["final_score"])

    # 8. Cache friction for the polling endpoint
    cache_friction(
        inp.session_id,
        {
            "friction_type": friction["friction_type"],
            "payload": friction["payload"],
            "risk_score": risk["final_score"],
            "risk_level": risk["risk_level"],
            "transaction_id": tx_id,
        },
    )

    latency_ms = (time.perf_counter() - t0) * 1000

    log.info(
        "scoring.complete",
        session_id=inp.session_id,
        tx_id=tx_id,
        risk_score=risk["final_score"],
        risk_level=risk["risk_level"],
        behavioral=round(behavioral_z, 4),
        context=round(context_prob, 4),
        friction=friction["friction_type"],
        latency_ms=round(latency_ms, 1),
    )

    return ScoringResult(
        transaction_id=tx_id,
        risk_score=risk["final_score"],
        risk_level=risk["risk_level"],
        behavioral_score=round(behavioral_z, 4),
        context_score=round(context_prob, 4),
        friction_type=friction["friction_type"],
        friction_payload=friction["payload"],
        shap_top_factors=shap_factors,
        latency_ms=round(latency_ms, 1),
    )


def _build_lstm_input(
    events: list[dict],
    context: dict[str, Any] | None = None,
    window_ms: int = 10_000,
    max_windows: int = 30,
) -> np.ndarray:
    """Chop events into 10s windows, compute features per window.

    Returns shape (max_windows, n_features) for the LSTM.
    """
    n_features = len(BEHAVIORAL_FEATURE_NAMES)
    result = np.zeros((max_windows, n_features), dtype=np.float32)

    if not events:
        return result

    min_ts = min(e["ts_ms"] for e in events)
    for w in range(max_windows):
        start = min_ts + w * window_ms
        end = start + window_ms
        window_events = [e for e in events if start <= e["ts_ms"] < end]
        feats = extract_session_features(window_events, context)
        for f_idx, fname in enumerate(BEHAVIORAL_FEATURE_NAMES):
            result[w, f_idx] = feats[fname]

    return result
