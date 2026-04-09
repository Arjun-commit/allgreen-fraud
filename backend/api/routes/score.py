"""POST /score — the hot path. Called when user initiates a transfer.

Phase 1: returns a deterministic stub so the bank frontend team can start
integrating against the contract. Real scoring lands in phase 4.
"""

from typing import Literal

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

log = structlog.get_logger()
router = APIRouter()


class ScoreTxInput(BaseModel):
    amount: float
    currency: str = "USD"
    payee_account: str
    payee_name: str | None = None
    transfer_type: Literal["domestic", "international", "crypto"] = "domestic"


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


@router.post("/score", response_model=ScoreResponse)
async def score_transaction(req: ScoreRequest) -> ScoreResponse:
    # STUB. Returns a low-risk "allow" response so the frontend team can wire
    # against the contract without the models being ready.
    # Phase 4 replaces this with: feature lookup → LSTM → XGBoost → ensemble → friction.
    log.info(
        "score.stub.called",
        session_id=req.session_id,
        amount=req.transaction.amount,
    )
    return ScoreResponse(
        transaction_id="stub-00000000-0000-0000-0000-000000000000",
        risk_score=12.0,
        risk_level="low",
        behavioral_score=0.10,
        context_score=0.15,
        friction=FrictionPayload(type="none"),
        shap_top_factors=[],
    )
