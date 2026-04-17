"""POST /score — the hot path.

Called by the bank's core banking system when a user initiates a transfer.
Runs the full scoring pipeline: features → LSTM → XGBoost → ensemble →
friction decision. Target latency: < 100ms.

The session events are loaded from the DB (session_events table, populated
by the Kafka consumer). In production we'd read from the Redis feature cache
first and fall back to DB; for now we always hit the DB because the consumer
might not have cached features yet.
"""

from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.features.transaction_extractor import UserHistory
from backend.kafka import topics
from backend.kafka.producer import publish
from backend.scoring.pipeline import ScoringInput, run_pipeline

log = structlog.get_logger()
router = APIRouter()


# ---------- Request / Response schemas (unchanged from phase 1 contract) ----------

class ScoreTxInput(BaseModel):
    amount: float
    currency: str = "USD"
    payee_account: str
    payee_name: str | None = None
    transfer_type: Literal["domestic", "international", "crypto"] = "domestic"
    is_new_payee: bool = False


class ScoreRequest(BaseModel):
    session_id: str
    transaction: ScoreTxInput


class FrictionPayload(BaseModel):
    type: Literal["none", "awareness_prompt", "cooling_timer", "callback_required"]
    duration_seconds: int | None = None
    message: str | None = None


class ShapFactor(BaseModel):
    feature: str
    direction: Literal["increases_risk", "decreases_risk"]
    magnitude: float


class ScoreResponse(BaseModel):
    transaction_id: str
    risk_score: float = Field(..., ge=0, le=100)
    risk_level: Literal["low", "medium", "high", "critical"]
    behavioral_score: float
    context_score: float
    friction: FrictionPayload
    shap_top_factors: list[ShapFactor]


# ---------- Event loading ----------

def _load_session_events(session_id: str) -> list[dict]:
    """Load raw session events for scoring.

    Phase 4: we pull from the session_events table via SQLAlchemy.
    In a future optimization pass we'd check the Redis feature cache first
    and skip the raw-event load entirely if features are already computed.

    For now, if we can't find events, we return an empty list — the pipeline
    handles that gracefully (all features → 0, models return low-risk).
    """
    try:
        from backend.db.models import Session as SessionRow
        from backend.db.models import SessionEventRow
        from backend.db.session import SessionLocal

        db = SessionLocal()
        try:
            sess = (
                db.query(SessionRow)
                .filter(SessionRow.session_token == session_id)
                .one_or_none()
            )
            if sess is None:
                log.debug("score.session_not_found", session_id=session_id)
                return []
            rows = (
                db.query(SessionEventRow)
                .filter(SessionEventRow.session_id == sess.id)
                .order_by(SessionEventRow.timestamp_ms)
                .all()
            )
            return [
                {"type": r.event_type, "ts_ms": r.timestamp_ms, **(r.event_data or {})}
                for r in rows
            ]
        finally:
            db.close()
    except Exception:
        # If DB is unreachable, score with empty events rather than 500.
        log.exception("score.load_events_failed", session_id=session_id)
        return []


def _load_user_history(session_id: str) -> UserHistory:
    """Load 90-day aggregates for the user behind this session.

    TODO(phase-4.5): real implementation that queries transactions table.
    For now returns defaults — the XGBoost will rely more on the
    behavioral_risk_score cross-feature until we wire this up.
    """
    return UserHistory()


# ---------- Route ----------

@router.post("/score", response_model=ScoreResponse)
async def score_transaction(req: ScoreRequest) -> ScoreResponse:
    events = _load_session_events(req.session_id)

    inp = ScoringInput(
        session_id=req.session_id,
        session_events=events,
        transaction=req.transaction.model_dump(),
        user_history=_load_user_history(req.session_id),
    )

    result = run_pipeline(inp)

    # Build the friction payload for the response
    friction_payload = FrictionPayload(type="none")
    if result.friction_type != "none" and result.friction_payload:
        friction_payload = FrictionPayload(
            type=result.friction_type,
            duration_seconds=result.friction_payload.get("duration_seconds"),
            message=result.friction_payload.get("body"),
        )

    # Publish final scores to Kafka for the dashboard + case system
    try:
        publish(
            topics.SCORES_FINAL,
            {
                "transaction_id": result.transaction_id,
                "session_id": req.session_id,
                "risk_score": result.risk_score,
                "risk_level": result.risk_level,
                "behavioral_score": result.behavioral_score,
                "context_score": result.context_score,
            },
            key=req.session_id,
        )
        if result.friction_type != "none":
            publish(
                topics.FRICTION_DECISIONS,
                {
                    "session_id": req.session_id,
                    "friction_type": result.friction_type,
                    "payload": result.friction_payload,
                    "transaction_id": result.transaction_id,
                },
                key=req.session_id,
            )
    except Exception:
        log.exception("score.kafka_publish_failed")

    return ScoreResponse(
        transaction_id=result.transaction_id,
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        behavioral_score=result.behavioral_score,
        context_score=result.context_score,
        friction=friction_payload,
        shap_top_factors=[
            ShapFactor(**f)
            for f in result.shap_top_factors
        ],
    )
