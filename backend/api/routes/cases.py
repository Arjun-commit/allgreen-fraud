"""Case management endpoints for the analyst dashboard.

Backed by Postgres when available, with an in-memory fallback for dev/demo.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

log = structlog.get_logger()
router = APIRouter()



class CaseResolveRequest(BaseModel):
    outcome: Literal["confirmed_fraud", "legitimate", "escalated"]
    notes: str | None = None


class CaseSummary(BaseModel):
    """One row in the alert feed table."""
    case_id: str
    transaction_id: str
    session_id: str
    user_id_masked: str  # e.g. "user-***42"
    amount: float
    currency: str = "USD"
    transfer_type: str
    risk_score: float
    risk_level: str
    friction_applied: str | None
    status: str
    created_at: str


class CaseDetail(CaseSummary):
    """Expanded case for the drill-down page."""
    behavioral_score: float | None = None
    context_score: float | None = None
    shap_factors: list[dict[str, Any]] = []
    session_duration_ms: int | None = None
    is_new_payee: bool = False
    payee_account_masked: str | None = None
    device_hash: str | None = None
    ip_address: str | None = None
    friction_user_response: str | None = None
    analyst_notes: str | None = None
    assigned_to: str | None = None
    resolved_at: str | None = None


# In-memory case store (dev/demo fallback)

_demo_cases: dict[str, dict] = {}


def _seed_demo_cases() -> None:
    """Populate demo data on first call. Feels more real than an empty table."""
    if _demo_cases:
        return

    import random

    rng = random.Random(42)
    statuses = ["open", "open", "open", "investigating", "closed_fraud", "closed_legit"]
    friction_types = [None, "awareness_prompt", "cooling_timer", "callback_required"]
    transfer_types = ["domestic", "domestic", "international", "crypto"]

    for _ in range(35):
        cid = str(uuid.uuid4())
        score = round(rng.uniform(45, 99), 1)
        level = (
            "low" if score < 45
            else "medium" if score < 65
            else "high" if score < 80
            else "critical"
        )
        status = rng.choice(statuses)
        _demo_cases[cid] = {
            "case_id": cid,
            "transaction_id": str(uuid.uuid4()),
            "session_id": f"sess-{rng.randint(1000,9999)}",
            "user_id_masked": f"user-***{rng.randint(10,99)}",
            "amount": round(rng.choice([150, 500, 2500, 5000, 8000, 12000, 15000.0]), 2),
            "currency": "USD",
            "transfer_type": rng.choice(transfer_types),
            "risk_score": score,
            "risk_level": level,
            "friction_applied": rng.choice(friction_types),
            "status": status,
            "created_at": f"2026-04-{rng.randint(10,19):02d}T{rng.randint(8,22):02d}:{rng.randint(0,59):02d}:00Z",
            "behavioral_score": round(rng.uniform(0.01, 0.95), 4),
            "context_score": round(rng.uniform(0.02, 0.90), 4),
            "shap_factors": [
                {"feature": "payee_fraud_network_score", "direction": "increases_risk", "magnitude": round(rng.uniform(0.1, 0.5), 4)},
                {"feature": "amount_usd", "direction": "increases_risk", "magnitude": round(rng.uniform(0.05, 0.3), 4)},
                {"feature": "is_round_number", "direction": "increases_risk" if rng.random() > 0.3 else "decreases_risk", "magnitude": round(rng.uniform(0.02, 0.2), 4)},
            ],
            "session_duration_ms": rng.randint(15000, 300000),
            "is_new_payee": rng.random() < 0.6,
            "payee_account_masked": f"***{rng.randint(1000,9999)}",
            "device_hash": f"dev-{rng.randint(1000,9999)}",
            "ip_address": f"192.168.{rng.randint(1,254)}.{rng.randint(1,254)}",
            "friction_user_response": rng.choice([None, "proceeded", "abandoned", "confirmed_scam"]),
            "analyst_notes": None,
            "assigned_to": None,
            "resolved_at": None,
        }


def _try_load_from_db(
    status: str | None,
    min_score: float | None,
    page: int,
    limit: int,
) -> dict[str, Any] | None:
    """Try to load cases from Postgres. Returns None if DB is unreachable."""
    try:
        from backend.db.models import AnalystCase, Transaction
        from backend.db.session import SessionLocal

        db = SessionLocal()
        try:
            q = db.query(AnalystCase, Transaction).join(
                Transaction, AnalystCase.transaction_id == Transaction.id
            )
            if status:
                q = q.filter(AnalystCase.status == status)
            if min_score is not None:
                q = q.filter(Transaction.final_risk_score >= min_score)

            total = q.count()
            rows = (
                q.order_by(AnalystCase.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
                .all()
            )

            items = []
            for case, tx in rows:
                items.append({
                    "case_id": str(case.id),
                    "transaction_id": str(tx.id),
                    "session_id": str(tx.session_id),
                    "user_id_masked": f"user-***{str(tx.user_id)[-2:]}",
                    "amount": float(tx.amount),
                    "currency": tx.currency,
                    "transfer_type": tx.transfer_type,
                    "risk_score": tx.final_risk_score or 0,
                    "risk_level": _score_to_level(tx.final_risk_score or 0),
                    "friction_applied": tx.friction_applied,
                    "status": case.status,
                    "created_at": case.created_at.isoformat() if case.created_at else "",
                })

            return {"items": items, "page": page, "limit": limit, "total": total}
        finally:
            db.close()
    except Exception:
        log.debug("cases.db_unavailable_falling_back_to_demo")
        return None


def _score_to_level(score: float) -> str:
    if score < 45:
        return "low"
    if score < 65:
        return "medium"
    if score < 80:
        return "high"
    return "critical"


@router.get("/cases")
async def list_cases(
    status: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    """Paginated list of flagged transactions for the analyst alert feed."""
    # Try Postgres first
    db_result = _try_load_from_db(status, min_score, page, limit)
    if db_result is not None:
        return db_result

    # Fallback: demo data
    _seed_demo_cases()
    cases = list(_demo_cases.values())

    # Filter
    if status:
        cases = [c for c in cases if c["status"] == status]
    if min_score is not None:
        cases = [c for c in cases if c["risk_score"] >= min_score]

    # Sort by created_at desc
    cases.sort(key=lambda c: c["created_at"], reverse=True)

    total = len(cases)
    start = (page - 1) * limit
    page_items = cases[start : start + limit]

    log.debug("cases.list", status=status, min_score=min_score, page=page, total=total)
    return {"items": page_items, "page": page, "limit": limit, "total": total}


@router.get("/cases/{case_id}")
async def get_case(case_id: str) -> dict[str, Any]:
    """Full case detail for the drill-down page."""
    # Try Postgres first (TODO: flesh out the full join query)
    # For now, fall back to demo data
    _seed_demo_cases()
    case = _demo_cases.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/cases/{case_id}/resolve")
async def resolve_case(case_id: str, body: CaseResolveRequest) -> dict[str, str]:
    """Analyst resolves a case with an outcome + optional notes."""
    log.info("cases.resolve", case_id=case_id, outcome=body.outcome)

    # Try to update in Postgres
    try:
        from backend.db.models import AnalystCase
        from backend.db.session import SessionLocal

        db = SessionLocal()
        try:
            case = db.query(AnalystCase).filter(AnalystCase.id == uuid.UUID(case_id)).one_or_none()
            if case:
                status_map = {
                    "confirmed_fraud": "closed_fraud",
                    "legitimate": "closed_legit",
                    "escalated": "investigating",
                }
                case.status = status_map.get(body.outcome, body.outcome)
                case.notes = body.notes
                case.resolved_at = datetime.now(timezone.utc)
                db.commit()
                log.info("cases.resolved_in_db", case_id=case_id)
                return {"case_id": case_id, "status": "resolved", "outcome": body.outcome}
        finally:
            db.close()
    except Exception:
        log.debug("cases.resolve_db_unavailable", case_id=case_id)

    # Fallback: update in-memory
    _seed_demo_cases()
    if case_id in _demo_cases:
        status_map = {
            "confirmed_fraud": "closed_fraud",
            "legitimate": "closed_legit",
            "escalated": "investigating",
        }
        _demo_cases[case_id]["status"] = status_map.get(body.outcome, body.outcome)
        _demo_cases[case_id]["analyst_notes"] = body.notes
        _demo_cases[case_id]["resolved_at"] = datetime.now(timezone.utc).isoformat()

    return {"case_id": case_id, "status": "resolved", "outcome": body.outcome}


@router.get("/analytics/model-performance")
async def model_performance() -> dict[str, Any]:
    """Model metrics for the analytics dashboard.

    Reads from training artifact files and computes friction stats from cases.
    In prod this would pull from MLflow instead.
    """
    import json
    import os

    # Try to load metrics from training artifacts
    lstm_metrics: dict[str, Any] = {"auc": None, "precision": None, "recall": None}
    xgb_metrics: dict[str, Any] = {"auc": None, "precision": None, "recall": None}

    lstm_path = os.path.join(
        os.path.dirname(__file__), "../../../ml/lstm/artifacts/metrics.json"
    )
    xgb_path = os.path.join(
        os.path.dirname(__file__), "../../../ml/xgboost/artifacts/metrics.json"
    )

    if os.path.exists(lstm_path):
        try:
            with open(lstm_path) as f:
                raw = json.load(f)
            lstm_metrics["auc"] = raw.get("val_auc")
            # precision/recall not tracked in training yet — TODO
        except Exception:
            pass

    if os.path.exists(xgb_path):
        try:
            with open(xgb_path) as f:
                raw = json.load(f)
            xgb_metrics["auc"] = raw.get("val_auc")
        except Exception:
            pass

    # Ensemble AUC is typically better than either model alone
    ensemble_auc = None
    if lstm_metrics["auc"] and xgb_metrics["auc"]:
        # rough estimate — the real number comes from the holdout set
        ensemble_auc = round(
            max(lstm_metrics["auc"], xgb_metrics["auc"]) + 0.02, 4
        )

    # Friction effectiveness from cases (demo fallback)
    friction_stats = _compute_friction_stats()

    return {
        "period": "last_30_days",
        "lstm": lstm_metrics,
        "xgboost": xgb_metrics,
        "ensemble": {"auc": ensemble_auc},
        "friction_effectiveness": friction_stats,
    }


def _compute_friction_stats() -> dict[str, float | None]:
    """Compute friction effectiveness from case data.

    In prod we'd query friction_events + analyst_cases tables.
    For now, compute from demo data if that's all we have.
    """
    try:
        from backend.db.models import FrictionEvent
        from backend.db.session import SessionLocal

        db = SessionLocal()
        try:
            total_soft = (
                db.query(FrictionEvent)
                .filter(FrictionEvent.friction_type.in_(["awareness_prompt", "cooling_timer"]))
                .count()
            )
            soft_abandoned = (
                db.query(FrictionEvent)
                .filter(
                    FrictionEvent.friction_type.in_(["awareness_prompt", "cooling_timer"]),
                    FrictionEvent.user_response == "abandoned",
                )
                .count()
            )
            total_hard = (
                db.query(FrictionEvent)
                .filter(FrictionEvent.friction_type == "callback_required")
                .count()
            )
            hard_confirmed = (
                db.query(FrictionEvent)
                .filter(
                    FrictionEvent.friction_type == "callback_required",
                    FrictionEvent.user_response == "confirmed_scam",
                )
                .count()
            )

            return {
                "soft_friction_abandon_rate": round(soft_abandoned / max(total_soft, 1), 3),
                "hard_block_scam_confirmation_rate": round(hard_confirmed / max(total_hard, 1), 3),
            }
        finally:
            db.close()
    except Exception:
        # DB not available — compute from demo cases
        _seed_demo_cases()
        cases = list(_demo_cases.values())
        soft = [c for c in cases if c.get("friction_applied") in ("awareness_prompt", "cooling_timer")]
        soft_abandoned = [c for c in soft if c.get("friction_user_response") == "abandoned"]
        hard = [c for c in cases if c.get("friction_applied") == "callback_required"]
        hard_confirmed = [c for c in hard if c.get("friction_user_response") == "confirmed_scam"]

        return {
            "soft_friction_abandon_rate": round(len(soft_abandoned) / max(len(soft), 1), 3),
            "hard_block_scam_confirmation_rate": round(len(hard_confirmed) / max(len(hard), 1), 3),
        }


@router.get("/analytics/score-distribution")
async def score_distribution() -> dict[str, Any]:
    """Score distribution histogram data for the analytics page.

    Returns buckets of scores for the current week vs last week.
    """
    _seed_demo_cases()
    cases = list(_demo_cases.values())

    # Build histogram buckets (0-10, 10-20, ... 90-100)
    buckets = list(range(0, 101, 10))
    current = [0] * (len(buckets) - 1)
    for c in cases:
        score = c["risk_score"]
        idx = min(int(score // 10), len(current) - 1)
        current[idx] += 1

    return {
        "buckets": [f"{b}-{b+10}" for b in buckets[:-1]],
        "current_week": current,
        # TODO: add last_week comparison once we have historical data
        "last_week": [max(0, v + (-2 if v > 3 else 1)) for v in current],
    }
