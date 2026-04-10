"""Compute transaction context features for XGBoost.

Pure function. The caller loads the user-history aggregates from Postgres
(cheap: a couple of indexed SUM/COUNT queries keyed by user_id + time window)
and passes them in. We don't hit the DB from here so the function is
trivially testable and trivially cacheable if we ever need to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TRANSACTION_FEATURE_NAMES: tuple[str, ...] = (
    "amount_usd",
    "amount_pct_of_30d_avg",
    "is_round_number",
    "transfer_type_encoded",
    "is_new_payee",
    "payee_age_days",
    "payee_fraud_network_score",
    "days_since_last_large_transfer",
    "large_transfers_30d_count",
    "international_transfers_90d",
    "avg_transfer_amount_90d",
    "behavioral_risk_score",
    "session_duration_at_tx_ms",
    "confirmation_page_dwell_ms",
    "payee_is_mule_candidate",
    "shared_payee_with_flagged_users",
)

_TRANSFER_TYPE_ENCODING: dict[str, int] = {
    "domestic": 0,
    "international": 1,
    "crypto": 2,
}


@dataclass
class UserHistory:
    """90-day aggregates the feature extractor needs.

    Loaded upstream via a few indexed queries on `transactions`.
    """

    avg_transfer_amount_90d: float = 0.0
    avg_transfer_amount_30d: float = 0.0
    large_transfers_30d_count: int = 0
    international_transfers_90d: int = 0
    days_since_last_large_transfer: int = 9999
    # Payee-level: loaded from `transactions` + (eventually) the graph DB.
    payee_age_days: int = 0
    payee_fraud_network_score: float = 0.0
    payee_is_mule_candidate: bool = False
    shared_payee_with_flagged_users: int = 0


@dataclass
class SessionContext:
    """Session-level state the transaction feature extractor needs.

    `behavioral_risk_score` is the LSTM output — the crucial cross-feature.
    """

    behavioral_risk_score: float = 0.0
    session_duration_at_tx_ms: int = 0
    confirmation_page_dwell_ms: int = 0


# Anything ≥ this counts as a "large" transfer for the rolling-window features.
LARGE_TRANSFER_THRESHOLD_USD = 2000.0


def _is_round_number(amount: float) -> bool:
    """Round-to-nearest-hundred heuristic — scammers often ask for nice numbers."""
    if amount <= 0:
        return False
    return amount % 100 == 0


def extract_transaction_features(
    tx: dict[str, Any],
    history: UserHistory,
    session_ctx: SessionContext,
) -> dict[str, float]:
    """Return a dict keyed exactly on TRANSACTION_FEATURE_NAMES.

    `tx` is the transaction dict from the /score request body or Kafka message.
    """
    amount = float(tx.get("amount", 0.0))
    transfer_type = tx.get("transfer_type", "domestic")
    is_new_payee = bool(tx.get("is_new_payee", False))

    avg_30d = history.avg_transfer_amount_30d or 1e-9  # avoid div-by-zero
    amount_pct = amount / avg_30d

    return {
        "amount_usd": amount,
        "amount_pct_of_30d_avg": amount_pct,
        "is_round_number": float(_is_round_number(amount)),
        "transfer_type_encoded": float(_TRANSFER_TYPE_ENCODING.get(transfer_type, 0)),
        "is_new_payee": float(is_new_payee),
        "payee_age_days": float(history.payee_age_days),
        "payee_fraud_network_score": history.payee_fraud_network_score,
        "days_since_last_large_transfer": float(history.days_since_last_large_transfer),
        "large_transfers_30d_count": float(history.large_transfers_30d_count),
        "international_transfers_90d": float(history.international_transfers_90d),
        "avg_transfer_amount_90d": history.avg_transfer_amount_90d,
        "behavioral_risk_score": session_ctx.behavioral_risk_score,
        "session_duration_at_tx_ms": float(session_ctx.session_duration_at_tx_ms),
        "confirmation_page_dwell_ms": float(session_ctx.confirmation_page_dwell_ms),
        "payee_is_mule_candidate": float(history.payee_is_mule_candidate),
        "shared_payee_with_flagged_users": float(history.shared_payee_with_flagged_users),
    }
