"""Transaction context features for XGBoost.

Phase 2 placeholder.
"""

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


def extract_transaction_features(tx: dict, user_history: dict) -> dict[str, float]:
    """Return dict of features. TODO(phase-2)."""
    return {name: 0.0 for name in TRANSACTION_FEATURE_NAMES}
