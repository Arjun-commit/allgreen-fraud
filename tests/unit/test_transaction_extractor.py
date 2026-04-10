"""Unit tests for backend.features.transaction_extractor."""

from __future__ import annotations

import pytest

from backend.features.transaction_extractor import (
    TRANSACTION_FEATURE_NAMES,
    SessionContext,
    UserHistory,
    extract_transaction_features,
)


def _default_history(**over) -> UserHistory:
    h = UserHistory(
        avg_transfer_amount_90d=500.0,
        avg_transfer_amount_30d=400.0,
        large_transfers_30d_count=1,
        international_transfers_90d=0,
        days_since_last_large_transfer=15,
        payee_age_days=200,
        payee_fraud_network_score=0.02,
        payee_is_mule_candidate=False,
        shared_payee_with_flagged_users=0,
    )
    for k, v in over.items():
        setattr(h, k, v)
    return h


def _default_ctx(**over) -> SessionContext:
    c = SessionContext(
        behavioral_risk_score=0.1,
        session_duration_at_tx_ms=60_000,
        confirmation_page_dwell_ms=3500,
    )
    for k, v in over.items():
        setattr(c, k, v)
    return c


def test_output_has_every_declared_feature() -> None:
    feats = extract_transaction_features(
        {"amount": 100, "transfer_type": "domestic", "is_new_payee": False},
        _default_history(),
        _default_ctx(),
    )
    assert set(feats.keys()) == set(TRANSACTION_FEATURE_NAMES)


def test_amount_pct_of_30d_avg_is_ratio() -> None:
    feats = extract_transaction_features(
        {"amount": 2000, "transfer_type": "domestic", "is_new_payee": False},
        _default_history(avg_transfer_amount_30d=400.0),
        _default_ctx(),
    )
    assert feats["amount_pct_of_30d_avg"] == pytest.approx(5.0)


def test_round_numbers_flagged() -> None:
    feats = extract_transaction_features(
        {"amount": 5000, "transfer_type": "domestic", "is_new_payee": False},
        _default_history(),
        _default_ctx(),
    )
    assert feats["is_round_number"] == 1.0

    feats2 = extract_transaction_features(
        {"amount": 5137.42, "transfer_type": "domestic", "is_new_payee": False},
        _default_history(),
        _default_ctx(),
    )
    assert feats2["is_round_number"] == 0.0


def test_transfer_type_encoding() -> None:
    for tt, expected in [("domestic", 0), ("international", 1), ("crypto", 2)]:
        feats = extract_transaction_features(
            {"amount": 100, "transfer_type": tt, "is_new_payee": False},
            _default_history(),
            _default_ctx(),
        )
        assert feats["transfer_type_encoded"] == float(expected)


def test_new_payee_flag_passes_through() -> None:
    feats = extract_transaction_features(
        {"amount": 100, "transfer_type": "domestic", "is_new_payee": True},
        _default_history(),
        _default_ctx(),
    )
    assert feats["is_new_payee"] == 1.0


def test_behavioral_score_cross_feature_preserved() -> None:
    feats = extract_transaction_features(
        {"amount": 100, "transfer_type": "domestic", "is_new_payee": False},
        _default_history(),
        _default_ctx(behavioral_risk_score=0.87),
    )
    assert feats["behavioral_risk_score"] == 0.87


def test_missing_30d_avg_does_not_crash() -> None:
    feats = extract_transaction_features(
        {"amount": 100, "transfer_type": "domestic", "is_new_payee": False},
        _default_history(avg_transfer_amount_30d=0.0),
        _default_ctx(),
    )
    # Should produce a large ratio, but no div-by-zero
    assert feats["amount_pct_of_30d_avg"] > 0
